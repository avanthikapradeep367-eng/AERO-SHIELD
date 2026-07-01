"""
AERO-SHIELD X — SentinelX AI / CUDA Integration Layer
=======================================================
Owned by Member 3. Provides the CUDA/PyTorch threat-detection engine that
will eventually back app.services.ai_service.AIService (the mock interface
layer owned by Member 1).

This package is currently SCAFFOLDING ONLY:
    - No routes, schemas, or services outside this package have been
      modified to use it.
    - app/services/ai_service.py still returns mocked data and does not
      import anything from here yet.
    - No ML dependencies (torch, onnxruntime, ...) are installed or
      required to import this package — device detection degrades
      gracefully to "cpu" until they are added to requirements.txt.

Layout
------
    app/ai/
        config.py       — AIConfig / load_config()
        exceptions.py    — internal exception hierarchy (AIBaseError, ...)
        datasets/        — BaseDataset + dataset registry
        models/          — BaseModel + model registry
        inference/       — InferenceEngine (preprocessing/predict/postprocessing)
        sentinelx/       — SentinelXEngine, the top-level facade
        utils/           — device detection (get_device, is_cuda_available)

Quick-start (once implemented)
-------------------------------
    from app.ai import SentinelXEngine

    engine = SentinelXEngine()
    result = engine.analyze({"attack_type": "SPOOFING", "device_id": "UAV-001"})

Integration point
------------------
When ready, app/services/ai_service.py will be updated (by agreement, not
by this package) to construct a SentinelXEngine and delegate
analyze_request()/get_status() to engine.analyze()/engine.status(), while
keeping the app.interfaces.ai_interface.IAIService contract unchanged.
"""

from .config import AIConfig, load_config
from .exceptions import (
    AIBaseError,
    CUDAUnavailableError,
    DatasetError,
    InferenceError,
    ModelLoadError,
)
from .sentinelx import SentinelXEngine

__all__ = [
    "AIConfig",
    "load_config",
    "SentinelXEngine",
    "AIBaseError",
    "DatasetError",
    "ModelLoadError",
    "InferenceError",
    "CUDAUnavailableError",
]
