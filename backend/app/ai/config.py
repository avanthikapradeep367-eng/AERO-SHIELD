"""
app/ai/config.py — SentinelX AI configuration.

Loads and validates environment variables for the CUDA/PyTorch inference
layer. Mirrors the pattern used by app/blockchain/config.py: an immutable
dataclass produced by load_config(), read once and shared across the
package.

Optional env vars (all have sensible CPU-safe defaults so the package
imports cleanly even before any ML dependencies are installed):
    AI_MODEL_DIR             — directory containing trained model weights
    AI_DEVICE                — "cuda" | "cpu" | "auto" (default "auto")
    AI_BATCH_SIZE             — inference batch size (default 1)
    AI_CONFIDENCE_THRESHOLD   — risk score above which threat_detected=True (default 70.0)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_THIS_DIR = Path(__file__).parent


@dataclass(frozen=True)
class AIConfig:
    """Immutable configuration snapshot used by all app.ai modules."""

    model_dir: Path
    device: str
    batch_size: int
    confidence_threshold: float


def load_config() -> AIConfig:
    """
    Load AI configuration from environment variables.

    Every field has a safe default, so this never raises — unlike
    app.blockchain.config.load_config(), the AI layer has no required
    external resources yet and must not block application startup.
    """
    model_dir = Path(os.getenv("AI_MODEL_DIR", str(_THIS_DIR / "models" / "weights")))
    device = os.getenv("AI_DEVICE", "auto").strip().lower()
    batch_size = int(os.getenv("AI_BATCH_SIZE", "1"))
    confidence_threshold = float(os.getenv("AI_CONFIDENCE_THRESHOLD", "70.0"))

    return AIConfig(
        model_dir=model_dir,
        device=device,
        batch_size=batch_size,
        confidence_threshold=confidence_threshold,
    )
