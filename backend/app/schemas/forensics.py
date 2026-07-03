"""
AERO-SHIELD X — Forensics Layer Pydantic Schemas

Request and response models for the Digital Forensics REST API layer.
All models follow the standard AERO-SHIELD response envelope defined
in schemas/common.py and Part 8 of the forensics specification.
"""

from __future__ import annotations

import base64
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ============================================================
#  PART 1 — Hash request schemas
# ============================================================

class HashTextRequest(BaseModel):
    """Hash a plain-text string."""
    text: str = Field(..., min_length=1, description="UTF-8 text to hash")
    label: Optional[str] = Field(None, description="Optional human-readable label")

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v


class HashJsonRequest(BaseModel):
    """Hash a JSON object (canonical serialisation)."""
    data: dict[str, Any] = Field(..., description="JSON object to hash")
    label: Optional[str] = Field(None, description="Optional label")


class HashFileRequest(BaseModel):
    """Hash a file by its server-side path."""
    file_path: str = Field(..., min_length=1, description="Absolute or relative server-side file path")
    label: Optional[str] = Field(None, description="Optional label")


class HashBytesRequest(BaseModel):
    """Hash binary data supplied as base64."""
    data_base64: str = Field(..., description="Base64-encoded binary data")
    label: Optional[str] = Field(None, description="Optional label")

    @field_validator("data_base64")
    @classmethod
    def valid_base64(cls, v: str) -> str:
        try:
            base64.b64decode(v, validate=True)
        except Exception:
            raise ValueError("data_base64 must be valid base64-encoded data")
        return v


class HashRequest(BaseModel):
    """
    Unified hash request — supply exactly ONE of text / json / bytes.
    The ``type`` field discriminates which input mode is used.
    """
    type: Literal["text", "json", "bytes"] = Field(
        ..., description="Input type: 'text', 'json', or 'bytes'"
    )
    text: Optional[str] = Field(None, description="Plain text (when type='text')")
    data: Optional[dict[str, Any]] = Field(None, description="JSON object (when type='json')")
    data_base64: Optional[str] = Field(None, description="Base64 bytes (when type='bytes')")
    label: Optional[str] = Field(None, description="Human-readable label for this hash")

    @model_validator(mode="after")
    def input_matches_type(self) -> "HashRequest":
        if self.type == "text" and not self.text:
            raise ValueError("'text' field is required when type='text'")
        if self.type == "json" and self.data is None:
            raise ValueError("'data' field is required when type='json'")
        if self.type == "bytes" and not self.data_base64:
            raise ValueError("'data_base64' field is required when type='bytes'")
        return self


# ============================================================
#  PART 2 — Verification request schemas
# ============================================================

class VerifyEvidenceRequest(BaseModel):
    """Verify a hash against the sealed blockchain record."""
    incident_id: str = Field(
        ..., min_length=1,
        description="On-chain incident ID (0x-prefixed hex)"
    )
    current_hash: Optional[str] = Field(
        None,
        description="Current SHA-256 hash of the evidence (0x-prefixed hex). "
                    "If omitted together with current_text/current_data, "
                    "the endpoint returns the on-chain state only."
    )
    current_text: Optional[str] = Field(
        None,
        description="Current evidence as plain text — hash computed server-side"
    )
    current_data: Optional[dict[str, Any]] = Field(
        None,
        description="Current evidence as a JSON dict — hash computed server-side"
    )

    @field_validator("incident_id")
    @classmethod
    def strip_incident_id(cls, v: str) -> str:
        return v.strip()

    @field_validator("current_hash")
    @classmethod
    def validate_hash_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        cleaned = v.strip().lower()
        bare = cleaned.removeprefix("0x")
        if not all(c in "0123456789abcdef" for c in bare):
            raise ValueError("current_hash must be a hex string (with or without 0x prefix)")
        return cleaned if cleaned.startswith("0x") else f"0x{cleaned}"


# ============================================================
#  PART 3 — Report request schemas
# ============================================================

