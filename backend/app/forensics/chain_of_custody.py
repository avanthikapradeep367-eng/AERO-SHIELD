"""
AERO-SHIELD X — Digital Chain of Custody

Tracks the immutable lifecycle of every piece of forensic evidence:
from initial collection → verification → resolution.

Storage: in-memory thread-safe dict (PostgreSQL-independent).
Each CustodyRecord captures who collected / verified the evidence,
which blockchain transaction anchors it, and the full audit history.

Design notes
------------
• One CustodyRecord per evidence_id.
• Every state change appends to ``verification_history`` (never overwrites).
• The ``current_status`` field reflects the latest state.
• Thread safety via a single module-level RLock.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.logger import get_logger

logger = get_logger("forensics.custody")

# ── Status constants ────────────────────────────────────────────────────────────
STATUS_COLLECTED   = "COLLECTED"
STATUS_VERIFIED    = "VERIFIED"
STATUS_TAMPERED    = "TAMPERED"
STATUS_INVESTIGATING = "INVESTIGATING"
STATUS_RESOLVED    = "RESOLVED"
STATUS_CLOSED      = "CLOSED"

VALID_STATUSES = {
    STATUS_COLLECTED, STATUS_VERIFIED, STATUS_TAMPERED,
    STATUS_INVESTIGATING, STATUS_RESOLVED, STATUS_CLOSED,
}

# ── In-memory store ─────────────────────────────────────────────────────────────
_store: dict[str, "CustodyRecord"] = {}
_lock = threading.RLock()


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class CustodyEvent:
    """A single entry in the audit trail."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = "COLLECTED"          # COLLECTED | VERIFIED | UPDATED | CLOSED
    actor: str = "SYSTEM"                  # who performed this action
    status: str = STATUS_COLLECTED
    notes: str | None = None
    transaction_hash: str | None = None
    blockchain_block: int | None = None
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "actor": self.actor,
            "status": self.status,
            "notes": self.notes,
            "transaction_hash": self.transaction_hash,
            "blockchain_block": self.blockchain_block,
            "timestamp": self.timestamp,
        }


@dataclass
class CustodyRecord:
    """Full chain-of-custody record for one piece of evidence."""
    custody_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    evidence_id: str = ""
    evidence_type: str = "INCIDENT"        # INCIDENT | FILE | LOG | REPORT | DEVICE
    description: str | None = None

    # Collection metadata
    collected_by: str = "SYSTEM"
    collection_time: str = field(default_factory=_now_iso)

    # Verification metadata
    verified_by: str | None = None
    verification_time: str | None = None

    # Blockchain anchor
    transaction_hash: str | None = None
    blockchain_block: int | None = None

    # Current workflow status
    current_status: str = STATUS_COLLECTED

    # Full audit trail
    verification_history: list[CustodyEvent] = field(default_factory=list)

    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "custody_id": self.custody_id,
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type,
            "description": self.description,
            "collected_by": self.collected_by,
            "collection_time": self.collection_time,
            "verified_by": self.verified_by,
            "verification_time": self.verification_time,
            "transaction_hash": self.transaction_hash,
            "blockchain_block": self.blockchain_block,
            "current_status": self.current_status,
            "verification_history": [e.to_dict() for e in self.verification_history],
            "event_count": len(self.verification_history),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ── Public API ──────────────────────────────────────────────────────────────────

def create_record(
    evidence_id: str,
    collected_by: str,
    evidence_type: str = "INCIDENT",
    description: str | None = None,
    transaction_hash: str | None = None,
    blockchain_block: int | None = None,
) -> CustodyRecord:
    """
    Create a new chain-of-custody record for a piece of evidence.
    If a record already exists for ``evidence_id``, the existing record is
    returned (idempotent — does not create duplicates).

    Args:
        evidence_id:       Unique identifier (incident ID, file hash, etc.).
        collected_by:      Name or ID of the entity that collected the evidence.
        evidence_type:     One of INCIDENT, FILE, LOG, REPORT, DEVICE.
        description:       Optional free-text description.
        transaction_hash:  Blockchain tx hash anchoring the creation event.
        blockchain_block:  Block number of the creation transaction.

    Returns:
        The new (or existing) CustodyRecord.
    """
    with _lock:
        if evidence_id in _store:
            logger.debug("create_record | evidence_id=%s already exists — returning existing", evidence_id)
            return _store[evidence_id]

        event = CustodyEvent(
            event_type="COLLECTED",
            actor=collected_by,
            status=STATUS_COLLECTED,
            notes=description,
            transaction_hash=transaction_hash,
            blockchain_block=blockchain_block,
        )

        record = CustodyRecord(
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            description=description,
            collected_by=collected_by,
            transaction_hash=transaction_hash,
            blockchain_block=blockchain_block,
            current_status=STATUS_COLLECTED,
            verification_history=[event],
        )

        _store[evidence_id] = record
        logger.info(
            "create_record | evidence_id=%s | type=%s | collected_by=%s",
            evidence_id, evidence_type, collected_by,
        )
        return record


def update_verification(
    evidence_id: str,
    verified_by: str,
    status: str,
    notes: str | None = None,
    transaction_hash: str | None = None,
    blockchain_block: int | None = None,
) -> CustodyRecord:
    """
    Record a verification event against an existing custody record.
    Appends to ``verification_history`` and updates ``current_status``.

    Args:
        evidence_id:      Evidence to update.
        verified_by:      Actor performing the verification.
        status:           New status (VERIFIED | TAMPERED | INVESTIGATING | RESOLVED | CLOSED).
        notes:            Optional verification notes.
        transaction_hash: Blockchain tx hash (if verification triggered a write).
        blockchain_block: Block number.

    Returns:
        Updated CustodyRecord.

    Raises:
        KeyError:   If no record exists for ``evidence_id``.
        ValueError: If ``status`` is not a recognised value.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")

    with _lock:
        record = get_record(evidence_id)   # raises KeyError if missing

        event = CustodyEvent(
            event_type="VERIFIED",
            actor=verified_by,
            status=status,
            notes=notes,
            transaction_hash=transaction_hash,
            blockchain_block=blockchain_block,
        )

        record.verification_history.append(event)
        record.current_status = status
        record.verified_by = verified_by
        record.verification_time = _now_iso()
        record.updated_at = _now_iso()

        if transaction_hash:
            record.transaction_hash = transaction_hash
        if blockchain_block is not None:
            record.blockchain_block = blockchain_block

        logger.info(
            "update_verification | evidence_id=%s | status=%s | by=%s",
            evidence_id, status, verified_by,
        )
        return record


def get_record(evidence_id: str) -> CustodyRecord:
    """
    Retrieve the chain-of-custody record for a given evidence ID.

    Raises:
        KeyError: If no record exists.
    """
    with _lock:
        record = _store.get(evidence_id)
        if record is None:
            raise KeyError(f"No chain-of-custody record found for evidence_id='{evidence_id}'")
        return record


def get_history(evidence_id: str) -> list[dict[str, Any]]:
    """
    Return the full audit trail for a given evidence ID.

    Raises:
        KeyError: If no record exists.
    """
    record = get_record(evidence_id)
    return [e.to_dict() for e in record.verification_history]


def list_records(limit: int = 100) -> list[dict[str, Any]]:
    """Return all custody records (newest first), up to ``limit``."""
    with _lock:
        records = sorted(
            _store.values(),
            key=lambda r: r.created_at,
            reverse=True,
        )
        return [r.to_dict() for r in records[:limit]]


def record_exists(evidence_id: str) -> bool:
    """Return True if a custody record exists for this evidence_id."""
    with _lock:
        return evidence_id in _store
