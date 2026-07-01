"""
app/ai/preprocessing/numerical_scaling.py — Deterministic per-column
numeric scaling (standardization or min-max), fit once and reused unchanged
thereafter.

No sklearn/numpy dependency — this project has not declared any ML
libraries yet (see backend/requirements.txt), so scaling is implemented
with plain Python/stdlib `math` only, operating on lists of per-column
dicts.

The critical property for a future inference service: fit() computes
statistics from a training batch; transform() applies those *exact same*
statistics to any later batch (including a single live record) without
recomputing them. to_dict()/from_dict() let a fitted scaler be persisted
alongside model weights so inference-time transforms exactly match what
the model was trained on.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class _ColumnStats:
    kind: str  # "standard" | "minmax"
    mean: float = 0.0
    std: float = 1.0
    min_val: float = 0.0
    max_val: float = 1.0

    def transform(self, x: float) -> float:
        if self.kind == "standard":
            if self.std == 0:
                return 0.0
            return (x - self.mean) / self.std
        span = self.max_val - self.min_val
        if span == 0:
            return 0.0
        return (x - self.min_val) / span

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "mean": self.mean,
            "std": self.std,
            "min_val": self.min_val,
            "max_val": self.max_val,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "_ColumnStats":
        return cls(**d)


class FeatureScaler:
    """Fit-once, transform-many per-column numeric scaler."""

    def __init__(self, kind: str = "standard") -> None:
        if kind not in ("standard", "minmax"):
            raise ValueError("kind must be 'standard' or 'minmax'")
        self._kind = kind
        self._columns: list[str] = []
        self._stats: dict[str, _ColumnStats] = {}
        self._fitted = False

    @property
    def fitted(self) -> bool:
        return self._fitted

    def fit(self, rows: list[dict[str, float]], columns: list[str]) -> "FeatureScaler":
        self._columns = list(columns)
        stats: dict[str, _ColumnStats] = {}
        for col in self._columns:
            values = [r[col] for r in rows]
            if not values:
                stats[col] = _ColumnStats(kind=self._kind)
                continue
            mean = sum(values) / len(values)
            variance = sum((v - mean) ** 2 for v in values) / len(values)
            std = math.sqrt(variance)
            stats[col] = _ColumnStats(
                kind=self._kind, mean=mean, std=std, min_val=min(values), max_val=max(values)
            )
        self._stats = stats
        self._fitted = True
        return self

    def transform(self, rows: list[dict[str, float]]) -> list[dict[str, float]]:
        if not self._fitted:
            raise RuntimeError("FeatureScaler.fit() must be called before transform().")
        return [{col: self._stats[col].transform(r[col]) for col in self._columns} for r in rows]

    def fit_transform(self, rows: list[dict[str, float]], columns: list[str]) -> list[dict[str, float]]:
        self.fit(rows, columns)
        return self.transform(rows)

    def to_dict(self) -> dict:
        if not self._fitted:
            raise RuntimeError("Cannot serialize an unfitted FeatureScaler.")
        return {
            "kind": self._kind,
            "columns": list(self._columns),
            "stats": {k: v.to_dict() for k, v in self._stats.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FeatureScaler":
        scaler = cls(kind=d["kind"])
        scaler._columns = list(d["columns"])
        scaler._stats = {k: _ColumnStats.from_dict(v) for k, v in d["stats"].items()}
        scaler._fitted = True
        return scaler
