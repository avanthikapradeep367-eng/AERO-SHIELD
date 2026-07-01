"""
app/ai/models/model_manager.py — Lifecycle management for SentinelX model
instances.

Where models/registry.py answers "what model *types* are available"
(register_model/get_model/list_models, keyed by class), ModelManager
answers "which model *instances* are currently loaded" — it owns the
load/unload lifecycle and hands out already-instantiated models to
callers (the future InferenceEngine) by name.

Does NOT implement training or inference: it only constructs a
registered BaseModel subclass, calls load_weights()/to_device() on it,
and tracks the resulting instance. Actual prediction happens in
app.ai.inference.InferenceEngine; actual weight-loading logic lives
inside each concrete BaseModel subclass — this file only orchestrates.

torch is never imported here, directly or indirectly, at module import
time: BaseModel.load_weights()/to_device() are where a concrete subclass
would call into torch, and that only happens when a caller explicitly
calls ModelManager.load(), never as a side effect of importing this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.exceptions import ModelLoadError

from .base import BaseModel
from .registry import get_model, list_models


@dataclass
class LoadedModel:
    """A live, loaded model instance plus the metadata needed to manage it."""

    name: str
    version: str
    device: str
    weights_path: str | None
    instance: BaseModel


class ModelManager:
    """
    Owns the load/unload lifecycle for model instances built from the
    class-level registry in app.ai.models.registry.

    Usage:
        manager = ModelManager()
        manager.load("gps_spoofing_detector", weights_path="...", device="cpu")
        model = manager.get("gps_spoofing_detector")
        manager.unload("gps_spoofing_detector")
    """

    def __init__(self) -> None:
        self._loaded: dict[str, LoadedModel] = {}

    # ── registry passthrough ────────────────────────────────────────

    def available_models(self) -> list[str]:
        """Model type names registered via @register_model, regardless of load state."""
        return list_models()

    def is_registered(self, name: str) -> bool:
        return name in list_models()

    # ── lifecycle ────────────────────────────────────────────────────

    def load(
        self,
        name: str,
        weights_path: str | None = None,
        device: str = "cpu",
        version: str = "latest",
        force_reload: bool = False,
    ) -> LoadedModel:
        """
        Instantiate a registered model class, load its weights, move it to
        `device`, and track it under `name` for later retrieval.

        Args:
            name: Model type name, as registered via @register_model in registry.py.
            weights_path: Passed through to BaseModel.load_weights(). May be
                None for a model that initializes its own weights.
            device: Passed through to BaseModel.to_device().
            version: Free-form version tag, stored alongside the instance.
            force_reload: If True, reload even if `name` is already loaded.
                If False (default) and `name` is already loaded, the
                existing LoadedModel is returned unchanged.

        Raises:
            ModelLoadError: If `name` is not registered, or if
                load_weights()/to_device() raises.
        """
        if not force_reload and name in self._loaded:
            return self._loaded[name]

        if not self.is_registered(name):
            raise ModelLoadError(
                f"No model registered under '{name}'.",
                details={"available_models": self.available_models()},
            )

        model_cls = get_model(name)
        instance = model_cls()

        try:
            if weights_path is not None:
                instance.load_weights(weights_path)
            instance.to_device(device)
        except Exception as exc:
            raise ModelLoadError(
                f"Failed to load model '{name}': {exc}",
                details={"name": name, "weights_path": weights_path, "device": device},
            ) from exc

        loaded = LoadedModel(
            name=name, version=version, device=device, weights_path=weights_path, instance=instance
        )
        self._loaded[name] = loaded
        return loaded

    def unload(self, name: str) -> bool:
        """Drop a loaded model instance. Returns True if something was unloaded."""
        return self._loaded.pop(name, None) is not None

    def unload_all(self) -> None:
        """Drop every currently loaded model instance."""
        self._loaded.clear()

    # ── retrieval ────────────────────────────────────────────────────

    def get(self, name: str) -> BaseModel:
        """Return the loaded model instance for `name`. Raises ModelLoadError if not loaded."""
        return self.get_loaded(name).instance

    def get_loaded(self, name: str) -> LoadedModel:
        """Return the LoadedModel (instance + metadata) for `name`."""
        try:
            return self._loaded[name]
        except KeyError as exc:
            raise ModelLoadError(
                f"Model '{name}' is not currently loaded.",
                details={"loaded_models": self.loaded_models()},
            ) from exc

    def is_loaded(self, name: str) -> bool:
        return name in self._loaded

    def loaded_models(self) -> list[str]:
        """Names of currently loaded model instances (subset of available_models())."""
        return sorted(self._loaded)
