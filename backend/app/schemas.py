"""
schemas.py — Pydantic schemas for request/response validation.

Pydantic models enforce strict type-checking, auto-validation, and
provide clean OpenAPI/Swagger documentation out of the box.
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal, Any
from uuid import UUID


# ── Allowed Status Values ─────────────────────────────────────────────────────
VALID_STATUSES = {"active", "inactive", "maintenance"}


# ── Request Schema ────────────────────────────────────────────────────────────
class DeviceRegisterRequest(BaseModel):
    """
    Schema for POST /register-device request body.

    Validates that all required fields are present and correctly formatted
    before the data ever reaches the database layer.
    """

    device_id: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Unique identifier for the device (e.g. SHIELD-001)",
        examples=["SHIELD-001"],
    )

    device_name: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Human-readable name for the device",
        examples=["Sensor Unit Alpha"],
    )

    status: Literal["active", "inactive", "maintenance"] = Field(
        default="active",
        description="Initial operational status of the device",
        examples=["active"],
    )

    @field_validator("device_id")
    @classmethod
    def sanitize_device_id(cls, v: str) -> str:
        """Strip whitespace and enforce uppercase for consistency."""
        return v.strip().upper()

    @field_validator("device_name")
    @classmethod
    def sanitize_device_name(cls, v: str) -> str:
        """Strip surrounding whitespace from device name."""
        return v.strip()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "device_id": "SHIELD-001",
                    "device_name": "Sensor Unit Alpha",
                    "status": "active",
                }
            ]
        }
    }


# ── Response Schema ───────────────────────────────────────────────────────────
class DeviceResponse(BaseModel):
    """
    Schema for API responses returning device data.

    Used by both POST /register-device and GET /device/{device_id}.
    Strips internal fields (like raw DB id) that clients don't need,
    and formats timestamps in ISO 8601.
    """

    id: UUID = Field(..., description="Internal UUID of the device record")
    device_id: str = Field(..., description="Unique device identifier")
    device_name: str = Field(..., description="Human-readable device name")
    status: str = Field(..., description="Current device status")
    created_at: datetime = Field(..., description="Registration timestamp (UTC)")

    model_config = {
        # Allows the schema to read from ORM model attributes directly
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "device_id": "SHIELD-001",
                    "device_name": "Sensor Unit Alpha",
                    "status": "active",
                    "created_at": "2026-06-11T06:30:00Z",
                }
            ]
        },
    }


# ── Error Response Schema ─────────────────────────────────────────────────────
class ErrorResponse(BaseModel):
    """Standard error response shape returned on 4xx/5xx errors."""

    detail: str = Field(..., description="Human-readable error description")

    model_config = {
        "json_schema_extra": {
            "examples": [{"detail": "Device with ID 'SHIELD-001' already exists."}]
        }
    }


# ── Health / Status Schemas ───────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Response schema for GET /api/v1/health."""

    status: str = Field(..., description="Overall service status: operational | degraded")
    version: str = Field(..., description="API version string")
    database: str = Field(..., description="Database connectivity: connected | unreachable")
    blockchain: str = Field(..., description="Blockchain layer status (mocked)")
    ai_engine: str = Field(..., description="AI engine status (mocked)")
    timestamp: datetime = Field(..., description="UTC timestamp of the health check")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "operational",
                    "version": "1.0.0",
                    "database": "connected",
                    "blockchain": "mocked",
                    "ai_engine": "mocked",
                    "timestamp": "2026-06-29T10:00:00Z",
                }
            ]
        }
    }


# ── Simulation Schemas ────────────────────────────────────────────────────────

VALID_ATTACK_TYPES = {
    "DDOS",
    "INJECTION",
    "REPLAY",
    "MAN_IN_THE_MIDDLE",
    "BRUTE_FORCE",
    "SPOOFING",
    "JAMMING",
    "UNKNOWN",
}


class AttackRequest(BaseModel):
    """Request body for POST /api/v1/simulate-attack."""

    device_id: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Target device identifier (e.g. SHIELD-001)",
        examples=["SHIELD-001"],
    )
    attack_type: str = Field(
        ...,
        description=(
            "Category of simulated attack. "
            f"One of: {', '.join(sorted(VALID_ATTACK_TYPES))}"
        ),
        examples=["DDOS"],
    )
    source_ip: str | None = Field(
        None,
        description="Source IP address of the simulated attack",
        examples=["192.168.1.100"],
    )
    payload_sample: str | None = Field(
        None,
        max_length=1000,
        description="Optional sample of the attack payload for analysis",
    )

    @field_validator("device_id")
    @classmethod
    def sanitize_device_id(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("attack_type")
    @classmethod
    def validate_attack_type(cls, v: str) -> str:
        normalized = v.strip().upper().replace(" ", "_").replace("-", "_")
        if normalized not in VALID_ATTACK_TYPES:
            raise ValueError(
                f"Invalid attack_type '{v}'. "
                f"Must be one of: {', '.join(sorted(VALID_ATTACK_TYPES))}"
            )
        return normalized

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "device_id": "SHIELD-001",
                    "attack_type": "DDOS",
                    "source_ip": "192.168.1.100",
                    "payload_sample": None,
                }
            ]
        }
    }


class AttackResponse(BaseModel):
    """Response schema for POST /api/v1/simulate-attack."""

    device_id: str = Field(..., description="Target device identifier")
    attack_type: str = Field(..., description="Category of attack analysed")
    analysis_id: str = Field(..., description="UUID for correlating this analysis event")
    risk_score: float = Field(..., description="AI-determined risk level (0–100)")
    ai_confidence: float = Field(..., description="AI model confidence percentage")
    threat_detected: bool = Field(..., description="True when risk_score > 90")
    key_rotated: bool = Field(
        ...,
        description="True when a high-risk score triggered rolling key rotation",
    )
    blockchain_logged: bool = Field(
        ...,
        description="True when the event was submitted to the blockchain",
    )
    blockchain_tx: str | None = Field(
        None, description="Mocked transaction hash (present when blockchain_logged=True)"
    )
    action_taken: str = Field(..., description="Human-readable description of the response action")
    timestamp: datetime = Field(..., description="UTC timestamp of the simulation")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "device_id": "SHIELD-001",
                    "attack_type": "DDOS",
                    "analysis_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
                    "risk_score": 91.5,
                    "ai_confidence": 96.3,
                    "threat_detected": True,
                    "key_rotated": True,
                    "blockchain_logged": True,
                    "blockchain_tx": "0xabc123...",
                    "action_taken": "Rolling key rotated; attack logged to blockchain.",
                    "timestamp": "2026-06-29T10:00:00Z",
                }
            ]
        }
    }
