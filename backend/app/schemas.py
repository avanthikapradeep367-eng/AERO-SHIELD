"""
schemas.py — Pydantic schemas for request/response validation.

Pydantic models enforce strict type-checking, auto-validation, and
provide clean OpenAPI/Swagger documentation out of the box.
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal
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
