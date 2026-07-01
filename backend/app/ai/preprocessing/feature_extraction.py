"""
app/ai/preprocessing/feature_extraction.py — AttackEventRecord -> FeatureVector.

Converts a validated AttackEventRecord (app.ai.datasets.schema) into a
flat, framework-agnostic FeatureVector: named numeric fields plus named
categorical fields, decoupled from any particular encoding/scaling choice
so those concerns stay in their own modules (categorical_encoding.py,
numerical_scaling.py).

Label leakage note
-------------------
`severity_hint` on AttackEventRecord is deliberately EXCLUDED from the
numeric feature set. Looking at app/ai/datasets/generator.py, severity_hint
is assigned a value *because* the generator already knows the event_type
(e.g. DOS -> 80-98, NORMAL -> 0.0) — it is a proxy for the label, not an
independently observable signal. Feeding it to a model would let the model
trivially reconstruct event_type/is_attack instead of learning from actual
traffic/auth behavior, so it is kept out of NUMERIC_COLUMNS entirely.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from app.ai.datasets.schema import AttackEventRecord

_IP_HASH_BUCKETS = 256

NUMERIC_COLUMNS: list[str] = [
    "request_rate_hz",
    "payload_size_bytes",
    "session_duration_ms",
    "packet_loss_ratio",
    "signal_strength_dbm",
    "signal_strength_missing",
    "rolling_key_version",
    "rolling_key_valid_flag",
    "auth_success_flag",
    "source_port",
    "destination_port",
    "source_ip_hash_bucket",
]

CATEGORICAL_COLUMNS: list[str] = ["device_type", "protocol"]


def _ip_hash_bucket(ip: str, buckets: int = _IP_HASH_BUCKETS) -> int:
    """
    Stable numeric bucket for an IP string, consistent across processes/runs.

    Uses sha256 rather than Python's built-in hash(), which is randomly
    salted per interpreter invocation (PYTHONHASHSEED) and would silently
    break determinism between two runs of the same pipeline.
    """
    digest = hashlib.sha256(ip.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % buckets


@dataclass(frozen=True)
class FeatureVector:
    """Intermediate, framework-agnostic representation of one record's features."""

    event_id: str
    device_id: str
    timestamp: datetime
    numeric: dict[str, float]
    categorical: dict[str, str]
    label_event_type: str
    label_is_attack: bool


def extract_features(record: AttackEventRecord) -> FeatureVector:
    """Convert one AttackEventRecord into a FeatureVector of model-ready fields."""
    numeric = {
        "request_rate_hz": float(record.request_rate_hz),
        "payload_size_bytes": float(record.payload_size_bytes),
        "session_duration_ms": float(record.session_duration_ms),
        "packet_loss_ratio": float(record.packet_loss_ratio),
        "signal_strength_dbm": (
            float(record.signal_strength_dbm) if record.signal_strength_dbm is not None else 0.0
        ),
        "signal_strength_missing": 0.0 if record.signal_strength_dbm is not None else 1.0,
        "rolling_key_version": float(record.rolling_key_version),
        "rolling_key_valid_flag": 1.0 if record.rolling_key_valid else 0.0,
        "auth_success_flag": 1.0 if record.auth_success else 0.0,
        "source_port": float(record.source_port),
        "destination_port": float(record.destination_port),
        "source_ip_hash_bucket": float(_ip_hash_bucket(record.source_ip)),
    }
    categorical = {
        "device_type": record.device_type.value,
        "protocol": record.protocol.value,
    }
    return FeatureVector(
        event_id=record.event_id,
        device_id=record.device_id,
        timestamp=record.timestamp,
        numeric=numeric,
        categorical=categorical,
        label_event_type=record.event_type.value,
        label_is_attack=record.is_attack,
    )


def extract_batch(records: list[AttackEventRecord]) -> list[FeatureVector]:
    """Extract features for a batch of records, preserving input order."""
    return [extract_features(r) for r in records]
