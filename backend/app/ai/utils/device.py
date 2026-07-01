"""
app/ai/utils/device.py — CUDA / device detection helpers.

Torch is not yet a declared dependency of this project (see
backend/requirements.txt). These helpers import torch lazily so the
app.ai package remains importable on machines without it installed —
callers get an honest "cuda_available=False" instead of an ImportError.
"""

from __future__ import annotations


def is_cuda_available() -> bool:
    """Return True if PyTorch is installed and reports a usable CUDA device."""
    try:
        import torch
    except ImportError:
        return False
    return torch.cuda.is_available()


def get_device(preferred: str = "auto") -> str:
    """
    Resolve the compute device to use for inference.

    Args:
        preferred: "cuda", "cpu", or "auto" (default). "auto" selects
                   "cuda" when available, otherwise falls back to "cpu".

    Returns:
        "cuda" or "cpu". Never raises — safe to call before torch is installed.
    """
    preferred = preferred.lower()
    if preferred == "cpu":
        return "cpu"
    return "cuda" if is_cuda_available() else "cpu"


def device_summary() -> dict:
    """Return a diagnostic dict describing current GPU/CPU availability."""
    cuda = is_cuda_available()
    summary: dict = {"cuda_available": cuda, "device": "cuda" if cuda else "cpu"}
    if cuda:
        try:
            import torch

            summary["cuda_device_name"] = torch.cuda.get_device_name(0)
            summary["cuda_device_count"] = torch.cuda.device_count()
        except Exception:
            pass
    return summary
