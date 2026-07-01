"""
app/ai/datasets/registry.py — Name-based lookup for dataset classes.

Lets inference/training code request a dataset by string name (e.g. from
config) instead of importing every dataset class directly.
"""

from __future__ import annotations

from .base import BaseDataset

_REGISTRY: dict[str, type[BaseDataset]] = {}


def register_dataset(name: str):
    """Class decorator: register a BaseDataset subclass under `name`."""

    def _decorator(cls: type[BaseDataset]) -> type[BaseDataset]:
        _REGISTRY[name] = cls
        return cls

    return _decorator


def get_dataset(name: str) -> type[BaseDataset]:
    """Look up a registered dataset class by name. Raises KeyError if unknown."""
    return _REGISTRY[name]


def list_datasets() -> list[str]:
    """Return the names of all currently registered datasets."""
    return sorted(_REGISTRY)
