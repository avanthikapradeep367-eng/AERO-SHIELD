"""
schemas/authentication.py — Request/response schemas for the Authentication Ledger API.

Mirrors the parameter contract of AuthenticationService.record_authentication() and
the AuthRecord dataclass returned by the service layer.  All hex IDs are accepted
with or without '0x' prefix — the service-layer hex_to_bytes32() handles both.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RecordAuthenticationRequest(BaseModel):
    """
    Request body for POST /blockchain/authentication.

    auth_id and session_id must be hex strings representing 32-byte values.
    If they are shorter, the service layer right-pads them with zero bytes.
    If longer, only the first 32 bytes are used.
    """

    auth_id: str = Field(
        ...,
        min_length=2,
        description=(
            "Unique 32-byte identifier for this authentication event (0x-prefixed hex). "
            "Typically generated as SHA-256 of the raw authentication event payload."
        ),
        examples=["0xabc123def456abc123def456abc123def456abc123def456abc123def456abc1"],
    )
    device_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Module 1 string device ID (e.g. UAV-ALPHA-001)",
        examples=["UAV-ALPHA-001"],
    )
    key_version: int = Field(
        ...,
        ge=0,
        description="Rolling key generation number stored as uint32 on-chain",
        examples=[42],
    )
    success: bool = Field(
        ...,
        description="True → AUTH_SUCCESS (1 on-chain). False → AUTH_FAILED (0 on-chain).",
        examples=[True],
    )
    session_id: str = Field(
        ...,
        min_length=2,
        description="Session identifier as a 0x-prefixed hex string (32 bytes).",
        examples=["0xdef456abc123def456abc123def456abc123def456abc123def456abc123def4"],
    )

    @field_validator("auth_id", "session_id")
    @classmethod
    def validate_hex_string(cls, v: str, info) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError(f"{info.field_name} must not be empty.")
        return cleaned

    @field_validator("device_id")
    @classmethod
    def sanitize_device_id(cls, v: str) -> str:
        sanitized = v.strip().upper()
        if not sanitized:
            raise ValueError("device_id must not be empty.")
        return sanitized

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "auth_id": "0xabc123def456abc123def456abc123def456abc123def456abc123def456abc1",
                    "device_id": "UAV-ALPHA-001",
                    "key_version": 42,
                    "success": True,
                    "session_id": "0xdef456abc123def456abc123def456abc123def456abc123def456abc123def4",
                }
            ]
        }
    }
