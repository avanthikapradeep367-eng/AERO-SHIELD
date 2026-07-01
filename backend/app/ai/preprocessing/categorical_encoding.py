"""
app/ai/preprocessing/categorical_encoding.py — Deterministic categorical
encoding for closed-set fields (device_type, protocol).

Unlike a typical sklearn-style LabelEncoder, the vocabulary here is NOT
fit from data — it's built directly from the AttackEventRecord schema's
Enum definitions (app.ai.datasets.schema.DeviceType / Protocol). Those
enums are a closed, already-validated set, so basing the encoding on them
(rather than "whatever values happen to appear in this batch") guarantees
the same encoding regardless of which records are passed in, and that a
value never seen during "training" is a real error, not just missing from
one particular batch.
"""

from __future__ import annotations

from enum import Enum


class CategoricalEncoder:
    """Fixed-vocabulary encoder: string category -> integer index / one-hot vector."""

    def __init__(self, values: list[str]) -> None:
        if len(set(values)) != len(values):
            raise ValueError("CategoricalEncoder values must be unique")
        self._values: list[str] = list(values)
        self._index: dict[str, int] = {v: i for i, v in enumerate(self._values)}

    @classmethod
    def from_enum(cls, enum_cls: type[Enum]) -> "CategoricalEncoder":
        """Build an encoder whose vocabulary is exactly `enum_cls`'s members, in definition order."""
        return cls([member.value for member in enum_cls])

    @property
    def values(self) -> list[str]:
        return list(self._values)

    @property
    def size(self) -> int:
        return len(self._values)

    def encode_index(self, value: str) -> int:
        try:
            return self._index[value]
        except KeyError as exc:
            raise ValueError(f"Unknown category '{value}'. Expected one of {self._values}") from exc

    def encode_one_hot(self, value: str) -> list[float]:
        idx = self.encode_index(value)
        row = [0.0] * self.size
        row[idx] = 1.0
        return row

    def decode_index(self, index: int) -> str:
        return self._values[index]

    def column_names(self, prefix: str) -> list[str]:
        """Human-readable one-hot column names, e.g. 'device_type__UAV'."""
        return [f"{prefix}__{v}" for v in self._values]

    def to_dict(self) -> dict:
        return {"values": list(self._values)}

    @classmethod
    def from_dict(cls, d: dict) -> "CategoricalEncoder":
        return cls(list(d["values"]))
