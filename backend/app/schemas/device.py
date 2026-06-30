"""
schemas/device.py — Device registration and lookup Pydantic schemas.

Owns DeviceRegisterRequest, DeviceResponse, ErrorResponse.
These were previously in app/schemas.py and are preserved here verbatim
so that existing routes (routes/auth.py) continue to work unchanged.
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Literal
from uuid import UUID


VALID_STATUSES: set[str] = {"active", "inactive", "maintenance"}


class DeviceRegisterRequest(BaseModel):
    """Request body for POST /api/v1/register-device."""

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
        return v.strip().upper()

    @field_validator("device_name")
    @classmethod
    def sanitize_device_name(cls, v: str) -> str:
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


class DeviceResponse(BaseModel):
    """Response schema for device registration and lookup endpoints."""

    id: UUID = Field(..., description="Internal UUID of the device record")
    device_id: str = Field(..., description="Unique device identifier")
    device_name: str = Field(..., description="Human-readable device name")
    status: str = Field(..., description="Current device status")
    created_at: datetime = Field(..., description="Registration timestamp (UTC)")

    model_config = {
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


class ErrorResponse(BaseModel):
    """Standard error response returned on 4xx / 5xx errors."""

    detail: str = Field(..., description="Human-readable error description")

    model_config = {
        "json_schema_extra": {
            "examples": [{"detail": "Device with ID 'SHIELD-001' already exists."}]
        }
    }
