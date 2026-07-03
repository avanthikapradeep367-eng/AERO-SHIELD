"""
api/blockchain/dependencies.py — FastAPI dependency factories and shared error
handling utilities for the entire Blockchain REST API layer.

Design contract
---------------
• Service factories (get_*_service) are the ONLY place where service objects
  are instantiated.  Route functions receive them via Depends() — never via
  module-level globals — so each request gets a fresh service that shares the
  underlying Web3 / account singletons from web3_client.py.

• blockchain_error_json() is the single error-to-response translator.  Every
  blockchain exception maps to a deterministic HTTP status code and the standard
  error envelope defined in schemas/common.py.

• success_response() and tx_success_response() build the standard success envelope
  so route functions stay free of formatting boilerplate.
"""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from app.blockchain.blockchain_service import BlockchainService, TransactionResult
from app.blockchain.services import (
    DeviceService,
    AuthenticationService,
    EvidenceService,
    ThreatService,
)
from app.blockchain.exceptions import (
    BlockchainBaseError,
    BlockchainConnectionError,
    GasEstimationError,
    TransactionError,
    DeviceNotFoundError,
    DuplicateDeviceError,
    AuthRecordNotFoundError,
    DuplicateAuthRecordError,
    IncidentNotFoundError,
    DuplicateIncidentError,
    EvidenceTamperingError,
    ThreatProfileNotFoundError,
    DeviceNotBlacklistedError,
)
from app.blockchain.utils import now_iso
from app.core.logger import get_logger

logger = get_logger("api.blockchain")


# ── Service dependency factories ────────────────────────────────────────────────
# Each factory returns a new service instance per request.  Because the underlying
# Web3 connection and account are module-level singletons (see web3_client.py),
# construction is cheap — it just performs dictionary lookups, not TCP connections.

def get_blockchain_service() -> BlockchainService:
    """Dependency: core BlockchainService (used by the health endpoint)."""
    return BlockchainService()


def get_device_service() -> DeviceService:
    """Dependency: Module 1 — Device Registry service."""
    return DeviceService()


def get_authentication_service() -> AuthenticationService:
    """Dependency: Module 2 — Authentication Ledger service."""
    return AuthenticationService()


def get_evidence_service() -> EvidenceService:
    """Dependency: Module 3 — Evidence Vault service."""
    return EvidenceService()


def get_threat_service() -> ThreatService:
    """Dependency: Module 4 — Threat Intelligence service."""
    return ThreatService()


# ── Standard response builders ──────────────────────────────────────────────────

def success_response(
    message: str,
    data: Any = None,
) -> dict:
    """
    Build a standard success envelope for read-only (view) operations.
    transactionHash and gasUsed are omitted (None) for view calls.
    """
    return {
        "success": True,
        "message": message,
        "timestamp": now_iso(),
        "transactionHash": None,
        "gasUsed": None,
        "data": data,
    }


def tx_success_response(
    message: str,
    result: TransactionResult,
    data: dict | None = None,
) -> dict:
    """
    Build a standard success envelope for write (state-changing) operations.
    Pulls tx_hash and gas_used directly from the TransactionResult.
    """
    return {
        "success": True,
        "message": message,
        "timestamp": now_iso(),
        "transactionHash": result.tx_hash,
        "gasUsed": str(result.gas_used),
        "data": {
            **(data or {}),
            "block_number": result.block_number,
            "gas_cost_eth": result.gas_cost_eth,
            "execution_time_ms": result.execution_time_ms,
            "wallet_address": result.wallet_address,
        },
    }


# ── Exception → HTTP status code mapping ───────────────────────────────────────

_STATUS_MAP: dict[type, int] = {
    # 404 Not Found
    DeviceNotFoundError:        404,
    AuthRecordNotFoundError:    404,
    IncidentNotFoundError:      404,
    ThreatProfileNotFoundError: 404,
    DeviceNotBlacklistedError:  404,
    # 409 Conflict / Duplicate
    DuplicateDeviceError:       409,
    DuplicateAuthRecordError:   409,
    DuplicateIncidentError:     409,
    EvidenceTamperingError:     409,
    # 422 Unprocessable — gas estimation reveals a contract revert
    GasEstimationError:         422,
    # 502 Bad Gateway — transaction sent but reverted
    TransactionError:           502,
    # 503 Service Unavailable — node unreachable
    BlockchainConnectionError:  503,
}


def _http_status_for(exc: Exception) -> int:
    """Return the most appropriate HTTP status code for an exception."""
    direct = _STATUS_MAP.get(type(exc))
    if direct:
        return direct
    if isinstance(exc, BlockchainBaseError):
        return 500
    if isinstance(exc, ValueError):
        return 422
    return 500


def blockchain_error_json(exc: Exception) -> JSONResponse:
    """
    Convert any blockchain domain exception (or plain ValueError) into a
    standardised JSON error response matching BlockchainErrorResponse.

    Logs a WARNING (or ERROR for unexpected exceptions) before returning.
    """
    exc_type_name = type(exc).__name__

    if isinstance(exc, BlockchainBaseError):
        message = exc.message
        details: dict = dict(exc.details) if exc.details else {}
    elif isinstance(exc, ValueError):
        message = str(exc)
        details = {}
    else:
        message = f"Unexpected error: {exc}"
        details = {"exception_type": exc_type_name}

    # Attach tx_hash to details when a transaction was submitted but reverted
    if isinstance(exc, TransactionError) and exc.tx_hash:
        details["tx_hash"] = exc.tx_hash

    status_code = _http_status_for(exc)

    log_fn = logger.error if status_code >= 500 else logger.warning
    log_fn(
        "Blockchain API error | %s | status=%d | %s",
        exc_type_name,
        status_code,
        message,
    )

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": message,
            "errorCode": exc_type_name,
            "details": details or None,
        },
    )
