"""
app/ai/datasets/schema.py — Typed schema for SentinelX aerospace attack-event records.

Defines the single unit of data the dataset layer works with: one
authentication/network observation for an aerospace device (UAV, ground
control station, sensor, or relay), labeled with a ground-truth event
category. Built on Pydantic v2 (already an existing project dependency —
see app/schemas/*.py) so validation is free and consistent with the rest
of the codebase.

This schema is intentionally independent from app.schemas.attack.VALID_ATTACK_TYPES
(the HTTP-facing attack simulation contract owned by Member 1). The dataset
layer's EventType is a broader, ML-oriented taxonomy suited for training
data; category names overlap where it makes sense (REPLAY, BRUTE_FORCE,
SPOOFING) but are not required to match 1:1.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from ipaddress import ip_address

from pydantic import BaseModel, Field, computed_field, field_validator


class EventType(str, Enum):
    """Ground-truth category assigned to a synthetic log record."""

    NORMAL = "NORMAL"
    REPLAY = "REPLAY"
    BRUTE_FORCE = "BRUTE_FORCE"
    SPOOFING = "SPOOFING"
    DOS = "DOS"
    INVALID_ROLLING_KEY = "INVALID_ROLLING_KEY"
    ABNORMAL_DEVICE_BEHAVIOR = "ABNORMAL_DEVICE_BEHAVIOR"


class DeviceType(str, Enum):
    """Aerospace device categories participating in the simulated network."""

    UAV = "UAV"
    GCS = "GCS"
    SENSOR = "SENSOR"
    RELAY = "RELAY"


class Protocol(str, Enum):
    """Application-layer protocols observed on the simulated link."""

    MAVLINK = "MAVLINK"
    MQTT = "MQTT"
    HTTPS = "HTTPS"
    CUSTOM_RF = "CUSTOM_RF"


class AttackEventRecord(BaseModel):
    """
    One simulated authentication/network event for an aerospace device.

    `event_type` is the ground-truth label used for future training;
    `is_attack` is a derived binary label computed from it so callers
    never need to keep the two in sync manually.
    """

    event_id: str = Field(..., description="UUID4 identifying this log record")
    timestamp: datetime = Field(..., description="UTC timestamp the event was observed")
    device_id: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Originating/target device identifier, e.g. SHIELD-001",
    )
    device_type: DeviceType = Field(default=DeviceType.UAV)
    event_type: EventType = Field(
        ..., description="Ground-truth category used as the training label"
    )
    protocol: Protocol = Field(default=Protocol.MAVLINK)
    source_ip: str = Field(..., description="Observed source IP address")
    destination_ip: str = Field(..., description="Observed destination IP address")
    source_port: int = Field(ge=1, le=65535)
    destination_port: int = Field(ge=1, le=65535)
    rolling_key_version: int = Field(ge=0, description="Rolling key version presented by the client")
    rolling_key_valid: bool = Field(..., description="Whether the presented key passed validation")
    auth_success: bool = Field(..., description="Whether authentication succeeded")
    request_rate_hz: float = Field(ge=0, description="Observed request rate in the sampling window")
    payload_size_bytes: int = Field(ge=0)
    session_duration_ms: float = Field(ge=0)
    packet_loss_ratio: float = Field(ge=0, le=1)
    signal_strength_dbm: float | None = Field(
        default=None, ge=-130, le=0, description="RF/telemetry link quality, when applicable"
    )
    severity_hint: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description=(
            "Domain-informed severity assigned by the generator for weak "
            "supervision. Descriptive metadata only — not a model prediction."
        ),
    )

    @field_validator("device_id")
    @classmethod
    def _normalize_device_id(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("source_ip", "destination_ip")
    @classmethod
    def _validate_ip(cls, v: str) -> str:
        try:
            ip_address(v)
        except ValueError as exc:
            raise ValueError(f"'{v}' is not a valid IP address") from exc
        return v

    @field_validator("timestamp")
    @classmethod
    def _tz_aware_utc(cls, v: datetime) -> datetime:
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)

    @computed_field  # type: ignore[misc]
    @property
    def is_attack(self) -> bool:
        """Binary label derived from event_type — NORMAL is the only negative class."""
        return self.event_type != EventType.NORMAL


class DatasetMetadata(BaseModel):
    """Descriptive summary of a generated/loaded dataset, for tracking and reproducibility."""

    name: str
    version: str = "0.1.0"
    generated_at: datetime
    seed: int
    total_records: int
    class_distribution: dict[str, int]
    description: str = ""
