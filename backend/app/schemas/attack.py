"""
schemas/attack.py — Attack simulation request and response schemas.
"""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime


VALID_ATTACK_TYPES: set[str] = {
    "DDOS",
    "INJECTION",
    "REPLAY",
    "MAN_IN_THE_MIDDLE",
    "BRUTE_FORCE",
    "SPOOFING",
    "JAMMING",
    "UNKNOWN",
}

HIGH_RISK_THRESHOLD: float = 90.0


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
        description="Optional sample of the attack payload for analysis context",
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
        ..., description="True when a high-risk score triggered rolling key rotation"
    )
    blockchain_logged: bool = Field(
        ..., description="True when the attack event was submitted to the blockchain"
    )
    blockchain_tx: str | None = Field(
        None, description="Transaction hash returned by blockchain (present when logged)"
    )
    action_taken: str = Field(
        ..., description="Human-readable summary of the automated response"
    )
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
