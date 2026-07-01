"""app/ai/models — SentinelX model wrappers (weights, architectures)."""

from .autoencoder import AutoencoderModel, AutoencoderPrediction
from .base import BaseModel
from .isolation_forest import IsolationForestModel, IsolationForestPrediction
from .model_manager import LoadedModel, ModelManager
from .registry import get_model, list_models, register_model

__all__ = [
    "BaseModel",
    "register_model",
    "get_model",
    "list_models",
    "ModelManager",
    "LoadedModel",
    "IsolationForestModel",
    "IsolationForestPrediction",
    "AutoencoderModel",
    "AutoencoderPrediction",
]
