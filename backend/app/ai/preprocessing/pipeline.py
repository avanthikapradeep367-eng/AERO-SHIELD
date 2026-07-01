"""
app/ai/preprocessing/pipeline.py — PreprocessingPipeline: the single
reusable entry point that turns AttackEventRecord data into model-ready
tensors.

Stages, in order:
    1. feature_extraction   — AttackEventRecord -> FeatureVector
    2. feature_validation    — catch malformed vectors early
    3. rolling_key_features  — enrich with device-history-aware key features
    4. categorical_encoding  — one-hot encode device_type / protocol
    5. numerical_scaling     — standardize/min-max scale numeric columns
    6. tensor_prep           — flatten into TensorBatch rows

fit() computes scaler statistics once (on a training split); transform()
reuses those exact statistics unchanged — this mirrors how a real
inference service must behave: the scaler/encoder state has to be
persisted (see to_dict/from_dict) and reloaded unchanged, never refit on
live traffic.
"""

from __future__ import annotations

from app.ai.datasets.base import BaseDataset
from app.ai.datasets.schema import AttackEventRecord, DeviceType, Protocol

from .categorical_encoding import CategoricalEncoder
from .exceptions import PipelineNotFittedError, PreprocessingError
from .feature_extraction import CATEGORICAL_COLUMNS, NUMERIC_COLUMNS, extract_batch
from .feature_validation import validate_feature_batch, validate_tensor_ready
from .numerical_scaling import FeatureScaler
from .rolling_key_features import ROLLING_KEY_FEATURE_NAMES, RollingKeyFeatureEngineer
from .tensor_prep import TensorBatch, build_row


def records_from_dataset(dataset: BaseDataset) -> list[AttackEventRecord]:
    """Materialize all records from any BaseDataset via its __len__/__getitem__ contract."""
    return [dataset[i] for i in range(len(dataset))]


class PreprocessingPipeline:
    """Reusable, fit-once/transform-many preprocessing pipeline."""

    def __init__(self, scaler_kind: str = "standard") -> None:
        self._categorical_encoders: dict[str, CategoricalEncoder] = {
            "device_type": CategoricalEncoder.from_enum(DeviceType),
            "protocol": CategoricalEncoder.from_enum(Protocol),
        }
        self._numeric_columns: list[str] = list(NUMERIC_COLUMNS) + list(ROLLING_KEY_FEATURE_NAMES)
        self._rolling_key_engineer = RollingKeyFeatureEngineer()
        self._scaler = FeatureScaler(kind=scaler_kind)
        self._fitted = False

    @property
    def fitted(self) -> bool:
        return self._fitted

    def feature_names(self) -> list[str]:
        """Column names in the exact order tensor rows are built (numeric, then one-hot categoricals)."""
        names = list(self._numeric_columns)
        for col in CATEGORICAL_COLUMNS:
            names.extend(self._categorical_encoders[col].column_names(col))
        return names

    def _prepare(self, records: list[AttackEventRecord]):
        vectors = extract_batch(records)
        report = validate_feature_batch(vectors)
        if not report.is_valid:
            raise PreprocessingError(
                "Feature extraction produced invalid vectors.",
                details={
                    "issues": report.issues[:10],
                    "duplicate_event_ids": report.duplicate_event_ids[:10],
                },
            )
        return self._rolling_key_engineer.transform(vectors)

    def fit(self, records: list[AttackEventRecord]) -> "PreprocessingPipeline":
        if not records:
            raise PreprocessingError("Cannot fit PreprocessingPipeline on an empty record list.")
        vectors = self._prepare(records)
        self._scaler.fit([v.numeric for v in vectors], columns=self._numeric_columns)
        self._fitted = True
        return self

    def transform(self, records: list[AttackEventRecord]) -> TensorBatch:
        if not self._fitted:
            raise PipelineNotFittedError("PreprocessingPipeline.fit() must be called before transform().")
        if not records:
            return TensorBatch(rows=[], feature_names=self.feature_names(), labels=[], label_names=[])

        vectors = self._prepare(records)
        scaled = self._scaler.transform([v.numeric for v in vectors])

        rows = [
            build_row(
                scaled[i],
                vectors[i].categorical,
                self._numeric_columns,
                CATEGORICAL_COLUMNS,
                self._categorical_encoders,
            )
            for i in range(len(vectors))
        ]

        issues = validate_tensor_ready(rows, expected_width=len(self.feature_names()))
        if issues:
            raise PreprocessingError("Tensor-ready validation failed.", details={"issues": issues[:10]})

        return TensorBatch(
            rows=rows,
            feature_names=self.feature_names(),
            labels=[1 if v.label_is_attack else 0 for v in vectors],
            label_names=[v.label_event_type for v in vectors],
        )

    def fit_transform(self, records: list[AttackEventRecord]) -> TensorBatch:
        self.fit(records)
        return self.transform(records)

    def transform_single(self, record: AttackEventRecord) -> TensorBatch:
        """
        Transform exactly one record.

        NOTE: rolling-key features are device-history-aware (see
        rolling_key_features.py). A lone record has no history, so
        key_version_delta/key_version_reused/consecutive_invalid_key_count
        will reflect a "first-ever event" baseline rather than real
        history. A future InferenceEngine that wants meaningful rolling-key
        signal at serving time must call transform() with the device's
        recent event window, not transform_single() with only the newest
        event — see the module docstring in rolling_key_features.py.
        """
        return self.transform([record])

    # ── persistence ──────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Serialize fitted state (scaler stats + encoder vocab) to a JSON-able dict."""
        if not self._fitted:
            raise PipelineNotFittedError("Cannot serialize an unfitted PreprocessingPipeline.")
        return {
            "scaler": self._scaler.to_dict(),
            "categorical_encoders": {k: v.to_dict() for k, v in self._categorical_encoders.items()},
            "numeric_columns": list(self._numeric_columns),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PreprocessingPipeline":
        """Reconstruct a previously fitted pipeline exactly, for reuse at inference time."""
        pipeline = cls(scaler_kind=d["scaler"]["kind"])
        pipeline._scaler = FeatureScaler.from_dict(d["scaler"])
        pipeline._categorical_encoders = {
            k: CategoricalEncoder.from_dict(v) for k, v in d["categorical_encoders"].items()
        }
        pipeline._numeric_columns = list(d["numeric_columns"])
        pipeline._fitted = True
        return pipeline
