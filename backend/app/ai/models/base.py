"""
app/ai/models/base.py — Abstract base class for SentinelX model wrappers.

Concrete model classes (e.g. a GPS-spoofing classifier, a DDoS detector)
subclass BaseModel. Kept framework-agnostic so it stays importable before
torch/onnxruntime are added to requirements.txt — `to_device` and
`predict` are where a real implementation would call into torch.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseModel(ABC):
    """Contract every SentinelX model wrapper must implement."""

    @abstractmethod
    def load_weights(self, path: str) -> None:
        """Load trained weights from `path` into the model."""

    @abstractmethod
    def to_device(self, device: str) -> None:
        """Move the model onto the given compute device ("cuda" or "cpu")."""

    @abstractmethod
    def predict(self, features: Any) -> Any:
        """Run a forward pass and return raw model output."""
