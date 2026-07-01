"""
app/ai/exceptions.py — SentinelX AI internal exception hierarchy.

Domain-level exceptions raised inside the app/ai package (datasets, models,
inference, sentinelx). These are plain Python exceptions, NOT FastAPI
HTTPExceptions — the HTTP-boundary exceptions used by routes/services live
in app/exceptions/ai.py and are unaffected by this module.

When app/services/ai_service.py is wired to call into this package, it is
responsible for catching these and translating them into the appropriate
app.exceptions.ai.AIServiceError subclass.
"""

from __future__ import annotations


class AIBaseError(Exception):
    """Root exception for all app.ai package errors."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | details={self.details}"
        return self.message


class DatasetError(AIBaseError):
    """Raised for dataset loading/validation failures."""


class ModelLoadError(AIBaseError):
    """Raised when model weights cannot be located or loaded."""


class InferenceError(AIBaseError):
    """Raised when a forward pass / prediction fails."""


class CUDAUnavailableError(AIBaseError):
    """Raised when CUDA is required but no GPU device is available."""
