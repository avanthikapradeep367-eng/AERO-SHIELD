"""
schemas/threat.py — Request/response schemas for the Threat Intelligence API.

Mirrors the parameter contracts of ThreatService.blacklist_device() and
ThreatService.update_threat_profile().  threat_level (0-10) and risk_score (0-100)
ranges are enforced here at the API boundary, matching the Solidity require() checks.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class BlacklistDeviceRequest(BaseModel):
    """
    Request body for POST /blockchain/threat/blacklist.

    Simultaneously creates or updates the device's on-chain ThreatProfile
    and marks it as blacklisted.  Called by SentinelX AI (Member 3) when
    a threat is detected above the configured alert threshold.
    """

    device_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Module 1 string device ID to blacklist (e.g. UAV-ALPHA-001)",
        examples=["UAV-ALPHA-001"],
    )
    threat_level: int = Field(
        ...,
        ge=0,
        le=10,
        description="Threat severity 0–10 (10 = maximum / critical threat)",
        examples=[8],
    )
    risk_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Overall risk score 0–100",
        examples=[95],
    )

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
                    "device_id": "UAV-ALPHA-001",
                    "threat_level": 8,
                    "risk_score": 95,
                }
            ]
        }
    }
