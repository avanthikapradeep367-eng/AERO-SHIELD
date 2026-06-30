"""
schemas/__init__.py — Unified re-export hub for all Pydantic schemas.

Importing from `app.schemas` continues to work exactly as before.
All existing routes and tests require zero changes.

New code should import directly from the sub-module:
    from app.schemas.integration import AIAnalysisResult
    from app.schemas.attack import AttackRequest
"""

# Device schemas (previously in app/schemas.py)
from app.schemas.device import (
    VALID_STATUSES,
    DeviceRegisterRequest,
    DeviceResponse,
    ErrorResponse,
)

# Attack simulation schemas
from app.schemas.attack import (
    VALID_ATTACK_TYPES,
    HIGH_RISK_THRESHOLD,
    AttackRequest,
    AttackResponse,
)

# Health schemas
from app.schemas.health import HealthResponse

# Inter-service integration contracts (new)
from app.schemas.integration import (
    BlockchainTxBase,
    BlockchainAuthResult,
    BlockchainAttackResult,
    BlockchainDeviceResult,
    BlockchainStatusResult,
    AIAnalysisResult,
    AIStatusResult,
)

__all__ = [
    # Device
    "VALID_STATUSES",
    "DeviceRegisterRequest",
    "DeviceResponse",
    "ErrorResponse",
    # Attack
    "VALID_ATTACK_TYPES",
    "HIGH_RISK_THRESHOLD",
    "AttackRequest",
    "AttackResponse",
    # Health
    "HealthResponse",
    # Integration contracts
    "BlockchainTxBase",
    "BlockchainAuthResult",
    "BlockchainAttackResult",
    "BlockchainDeviceResult",
    "BlockchainStatusResult",
    "AIAnalysisResult",
    "AIStatusResult",
]
