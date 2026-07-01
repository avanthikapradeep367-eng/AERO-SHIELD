"""
app/ai/preprocessing/tensor_prep.py — Final flat, framework-agnostic
"tensor-ready" representation.

Produces plain Python lists (not torch.Tensor — torch is not yet a
declared dependency; see app/ai/utils/device.py for the same lazy-import
pattern) so this module stays importable everywhere. TensorBatch.to_torch()
converts on demand when torch is available.
"""

from __future__ import annotations

from dataclasses import dataclass

from .categorical_encoding import CategoricalEncoder


def build_row(
    numeric: dict[str, float],
    categorical: dict[str, str],
    numeric_columns: list[str],
    categorical_columns: list[str],
    categorical_encoders: dict[str, CategoricalEncoder],
) -> list[float]:
    """
    Concatenate scaled numeric values (in fixed column order) with one-hot
    encoded categorical values (in fixed column order) into a single row.
    """
    row: list[float] = [numeric[col] for col in numeric_columns]
    for col in categorical_columns:
        row.extend(categorical_encoders[col].encode_one_hot(categorical[col]))
    return row


@dataclass
class TensorBatch:
    """Model-input-ready batch: a rectangular matrix plus column names and labels."""

    rows: list[list[float]]
    feature_names: list[str]
    labels: list[int]
    label_names: list[str]

    @property
    def shape(self) -> tuple[int, int]:
        return (len(self.rows), len(self.feature_names))

    def to_torch(self, device: str = "cpu"):
        """
        Convert to a torch.Tensor pair (features, labels) on demand.

        Lazily imports torch so this module — and the whole preprocessing
        package — stays importable before torch is added to requirements.txt.
        """
        try:
            import torch
        except ImportError as exc:
            raise ImportError(
                "torch is not installed. Add it to backend/requirements.txt "
                "before calling TensorBatch.to_torch()."
            ) from exc
        features = torch.tensor(self.rows, dtype=torch.float32, device=device)
        labels = torch.tensor(self.labels, dtype=torch.long, device=device)
        return features, labels
