"""
app/ai/models/isolation_forest.py — Isolation Forest anomaly-detection
model wrapper.

Concrete BaseModel implementation backed by scikit-learn's
IsolationForest. load_weights() deserializes a *pre-trained* estimator
persisted to disk — this module does not fit/train a model itself; a
separate offline training step is responsible for producing the artifact
load_weights() reads (see the "Do not implement training" constraint).

scikit-learn (and joblib) are imported lazily, inside load_weights() and
predict() only — never at module import time. Importing app.ai.models (or
this file directly) must succeed on a machine with no scikit-learn
installed, matching the lazy-import pattern already established for torch
in app/ai/utils/device.py and app/ai/preprocessing/tensor_prep.py.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from app.ai.exceptions import InferenceError, ModelLoadError
from app.ai.preprocessing.tensor_prep import TensorBatch

from .base import BaseModel
from .registry import register_model

MODEL_NAME = "isolation_forest"


@dataclass
class IsolationForestPrediction:
    """Structured prediction output, ready for the future InferenceEngine."""

    prediction: list[int]  # 1 = anomaly/attack, 0 = normal — matches TensorBatch.labels convention
    confidence: list[float]  # confidence that each sample is anomalous, in [0, 1]
    metadata: dict[str, Any]


@register_model(MODEL_NAME)
class IsolationForestModel(BaseModel):
    """
    Unsupervised anomaly-detection wrapper around sklearn.ensemble.IsolationForest.

    Lifecycle is owned externally by app.ai.models.ModelManager — this
    class never manages its own load/unload state:

        model = IsolationForestModel()
        model.load_weights("path/to/isolation_forest.joblib")
        model.to_device("cpu")
        result = model.predict(tensor_batch)  # TensorBatch from PreprocessingPipeline
    """

    def __init__(self) -> None:
        self._estimator: Any = None
        self._device: str = "cpu"
        self._weights_path: str | None = None

    def load_weights(self, path: str) -> None:
        """
        Deserialize a previously trained sklearn IsolationForest from `path`.

        No training happens here — `path` must point to an artifact
        produced by an offline training step, e.g.:
            joblib.dump(fitted_isolation_forest, path)
        """
        try:
            import joblib
        except ImportError as exc:
            raise ModelLoadError(
                "scikit-learn is not installed. Add scikit-learn to "
                "backend/requirements.txt before loading IsolationForestModel weights.",
                details={"path": path},
            ) from exc

        try:
            estimator = joblib.load(path)
        except FileNotFoundError as exc:
            raise ModelLoadError(f"Isolation Forest weights file not found: {path}") from exc
        except Exception as exc:
            raise ModelLoadError(
                f"Failed to load Isolation Forest weights from {path}: {exc}"
            ) from exc

        self._validate_estimator(estimator)
        self._estimator = estimator
        self._weights_path = path

    def to_device(self, device: str) -> None:
        """
        Record the target device.

        IsolationForest is a scikit-learn/CPU estimator — there is no GPU
        tensor to move — so any value is accepted and simply recorded, for
        forward compatibility with ModelManager's uniform device API
        across CPU-only and future CUDA-backed models.
        """
        self._device = device

    def predict(self, features: TensorBatch) -> IsolationForestPrediction:
        """
        Run anomaly detection over a TensorBatch produced by
        app.ai.preprocessing.PreprocessingPipeline.

        Args:
            features: A TensorBatch whose `.rows` is the flat, scaled/
                encoded feature matrix built by the preprocessing pipeline.

        Returns:
            IsolationForestPrediction with one prediction/confidence pair
            per row of `features.rows`.
        """
        if self._estimator is None:
            raise InferenceError(
                "IsolationForestModel.predict() called before load_weights(). "
                "Load a trained estimator first."
            )
        if not isinstance(features, TensorBatch):
            raise InferenceError(
                f"IsolationForestModel.predict() expects a TensorBatch, got {type(features).__name__}."
            )

        if not features.rows:
            return IsolationForestPrediction(
                prediction=[], confidence=[], metadata=self._metadata(n_samples=0)
            )

        try:
            raw_labels = self._estimator.predict(features.rows)  # 1 = inlier, -1 = outlier
            raw_scores = self._estimator.decision_function(features.rows)  # higher = more normal
        except Exception as exc:
            raise InferenceError(f"Isolation Forest inference failed: {exc}") from exc

        prediction = [1 if int(label) == -1 else 0 for label in raw_labels]
        confidence = [self._to_confidence(float(score)) for score in raw_scores]

        return IsolationForestPrediction(
            prediction=prediction,
            confidence=confidence,
            metadata=self._metadata(n_samples=len(features.rows), feature_names=features.feature_names),
        )

    # ── internals ────────────────────────────────────────────────────

    @staticmethod
    def _to_confidence(decision_score: float) -> float:
        """
        Map a raw IsolationForest decision_function score (higher = more
        normal, lower/negative = more anomalous) to a [0, 1] confidence
        that the sample is anomalous, via a logistic squash. Plain
        math.exp on a single float — no numpy dependency here.
        """
        anomaly_score = -decision_score
        return 1.0 / (1.0 + math.exp(-anomaly_score))

    def _metadata(self, n_samples: int, feature_names: list[str] | None = None) -> dict[str, Any]:
        return {
            "model": MODEL_NAME,
            "device": self._device,
            "weights_path": self._weights_path,
            "n_samples": n_samples,
            "feature_names": feature_names or [],
            "n_estimators": getattr(self._estimator, "n_estimators", None),
            "contamination": getattr(self._estimator, "contamination", None),
        }

    @staticmethod
    def _validate_estimator(estimator: Any) -> None:
        required = ("predict", "decision_function")
        missing = [m for m in required if not hasattr(estimator, m)]
        if missing:
            raise ModelLoadError(
                "Loaded object is not a fitted IsolationForest-like estimator; "
                f"missing methods: {missing}"
            )
