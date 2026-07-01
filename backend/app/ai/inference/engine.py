"""
app/ai/inference/engine.py — InferenceEngine: orchestrates the complete
prediction pipeline for one model.

    AttackEventRecord(s) / BaseDataset
        -> PreprocessingPipeline.transform()   (already fitted, never refit here)
        -> TensorBatch
        -> ModelManager.get(model_name)        (already loaded, never loaded implicitly here)
        -> BaseModel.predict(TensorBatch)
        -> InferenceResult

This module only orchestrates — it does not fit the preprocessing
pipeline, does not load model weights implicitly, does not implement
SentinelX risk-scoring/response logic, and does not integrate with
AIService. Those are separate concerns owned elsewhere:
  - Fitting/persisting a PreprocessingPipeline is a training-time concern.
  - Loading model weights is ModelManager's job (called explicitly via
    InferenceEngine.load_model(), which is a thin passthrough).
  - Translating an InferenceResult into SentinelX's risk_score/
    threat_detected/attack_labels vocabulary belongs to a future
    SentinelXEngine (see the module docstring in
    app/ai/sentinelx/engine.py) — that mapping is intentionally NOT
    implemented here.

Model-agnostic by contract, not by type-checking: BaseModel.predict()
returns `Any` (see app/ai/models/base.py), so this engine does not import
or special-case IsolationForestModel. Instead it requires — at runtime,
via duck typing — that whatever a model's predict() returns exposes
`.prediction`, `.confidence`, and `.metadata` attributes. IsolationForestModel
already returns exactly that shape (IsolationForestPrediction); a future
AutoencoderModel (or anything else) only needs to match the same shape to
work here without any change to this file.

No ML dependency (torch, sklearn, ...) is imported anywhere in this
module, directly or indirectly at import time — model_manager.load()
is what triggers a concrete model's own lazy import, and that only
happens when a caller explicitly calls InferenceEngine.load_model().
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.ai.datasets.base import BaseDataset
from app.ai.datasets.schema import AttackEventRecord
from app.ai.exceptions import InferenceError
from app.ai.models.model_manager import LoadedModel, ModelManager
from app.ai.preprocessing.pipeline import PreprocessingPipeline, records_from_dataset


@dataclass
class ExecutionInfo:
    """Runtime/execution details for one InferenceEngine.predict*() call."""

    model_name: str
    device: str
    n_samples: int
    duration_ms: float
    timestamp: str  # ISO-8601 UTC
    single_event: bool


@dataclass
class InferenceResult:
    """Structured inference output: one row per input record, in input order."""

    event_ids: list[str]
    prediction: list[int]
    confidence: list[float]
    preprocessing_metadata: dict[str, Any]
    model_metadata: dict[str, Any]
    execution: ExecutionInfo

    @property
    def n_samples(self) -> int:
        return len(self.prediction)

    def single(self) -> tuple[int, float]:
        """Convenience accessor for a single-event result: (prediction, confidence)."""
        if self.n_samples != 1:
            raise InferenceError(f"single() requires exactly 1 sample, got {self.n_samples}.")
        return self.prediction[0], self.confidence[0]


class InferenceEngine:
    """
    Runs the complete preprocess -> predict pipeline for one named model.

    Requires a *fitted* PreprocessingPipeline (fit during training/offline,
    then persisted via to_dict()/from_dict() — see pipeline.py) and uses
    ModelManager for model lifecycle, rather than reimplementing either.

    Usage:
        pipeline = PreprocessingPipeline.from_dict(persisted_pipeline_state)
        engine = InferenceEngine(model_name="isolation_forest", pipeline=pipeline)
        engine.load_model(weights_path="isolation_forest.joblib", device="cpu")

        result = engine.predict(some_attack_event_record)      # single event
        result = engine.predict([record_a, record_b])          # batch of records
        result = engine.predict(attack_log_dataset)             # any BaseDataset
    """

    def __init__(
        self,
        model_name: str,
        pipeline: PreprocessingPipeline,
        model_manager: ModelManager | None = None,
    ) -> None:
        if not isinstance(pipeline, PreprocessingPipeline):
            raise InferenceError(
                f"InferenceEngine requires a PreprocessingPipeline, got {type(pipeline).__name__}."
            )
        if not pipeline.fitted:
            raise InferenceError(
                "InferenceEngine requires a fitted PreprocessingPipeline "
                "(call pipeline.fit(...) or PreprocessingPipeline.from_dict(...) first)."
            )
        self._model_name = model_name
        self._pipeline = pipeline
        self._manager = model_manager or ModelManager()

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_manager(self) -> ModelManager:
        return self._manager

    def is_model_loaded(self) -> bool:
        return self._manager.is_loaded(self._model_name)

    def load_model(
        self,
        weights_path: str | None = None,
        device: str = "cpu",
        force_reload: bool = False,
    ) -> LoadedModel:
        """
        Thin passthrough to ModelManager.load(), scoped to this engine's
        model_name. Only place in this module where a model's own
        (possibly ML-library-importing) load_weights()/to_device() runs.
        """
        return self._manager.load(
            self._model_name, weights_path=weights_path, device=device, force_reload=force_reload
        )

    # ── public prediction API ───────────────────────────────────────

    def predict(
        self, input_data: AttackEventRecord | list[AttackEventRecord] | BaseDataset
    ) -> InferenceResult:
        """
        Single entry point accepting any supported input shape:
        one AttackEventRecord, a list of them, or any BaseDataset
        (e.g. AttackLogDataset).
        """
        if isinstance(input_data, BaseDataset):
            return self.predict_dataset(input_data)
        if isinstance(input_data, AttackEventRecord):
            return self.predict_event(input_data)
        if isinstance(input_data, list):
            return self.predict_records(input_data)
        raise InferenceError(
            "InferenceEngine.predict() does not support input of type "
            f"{type(input_data).__name__}. Expected AttackEventRecord, "
            "list[AttackEventRecord], or BaseDataset."
        )

    def predict_event(self, record: AttackEventRecord) -> InferenceResult:
        """
        Single-event inference.

        NOTE: rolling-key features are device-history-aware (see
        app/ai/preprocessing/rolling_key_features.py). A lone event has no
        history, so key_version_delta/key_version_reused/
        consecutive_invalid_key_count reflect a "first-ever event"
        baseline rather than real history. Callers that need meaningful
        rolling-key signal at serving time should use predict_records()
        with the device's recent event window instead.
        """
        return self._run([record], single_event=True)

    def predict_records(self, records: list[AttackEventRecord]) -> InferenceResult:
        """Batch inference over an explicit list of AttackEventRecord."""
        return self._run(list(records), single_event=False)

    def predict_dataset(self, dataset: BaseDataset) -> InferenceResult:
        """
        Batch inference over any BaseDataset (e.g. AttackLogDataset).

        The caller is responsible for calling dataset.load() first — this
        mirrors app.ai.preprocessing.pipeline.records_from_dataset(), which
        materializes records via the dataset's __len__/__getitem__ contract
        without forcing a load as a side effect.
        """
        records = records_from_dataset(dataset)
        return self._run(records, single_event=False)

    # ── internals ────────────────────────────────────────────────────

    def _run(self, records: list[AttackEventRecord], single_event: bool) -> InferenceResult:
        if not records:
            raise InferenceError(
                "InferenceEngine received an empty batch of records. "
                "If this came from a dataset, confirm dataset.load() was called first."
            )

        start = time.perf_counter()

        batch = self._pipeline.transform(records)
        model = self._manager.get(self._model_name)  # raises ModelLoadError if not loaded
        raw = model.predict(batch)
        self._validate_prediction_contract(raw, expected_n=batch.shape[0])

        duration_ms = (time.perf_counter() - start) * 1000
        device = self._manager.get_loaded(self._model_name).device

        return InferenceResult(
            event_ids=[r.event_id for r in records],
            prediction=list(raw.prediction),
            confidence=list(raw.confidence),
            preprocessing_metadata={
                "feature_names": batch.feature_names,
                "n_features": len(batch.feature_names),
                "n_samples": batch.shape[0],
                "ground_truth_labels": batch.label_names,
            },
            model_metadata=dict(raw.metadata),
            execution=ExecutionInfo(
                model_name=self._model_name,
                device=device,
                n_samples=len(records),
                duration_ms=round(duration_ms, 3),
                timestamp=datetime.now(timezone.utc).isoformat(),
                single_event=single_event,
            ),
        )

    def _validate_prediction_contract(self, raw: Any, expected_n: int) -> None:
        """
        Enforce the model-agnostic output contract at runtime, since
        BaseModel.predict() is typed `Any` and this engine deliberately
        never imports a concrete model class to check against.
        """
        missing = [attr for attr in ("prediction", "confidence", "metadata") if not hasattr(raw, attr)]
        if missing:
            raise InferenceError(
                f"Model '{self._model_name}'.predict() returned an object missing "
                f"required attributes: {missing}. Every BaseModel.predict() must return "
                "an object exposing .prediction, .confidence, and .metadata "
                "(see IsolationForestPrediction for the reference shape).",
            )
        if len(raw.prediction) != expected_n or len(raw.confidence) != expected_n:
            raise InferenceError(
                f"Model '{self._model_name}'.predict() returned {len(raw.prediction)} "
                f"predictions / {len(raw.confidence)} confidences for {expected_n} input rows.",
            )
