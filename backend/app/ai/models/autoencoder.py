"""
app/ai/models/autoencoder.py — Autoencoder anomaly-detection model wrapper.

Concrete BaseModel implementation backed by a small feed-forward PyTorch
autoencoder. Anomalies are flagged by reconstruction error: the network is
trained (offline, not here) to reconstruct normal traffic well; a sample
the network reconstructs poorly is scored as anomalous. load_weights()
deserializes a *pre-trained* checkpoint from disk — this module does not
fit/train a model itself, mirroring the "no training" constraint already
established for app.ai.models.isolation_forest.IsolationForestModel.

PyTorch is imported lazily, inside load_weights()/to_device()/predict()
only — never at module import time, and the nn.Module architecture class
itself is defined *inside* a function (see _build_autoencoder_net()) so
merely importing this file never triggers `import torch`. Importing
app.ai.models (or this file directly) must succeed on a machine with no
PyTorch installed, matching the pattern already established for sklearn
in isolation_forest.py and for torch in app/ai/utils/device.py.

CUDA optimization
-----------------
- Automatic detection: __init__ defaults self._device to
  get_device("auto") (CUDA if available, else CPU) so direct usage
  already prefers CUDA without requiring an explicit to_device() call;
  ModelManager's own explicit to_device(device) call still takes
  precedence, so callers that request "cpu" always get CPU.
- CPU fallback: get_device() (app.ai.utils.device — the same helper
  InferenceEngine/ModelManager already use elsewhere) resolves "cpu" |
  "cuda" | "auto" and falls back to "cpu" whenever CUDA/torch is
  unavailable, so this model is always usable on CPU-only machines.
- Device placement happens exactly twice, not per prediction:
  load_weights() and to_device() are the only two places self._net's
  device is changed, and both immediately move the model there. predict()
  therefore never re-issues a `.to(device)` on the model on every call —
  only the input tensor moves, and it moves once, as a single batched
  transfer covering the whole TensorBatch (never per-row).
- torch.inference_mode() (not torch.no_grad()) wraps the forward pass —
  it skips the same gradient tracking no_grad() does plus the extra
  autograd version-counter bookkeeping, which matters on a hot inference
  path invoked for every SentinelX analysis.

Checkpoint contract
-------------------
load_weights(path) expects a checkpoint produced by an offline training
step via:

    torch.save({
        "state_dict": model.state_dict(),
        "input_dim": <int>,                          # required
        "hidden_dim": <int>,                          # optional, default 16
        "latent_dim": <int>,                          # optional, default 8
        "reconstruction_error_threshold": <float>,     # optional, default 1.0
    }, path)

`input_dim` must match the width of the TensorBatch rows produced by
PreprocessingPipeline for the fitted feature set this checkpoint was
trained against.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.exceptions import InferenceError, ModelLoadError
from app.ai.preprocessing.tensor_prep import TensorBatch
from app.ai.utils.device import get_device, is_cuda_available

from .base import BaseModel
from .registry import register_model

MODEL_NAME = "autoencoder"
_DEFAULT_HIDDEN_DIM = 16
_DEFAULT_LATENT_DIM = 8
_DEFAULT_RECONSTRUCTION_ERROR_THRESHOLD = 1.0


def _build_autoencoder_net(input_dim: int, hidden_dim: int, latent_dim: int) -> Any:
    """
    Lazily define and instantiate the autoencoder architecture.

    The nn.Module subclass is defined *inside* this function, not at
    module level, so that the `class _AutoencoderNet(nn.Module):`
    statement — which would otherwise require torch to already be
    imported at module-import time — only ever executes when a caller
    actually needs a network (i.e. inside load_weights()).
    """
    import torch.nn as nn

    class _AutoencoderNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = nn.Sequential(
                nn.Linear(input_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, latent_dim),
                nn.ReLU(),
            )
            self.decoder = nn.Sequential(
                nn.Linear(latent_dim, hidden_dim),
                nn.ReLU(),
                nn.Linear(hidden_dim, input_dim),
            )

        def forward(self, x):
            return self.decoder(self.encoder(x))

    return _AutoencoderNet()


@dataclass
class AutoencoderPrediction:
    """
    Structured prediction output — deliberately the same shape as
    IsolationForestPrediction (see app.ai.models.isolation_forest) so
    InferenceEngine's duck-typed model-agnostic contract
    (.prediction/.confidence/.metadata) is satisfied without any change
    to InferenceEngine or SentinelXEngine.
    """

    prediction: list[int]  # 1 = anomaly/attack, 0 = normal — matches TensorBatch.labels convention
    confidence: list[float]  # confidence that each sample is anomalous, in [0, 1]
    metadata: dict[str, Any]


@register_model(MODEL_NAME)
class AutoencoderModel(BaseModel):
    """
    Reconstruction-error-based anomaly-detection wrapper around a small
    feed-forward PyTorch autoencoder.

    Lifecycle is owned externally by app.ai.models.ModelManager — this
    class never manages its own load/unload state:

        model = AutoencoderModel()
        model.load_weights("path/to/autoencoder.pt")
        model.to_device("cuda")  # or "cpu" / "auto" — CPU-safe either way
        result = model.predict(tensor_batch)  # TensorBatch from PreprocessingPipeline
    """

    def __init__(self) -> None:
        self._net: Any = None
        # Auto-detect the best device up front (get_device("auto") ->
        # "cuda" if available, else "cpu") rather than hardcoding "cpu",
        # so direct usage of this class without an explicit to_device()
        # call still prefers CUDA when it's available. An explicit
        # to_device() call (as ModelManager.load() always makes) still
        # takes precedence over this default.
        self._device: str = get_device("auto")
        self._weights_path: str | None = None
        self._input_dim: int | None = None
        self._threshold: float = _DEFAULT_RECONSTRUCTION_ERROR_THRESHOLD

    def load_weights(self, path: str) -> None:
        """
        Deserialize a previously trained autoencoder checkpoint from `path`.

        No training happens here — see the module docstring for the
        expected checkpoint contract.
        """
        try:
            import torch
        except ImportError as exc:
            raise ModelLoadError(
                "PyTorch is not installed. Add torch to backend/requirements.txt "
                "before loading AutoencoderModel weights.",
                details={"path": path},
            ) from exc

        try:
            checkpoint = torch.load(path, map_location="cpu")
        except FileNotFoundError as exc:
            raise ModelLoadError(f"Autoencoder weights file not found: {path}") from exc
        except Exception as exc:
            raise ModelLoadError(f"Failed to load autoencoder weights from {path}: {exc}") from exc

        self._validate_checkpoint(checkpoint)

        input_dim = int(checkpoint["input_dim"])
        hidden_dim = int(checkpoint.get("hidden_dim", _DEFAULT_HIDDEN_DIM))
        latent_dim = int(checkpoint.get("latent_dim", _DEFAULT_LATENT_DIM))

        net = _build_autoencoder_net(input_dim=input_dim, hidden_dim=hidden_dim, latent_dim=latent_dim)
        try:
            net.load_state_dict(checkpoint["state_dict"])
        except Exception as exc:
            raise ModelLoadError(f"Autoencoder state_dict incompatible with architecture: {exc}") from exc
        net.eval()

        self._net = net
        self._input_dim = input_dim
        self._threshold = float(
            checkpoint.get("reconstruction_error_threshold", _DEFAULT_RECONSTRUCTION_ERROR_THRESHOLD)
        )
        self._weights_path = path
        self._net.to(torch.device(self._device))

    def to_device(self, device: str) -> None:
        """
        Move the model onto `device` ("cpu", "cuda", or "auto").

        Resolved via app.ai.utils.device.get_device(), which falls back
        to "cpu" whenever CUDA/torch is unavailable — safe to call even
        before a model is loaded (the resolved device is just recorded).
        """
        self._device = get_device(device)
        if self._net is not None:
            import torch

            self._net.to(torch.device(self._device))

    def predict(self, features: TensorBatch) -> AutoencoderPrediction:
        """
        Run reconstruction-error-based anomaly detection over a
        TensorBatch produced by app.ai.preprocessing.PreprocessingPipeline.

        Args:
            features: A TensorBatch whose `.rows` is the flat, scaled/
                encoded feature matrix built by the preprocessing pipeline.

        Returns:
            AutoencoderPrediction with one prediction/confidence pair per
            row of `features.rows`.
        """
        if self._net is None:
            raise InferenceError(
                "AutoencoderModel.predict() called before load_weights(). "
                "Load a trained model first."
            )
        if not isinstance(features, TensorBatch):
            raise InferenceError(
                f"AutoencoderModel.predict() expects a TensorBatch, got {type(features).__name__}."
            )

        if not features.rows:
            return AutoencoderPrediction(prediction=[], confidence=[], metadata=self._metadata(n_samples=0))

        if len(features.rows[0]) != self._input_dim:
            raise InferenceError(
                f"AutoencoderModel expects {self._input_dim} input features per row, "
                f"got {len(features.rows[0])}."
            )

        try:
            import torch
        except ImportError as exc:
            raise InferenceError("PyTorch is not installed; cannot run AutoencoderModel.predict().") from exc

        try:
            torch_device = torch.device(self._device)
            # The model is already on `torch_device` — load_weights()/
            # to_device() are the only two places self._net's device is
            # ever changed, and both keep it in sync with self._device —
            # so predict() does not re-issue a `.to(device)` on the model
            # every call. Only the input tensor needs to move here, and
            # it moves once, as a single batched transfer (never per-row).
            # inference_mode() is used instead of no_grad(): both skip
            # gradient tracking, but inference_mode() also skips the
            # extra autograd version-counter bookkeeping no_grad() still
            # does, which matters on a hot inference path called for
            # every SentinelX analysis.
            with torch.inference_mode():
                x = torch.tensor(features.rows, dtype=torch.float32, device=torch_device)
                reconstruction = self._net(x)
                errors = torch.mean((reconstruction - x) ** 2, dim=1)
                error_values = errors.detach().to("cpu").tolist()
        except Exception as exc:
            raise InferenceError(f"Autoencoder inference failed: {exc}") from exc

        prediction = [1 if err > self._threshold else 0 for err in error_values]
        confidence = [self._to_confidence(err, self._threshold) for err in error_values]

        return AutoencoderPrediction(
            prediction=prediction,
            confidence=confidence,
            metadata=self._metadata(n_samples=len(features.rows), feature_names=features.feature_names),
        )

    # ── internals ────────────────────────────────────────────────────

    @staticmethod
    def _to_confidence(error: float, threshold: float) -> float:
        """
        Map a reconstruction error (>= 0, higher = more anomalous) to a
        [0, 1] confidence relative to `threshold`: error==0 -> 0.0,
        error==threshold -> 0.5, error>=2*threshold -> 1.0 (capped). Plain
        arithmetic — no numpy/torch needed for this scalar mapping.
        """
        if threshold <= 0:
            return 1.0 if error > 0 else 0.0
        ratio = error / (2.0 * threshold)
        return max(0.0, min(1.0, ratio))

    def _metadata(self, n_samples: int, feature_names: list[str] | None = None) -> dict[str, Any]:
        return {
            "model": MODEL_NAME,
            "device": self._device,
            "weights_path": self._weights_path,
            "n_samples": n_samples,
            "feature_names": feature_names or [],
            "input_dim": self._input_dim,
            "reconstruction_error_threshold": self._threshold,
            "cuda_available": is_cuda_available(),
        }

    @staticmethod
    def _validate_checkpoint(checkpoint: Any) -> None:
        if not isinstance(checkpoint, dict):
            raise ModelLoadError(
                "Autoencoder checkpoint must be a dict with at least 'state_dict' and "
                "'input_dim' keys (see AutoencoderModel.load_weights docstring)."
            )
        missing = [k for k in ("state_dict", "input_dim") if k not in checkpoint]
        if missing:
            raise ModelLoadError(f"Autoencoder checkpoint missing required keys: {missing}")
