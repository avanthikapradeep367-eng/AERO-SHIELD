"""
schemas/common.py — Standardised response envelopes for the AERO-SHIELD Blockchain REST API.

Every blockchain endpoint MUST return one of these two models:
  • BlockchainApiResponse   — successful operation  (success=True)
  • BlockchainErrorResponse — failed operation      (success=False)

Keeping the contract here means Swagger docs stay consistent across all
five blockchain sub-routers (device / authentication / evidence / threat / health).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    """Current UTC instant as ISO-8601 string — used as response timestamp default."""
    return datetime.now(tz=timezone.utc).isoformat()


# ── Success envelope ────────────────────────────────────────────────────────────

class BlockchainApiResponse(BaseModel):
    """
    Standard success envelope returned by every blockchain API endpoint.

    Read-only (view) endpoints:
        transactionHash = None
        gasUsed         = None

    Write (state-changing) endpoints:
        transactionHash = mined Ethereum tx hash
        gasUsed         = gas consumed, as a decimal string
    """

    success: bool = Field(
        default=True,
        description="Always True for success responses",
    )
    message: str = Field(
        ...,
        description="Human-readable description of the operation result",
        examples=["Device registered on-chain successfully."],
    )
    timestamp: str = Field(
        default_factory=_utc_now_iso,
        description="ISO-8601 UTC timestamp of when the response was generated",
        examples=["2026-07-03T10:00:00+00:00"],
    )
    transactionHash: Optional[str] = Field(
        default=None,
        description="Ethereum transaction hash — write operations only",
        examples=["0xabc123def456abc123def456abc123def456abc123def456abc123def456abc1"],
    )
    gasUsed: Optional[str] = Field(
        default=None,
        description="Gas consumed by the transaction (decimal string) — write operations only",
        examples=["78432"],
    )
    data: Optional[Any] = Field(
        default=None,
        description="Endpoint-specific response payload",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Device registered on-chain successfully.",
                    "timestamp": "2026-07-03T10:00:00+00:00",
                    "transactionHash": "0xabc123def456abc123def456abc123def456abc123def456abc123def456abc1",
                    "gasUsed": "78432",
                    "data": {
                        "device_id": "UAV-ALPHA-001",
                        "device_type": "UAV",
                        "block_number": 42,
                    },
                }
            ]
        }
    }


# ── Error envelope ──────────────────────────────────────────────────────────────

class BlockchainErrorResponse(BaseModel):
    """
    Standard error envelope returned by blockchain API endpoints on failure.

    errorCode maps to the Python exception class name, making it machine-parseable
    without forcing callers to parse free-text message strings.
    """

    success: bool = Field(
        default=False,
        description="Always False for error responses",
    )
    message: str = Field(
        ...,
        description="Human-readable error description",
        examples=["Device 'UAV-ALPHA-001' not found in the registry."],
    )
    errorCode: str = Field(
        ...,
        description="Machine-readable exception class name",
        examples=["DeviceNotFoundError", "BlockchainConnectionError", "DuplicateDeviceError"],
    )
    details: Optional[dict[str, Any]] = Field(
        default=None,
        description="Additional structured error context (tx_hash for reverted transactions, etc.)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": False,
                    "message": "Device 'UAV-ALPHA-001' not found in the registry.",
                    "errorCode": "DeviceNotFoundError",
                    "details": {"device_id": "UAV-ALPHA-001"},
                }
            ]
        }
    }
