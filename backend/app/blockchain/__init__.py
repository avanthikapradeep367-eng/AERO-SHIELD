"""
AERO-SHIELD X — Blockchain Integration Layer
=============================================
Provides a zero-knowledge interface to the EvidenceVault smart contract for
Member 1 (Rolling Key Authentication) and Member 3 (SentinelX AI).

Quick-start
-----------
    from app.blockchain import DeviceService, AuthenticationService
    from app.blockchain import EvidenceService, ThreatService

    # Module 1 — Device Registry
    device_svc = DeviceService()
    device_svc.register_device("UAV-ALPHA-001", "UAV", "0x04...")
    record = device_svc.get_device("UAV-ALPHA-001")

    # Module 2 — Authentication Ledger (Member 1)
    auth_svc = AuthenticationService()
    auth_svc.record_authentication(
        auth_id="0xabc...", device_id="UAV-ALPHA-001",
        key_version=1, success=True, session_id="0xdef...",
    )

    # Module 3 — Evidence Vault (Member 3)
    evidence_svc = EvidenceService()
    evidence_svc.record_incident(
        incident_id="0x111...", attack_type="GPS_SPOOFING",
        source_device="UAV-ALPHA-001", target_device="GCS-001",
        risk_score=87, ai_confidence=94,
        action_taken="QUARANTINE", evidence_hash="0xsha256...",
    )

    # Module 4 — Threat Intelligence (Member 3)
    threat_svc = ThreatService()
    threat_svc.blacklist_device("UAV-ALPHA-001", threat_level=8, risk_score=95)

Health check (call from FastAPI startup event):
    from app.blockchain import BlockchainService
    svc = BlockchainService()
    print(svc.verify_connection())

Required environment variables (add to backend/.env):
    PRIVATE_KEY       — Ganache account private key (0x-prefixed)
    GANACHE_RPC_URL   — defaults to http://127.0.0.1:7545
    CHAIN_ID          — defaults to 1337
"""

from .blockchain_service import BlockchainService, TransactionResult
from .config import BlockchainConfig, load_config
from .services import (
    AuthenticationService,
    AuthRecord,
    DeviceRecord,
    DeviceService,
    EvidenceService,
    IncidentRecord,
    ThreatProfile,
    ThreatService,
)
from .exceptions import (
    ABIError,
    AuthRecordNotFoundError,
    BlockchainBaseError,
    BlockchainConnectionError,
    ContractError,
    ContractNotFoundError,
    DeviceNotBlacklistedError,
    DeviceNotFoundError,
    DuplicateAuthRecordError,
    DuplicateDeviceError,
    DuplicateIncidentError,
    EvidenceTamperingError,
    GasEstimationError,
    IncidentNotFoundError,
    ThreatProfileNotFoundError,
    TransactionError,
)

__all__ = [
    # Core services
    "BlockchainService",
    "TransactionResult",
    "BlockchainConfig",
    "load_config",
    # Domain services
    "DeviceService",
    "AuthenticationService",
    "EvidenceService",
    "ThreatService",
    # Return types
    "DeviceRecord",
    "AuthRecord",
    "IncidentRecord",
    "ThreatProfile",
    # Exceptions
    "BlockchainBaseError",
    "BlockchainConnectionError",
    "ContractError",
    "ContractNotFoundError",
    "ABIError",
    "GasEstimationError",
    "TransactionError",
    "DeviceNotFoundError",
    "DuplicateDeviceError",
    "AuthRecordNotFoundError",
    "DuplicateAuthRecordError",
    "IncidentNotFoundError",
    "DuplicateIncidentError",
    "EvidenceTamperingError",
    "ThreatProfileNotFoundError",
    "DeviceNotBlacklistedError",
]
