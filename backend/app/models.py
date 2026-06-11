"""
models.py — SQLAlchemy ORM models for AERO-SHIELD.

Defines the database table schemas. Each class maps to a PostgreSQL table.
"""

from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
import uuid

from app.database import Base


class Device(Base):
    """
    Represents a registered AERO-SHIELD device in the database.

    Table: devices

    Columns:
        id          — Auto-generated UUID primary key (internal DB identifier)
        device_id   — Unique human-readable device identifier (e.g. "SHIELD-001")
        device_name — Friendly name for the device (e.g. "Sensor Unit Alpha")
        status      — Current operational status: 'active' | 'inactive' | 'maintenance'
        created_at  — Timestamp of when the device was first registered (UTC)
    """

    __tablename__ = "devices"

    # Primary key — UUID generated at the database level for uniqueness & security
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False,
        comment="Internal unique identifier (UUID)",
    )

    # Unique device identifier provided by the client (e.g. hardware serial)
    device_id = Column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique external device identifier (e.g. SHIELD-001)",
    )

    # Human-readable name for the device
    device_name = Column(
        String(200),
        nullable=False,
        comment="Friendly display name for the device",
    )

    # Operational status of the device
    status = Column(
        String(50),
        nullable=False,
        default="active",
        comment="Device status: active | inactive | maintenance",
    )

    # Auto-populated timestamp at record creation (server-side UTC)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="UTC timestamp of device registration",
    )

    def __repr__(self) -> str:
        return (
            f"<Device(device_id='{self.device_id}', "
            f"name='{self.device_name}', status='{self.status}')>"
        )
