"""
app/ai/preprocessing/exceptions.py — Preprocessing-layer exceptions.

Subclasses the shared app.ai.exceptions.AIBaseError hierarchy (unmodified)
so callers can catch either the specific PreprocessingError or the
broader AIBaseError. Kept local to this package rather than added to
app/ai/exceptions.py, to keep this change scoped to app/ai/preprocessing/.
"""

from __future__ import annotations

from app.ai.exceptions import AIBaseError


class PreprocessingError(AIBaseError):
    """Raised for feature-extraction/validation/encoding/scaling failures."""


class PipelineNotFittedError(PreprocessingError):
    """Raised when transform()/transform_single() is called before fit()."""