class GenerateReportRequest(BaseModel):
    """Generate a full forensic report for an incident."""
    incident_id: str = Field(..., min_length=1, description="On-chain incident ID")
    current_hash: Optional[str] = Field(
        None, description="Current evidence hash for comparison (optional)"
    )
    include_chain_of_custody: bool = Field(True, description="Attach chain-of-custody history")
    include_incident_record: bool = Field(True, description="Attach on-chain IncidentRecord")
    analyst: str = Field("SYSTEM", description="Name / ID of the generating analyst")

    @field_validator("incident_id")
    @classmethod
    def strip_id(cls, v: str) -> str:
        return v.strip()


# ============================================================
#  PART 4 — Chain of Custody schemas
# ============================================================

class CreateCustodyRequest(BaseModel):
    """Create a chain-of-custody record for a piece of evidence."""
    evidence_id: str = Field(..., min_length=1, description="Unique evidence identifier")
    collected_by: str = Field(..., min_length=1, description="Collector name / ID")
    evidence_type: Literal["INCIDENT", "FILE", "LOG", "REPORT", "DEVICE"] = Field(
        "INCIDENT", description="Evidence type"
    )
    description: Optional[str] = Field(None, description="Free-text description")
    transaction_hash: Optional[str] = Field(None, description="Anchoring blockchain tx hash")
    blockchain_block: Optional[int] = Field(None, description="Blockchain block number")


class UpdateCustodyRequest(BaseModel):
    """Record a verification event against an existing custody record."""
    evidence_id: str = Field(..., min_length=1, description="Existing evidence ID")
    verified_by: str = Field(..., min_length=1, description="Verifier name / ID")
    status: Literal["VERIFIED", "TAMPERED", "INVESTIGATING", "RESOLVED", "CLOSED"] = Field(
        "VERIFIED", description="New verification status"
    )
    notes: Optional[str] = Field(None, description="Verification notes")
    transaction_hash: Optional[str] = Field(None, description="Optional blockchain tx hash")
    blockchain_block: Optional[int] = Field(None, description="Optional block number")


# ============================================================
#  PART 5 — Threat Intelligence schemas
# ============================================================

class PublishThreatRequest(BaseModel):
    """Publish a new threat intelligence entry."""
    device_id: str = Field(
        ..., min_length=1,
        description="Target device ID or IOC identifier"
    )
    threat_type: Literal["DEVICE", "IOC", "SIGNATURE", "REPLAY_ATTACK", "MALWARE", "ANOMALY"] = Field(
        ..., description="Type of threat"
    )
    threat_level: int = Field(..., ge=0, le=10, description="Severity 0–10")
    risk_score: int = Field(..., ge=0, le=100, description="Overall risk 0–100")
    threat_category: str = Field("UNKNOWN", description="Attack category (GPS_SPOOFING, etc.)")
    attack_signatures: list[str] = Field(default_factory=list, description="Attack signature strings")
    ioc_patterns: list[str] = Field(default_factory=list, description="Indicator-of-Compromise patterns")
    description: Optional[str] = Field(None, description="Free-text description")
    published_by: str = Field("SYSTEM", description="Publishing actor / system")
    publish_to_blockchain: bool = Field(
        True, description="Also blacklist the device on-chain (DEVICE type only)"
    )
    threat_id: Optional[str] = Field(
        None, description="Optional explicit threat ID (auto-generated if omitted)"
    )

    @field_validator("device_id")
    @classmethod
    def uppercase_device(cls, v: str) -> str:
        return v.strip().upper()


class UpdateThreatRequest(BaseModel):
    """Update an existing threat intelligence entry."""
    threat_id: str = Field(..., min_length=1, description="Threat ID to update")
    threat_level: Optional[int] = Field(None, ge=0, le=10, description="Updated severity")
    risk_score: Optional[int] = Field(None, ge=0, le=100, description="Updated risk score")
    attack_signatures: Optional[list[str]] = Field(None, description="Replace signature list")
    ioc_patterns: Optional[list[str]] = Field(None, description="Replace IOC list")
    threat_category: Optional[str] = Field(None, description="Updated category")
    description: Optional[str] = Field(None, description="Updated description")
    status: Optional[Literal["ACTIVE", "INVESTIGATING", "RESOLVED"]] = Field(
        None, description="Updated status"
    )
    attack_count: Optional[int] = Field(None, ge=0, description="Updated attack count")
    sync_blockchain: bool = Field(
        False, description="Sync updated levels to on-chain profile"
    )
