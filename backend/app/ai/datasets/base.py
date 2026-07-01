"""
app/ai/datasets/base.py — Abstract base class for SentinelX datasets.

Concrete dataset loaders (e.g. network-traffic captures, GPS-spoofing
samples, attack-signature corpora) will subclass BaseDataset. Kept
framework-agnostic (no torch.utils.data.Dataset dependency) so it stays
importable before ML dependencies are added to requirements.txt.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseDataset(ABC):
    """Contract every SentinelX dataset loader must implement."""

    @abstractmethod
    def load(self) -> None:
        """Load raw data from disk/source into memory or set up lazy access."""

    @abstractmethod
    def __len__(self) -> int:
        """Return the number of samples in the dataset."""

    @abstractmethod
    def __getitem__(self, index: int) -> Any:
        """Return the sample (and label, if supervised) at `index`."""
