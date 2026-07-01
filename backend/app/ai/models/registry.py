"""
app/ai/models/registry.py — Name/version-based lookup for model classes.

Lets the inference engine request a model by string name (e.g. from
config) instead of importing every model class directly.
"""

from __future__ import annotations

from .base import BaseModel

_REGISTRY: dict[str, type[BaseModel]] = {}


def register_model(name: str):
    """Class decorator: register a BaseModel subclass under `name`."""

    def _decorator(cls: type[BaseModel]) -> type[BaseModel]:
        _REGISTRY[name] = cls
        return cls

    return _decorator


def get_model(name: str) -> type[BaseModel]:
    """Look up a registered model class by name. Raises KeyError if unknown."""
    return _REGISTRY[name]


def list_models() -> list[str]:
    """Return the names of all currently registered models."""
    return sorted(_REGISTRY)
