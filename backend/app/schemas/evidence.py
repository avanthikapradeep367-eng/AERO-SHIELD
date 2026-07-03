"""
schemas/evidence.py — Request/response schemas for the Evidence Vault API.

Mirrors the parameter contract of EvidenceService.record_incident() and the
IncidentRecord dataclass returned by the service layer.  risk_score and
ai_confidence are validated against the 0-100 range enforced by the service.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

# Common attack type strings used by SentinelX (not enforced as enum — extensible)
KNOWN_ATTACK_TYPES: set[str] = {
    "GPS_SPOOFING",
    "REPLAY_ATTACK",
    "JAMMING",
    "MITM",
    "UNAUTHORIZED_ACCESS",
    "PROTOCOL_EXPLOIT",
    "SIGNAL_INTERFERENCE",
    "SUPPLY_CHAIN_COMPROMISE",
    "FIRMWARE_TAMPERING",
    "COMMAND_INJECTION",
}


class RecordEvidenceRequest(BaseModel):
    """
    Request body for POST /blockchain/evidence.

    Maps 1-to-1 onto EvidenceService.record_incident() parameters.
    Both source_device and target_device must be valid Module 1 string IDs;
    they are stored on-chain as keccak256(device_id) for cross-module consistency.
    """

    incident_id: str = Field(
        ...,
        min_length=2,
        description=(
            "Unique 32-byte hex identifier for this incident (0x-prefixed). "
            "Typically SHA-256 of the incident payload or a UUID-as-hex."
        ),
        examples=["0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"],
    )
    attack_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description=(
            "Attack category string. "
            f"Known SentinelX types: {', '.join(sorted(KNOWN_ATTACK_TYPES))}. "
            "Custom strings are accepted and stored as-is."
        ),
        examples=["GPS_SPOOFING"],
    )
    source_device: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Module 1 string device ID of the attacker or originating device",
        examples=["UAV-ALPHA-001"],
    )
    target_device: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Module 1 string device ID of the targeted device",
        examples=["GROUND-GCS-001"],
    )
    risk_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="SentinelX AI-assessed risk level 0–100 (100 = maximum risk)",
        examples=[87],
    )
    ai_confidence: int = Field(
        ...,
        ge=0,
        le=100,
        description="SentinelX model confidence percentage 0–100",
        examples=[94],
    )
    action_taken: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Response action string (e.g. QUARANTINE_ISSUED, ALERT_SENT, LOGGED)",
        examples=["QUARANTINE_ISSUED"],
    )
    evidence_hash: str = Field(
        ...,
        min_length=2,
        description=(
            "SHA-256 or SHA-3 hash of the evidence package (0x-prefixed hex). "
            "This hash is sealed immutably on-chain and used later to detect tampering."
        ),
        examples=["0xe3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
    )

    @field_validator("incident_id", "evidence_hash")
    @classmethod
    def validate_hex(cls, v: str, info) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError(f"{info.field_name} must not be empty.")
        return cleaned

    @field_validator("source_device", "target_device")
    @classmethod
    def sanitize_device_id(cls, v: str) -> str:
        sanitized = v.strip().upper()
        if not sanitized:
            raise ValueError("Device ID must not be empty.")
        return sanitized

    @field_validator("attack_type")
    @classmethod
    def sanitize_attack_type(cls, v: str) -> str:
        return v.strip().upper()

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "incident_id": "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
                    "attack_type": "GPS_SPOOFING",
                    "source_device": "UAV-ALPHA-001",
                    "target_device": "GROUND-GCS-001",
                    "risk_score": 87,
                    "ai_confidence": 94,
                    "action_taken": "QUARANTINE_ISSUED",
                    "evidence_hash": "0xe3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                }
            ]
        }
    }
