"""
AERO-SHIELD X — Threat Intelligence Engine

Provides an enriched, metadata-rich threat intelligence layer on top of the
existing on-chain ThreatService.  The blockchain stores canonical truth
(which devices are blacklisted); this engine stores rich IOC metadata
(signatures, categories, attack patterns, threat feeds).

Architecture
------------
• In-memory ThreatEntry store (thread-safe dict + RLock).
• Optional blockchain sync: publishing a threat can simultaneously blacklist
  the device on-chain via ThreatService.
• Independent of PostgreSQL — no SQLAlchemy dependency.

Threat types
------------
    DEVICE          — a specific aerospace device (UAV, GCS, satellite)
    IOC             — indicator of compromise (hash, IP, domain)
    SIGNATURE       — attack signature / pattern
    REPLAY_ATTACK   — detected replay attack pattern
    MALWARE         — malware signature or behaviour pattern
    ANOMALY         — statistical anomaly (flagged by SentinelX AI)
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from app.blockchain.services.threat_service import ThreatService
from app.blockchain.exceptions import BlockchainBaseError
from app.core.logger import get_logger

logger = get_logger("forensics.threat_intelligence")

# ── Status constants ────────────────────────────────────────────────────────────
STATUS_ACTIVE        = "ACTIVE"
STATUS_INVESTIGATING = "INVESTIGATING"
STATUS_RESOLVED      = "RESOLVED"
STATUS_REVOKED       = "REVOKED"

THREAT_TYPES = {"DEVICE", "IOC", "SIGNATURE", "REPLAY_ATTACK", "MALWARE", "ANOMALY"}
THREAT_CATEGORIES = {
    "GPS_SPOOFING", "RADAR_JAMMING", "REPLAY_ATTACK", "MAN_IN_THE_MIDDLE",
    "UNAUTHORIZED_ACCESS", "DATA_EXFILTRATION", "DENIAL_OF_SERVICE",
    "FIRMWARE_TAMPERING", "SIGNAL_INTERFERENCE", "SUPPLY_CHAIN_ATTACK", "UNKNOWN",
}

# ── In-memory store ─────────────────────────────────────────────────────────────
_store: dict[str, "ThreatEntry"] = {}
_lock = threading.RLock()


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class ThreatEntry:
    """Rich threat intelligence record (in-memory metadata layer)."""
    threat_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    device_id: str = ""
    threat_type: str = "DEVICE"
    threat_level: int = 0                  # 0–10
    risk_score: int = 0                    # 0–100
    threat_category: str = "UNKNOWN"
    attack_signatures: list[str] = field(default_factory=list)
    ioc_patterns: list[str] = field(default_factory=list)
    description: str | None = None
    status: str = STATUS_ACTIVE
    on_chain: bool = False                 # True if blacklisted on-chain
    blockchain_tx: str | None = None
    published_by: str = "SYSTEM"
    published_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    attack_count: int = 0
    last_seen: str | None = None
    feed_source: str = "AERO-SHIELD-X"    # threat feed origin label

    def to_dict(self) -> dict[str, Any]:
        return {
            "threat_id": self.threat_id,
            "device_id": self.device_id,
            "threat_type": self.threat_type,
            "threat_level": self.threat_level,
            "risk_score": self.risk_score,
            "threat_category": self.threat_category,
            "attack_signatures": self.attack_signatures,
            "ioc_patterns": self.ioc_patterns,
            "description": self.description,
            "status": self.status,
            "on_chain": self.on_chain,
            "blockchain_tx": self.blockchain_tx,
            "published_by": self.published_by,
            "published_at": self.published_at,
            "updated_at": self.updated_at,
            "attack_count": self.attack_count,
            "last_seen": self.last_seen,
            "feed_source": self.feed_source,
        }


# ── Public API ──────────────────────────────────────────────────────────────────

def publish_threat(
    device_id: str,
    threat_type: str,
    threat_level: int,
    risk_score: int,
    threat_category: str = "UNKNOWN",
    attack_signatures: list[str] | None = None,
    ioc_patterns: list[str] | None = None,
    description: str | None = None,
    published_by: str = "SYSTEM",
    publish_to_blockchain: bool = True,
    threat_id: str | None = None,
) -> ThreatEntry:
    """
    Publish a new threat intelligence entry.

    Optionally blacklists the device on-chain via ThreatService when
    ``publish_to_blockchain=True`` and threat_type == 'DEVICE'.

    Args:
        device_id:             Module 1 string device ID or IOC identifier.
        threat_type:           DEVICE | IOC | SIGNATURE | REPLAY_ATTACK | MALWARE | ANOMALY
        threat_level:          0–10 severity.
        risk_score:            0–100 overall risk.
        threat_category:       Attack category string.
        attack_signatures:     List of signature strings.
        ioc_patterns:          List of IOC pattern strings.
        description:           Free-text description.
        published_by:          Author / system publishing this entry.
        publish_to_blockchain: If True, also call ThreatService.blacklist_device().
        threat_id:             Optional explicit threat ID (auto-generated if None).

    Returns:
        The created ThreatEntry.

    Raises:
        ValueError: If threat_level or risk_score is out of range.
    """
    if not 0 <= threat_level <= 10:
        raise ValueError(f"threat_level must be 0–10, got {threat_level}")
    if not 0 <= risk_score <= 100:
        raise ValueError(f"risk_score must be 0–100, got {risk_score}")
    if threat_type not in THREAT_TYPES:
        raise ValueError(f"threat_type must be one of {THREAT_TYPES}, got '{threat_type}'")

    tid = threat_id or str(uuid.uuid4())
    blockchain_tx: str | None = None
    on_chain = False

    # Attempt blockchain blacklist if requested and this is a device-type threat
    if publish_to_blockchain and threat_type == "DEVICE":
        try:
            svc = ThreatService()
            result = svc.blacklist_device(
                device_id=device_id,
                threat_level=threat_level,
                risk_score=risk_score,
            )
            blockchain_tx = result.tx_hash
            on_chain = True
            logger.warning(
                "publish_threat | device blacklisted on-chain | device=%s | tx=%s",
                device_id, blockchain_tx,
            )
        except BlockchainBaseError as exc:
            logger.error(
                "publish_threat | blockchain blacklist failed | device=%s | %s: %s",
                device_id, type(exc).__name__, exc.message,
            )
            # Do not re-raise — store the entry in-memory even if blockchain fails

    entry = ThreatEntry(
        threat_id=tid,
        device_id=device_id,
        threat_type=threat_type,
        threat_level=threat_level,
        risk_score=risk_score,
        threat_category=threat_category,
        attack_signatures=attack_signatures or [],
        ioc_patterns=ioc_patterns or [],
        description=description,
        status=STATUS_ACTIVE,
        on_chain=on_chain,
        blockchain_tx=blockchain_tx,
        published_by=published_by,
        last_seen=_now_iso(),
    )

    with _lock:
        _store[tid] = entry

    logger.warning(
        "publish_threat | threat_id=%s | device=%s | level=%d | risk=%d | on_chain=%s",
        tid, device_id, threat_level, risk_score, on_chain,
    )
    return entry


def update_threat(
    threat_id: str,
    threat_level: int | None = None,
    risk_score: int | None = None,
    attack_signatures: list[str] | None = None,
    ioc_patterns: list[str] | None = None,
    threat_category: str | None = None,
    description: str | None = None,
    status: str | None = None,
    attack_count: int | None = None,
    sync_blockchain: bool = False,
) -> ThreatEntry:
    """
    Update an existing threat intelligence entry.

    Args:
        threat_id:         ID of the entry to update.
        threat_level:      Updated severity (0–10), or None to keep existing.
        risk_score:        Updated risk score (0–100), or None to keep existing.
        attack_signatures: Replace signature list (None = keep existing).
        ioc_patterns:      Replace IOC list (None = keep existing).
        threat_category:   Updated category (None = keep existing).
        description:       Updated description (None = keep existing).
        status:            Updated status (None = keep existing).
        attack_count:      Updated attack count (None = keep existing).
        sync_blockchain:   If True and entry is on-chain, update blockchain profile.

    Returns:
        Updated ThreatEntry.

    Raises:
        KeyError: If threat_id does not exist.
    """
    with _lock:
        entry = get_threat(threat_id)   # raises KeyError if not found

        if threat_level is not None:
            if not 0 <= threat_level <= 10:
                raise ValueError(f"threat_level must be 0–10, got {threat_level}")
            entry.threat_level = threat_level

        if risk_score is not None:
            if not 0 <= risk_score <= 100:
                raise ValueError(f"risk_score must be 0–100, got {risk_score}")
            entry.risk_score = risk_score

        if attack_signatures is not None:
            entry.attack_signatures = attack_signatures
        if ioc_patterns is not None:
            entry.ioc_patterns = ioc_patterns
        if threat_category is not None:
            entry.threat_category = threat_category
        if description is not None:
            entry.description = description
        if status is not None:
            entry.status = status
        if attack_count is not None:
            entry.attack_count = attack_count

        entry.last_seen = _now_iso()
        entry.updated_at = _now_iso()

    # Optionally sync to blockchain (outside lock to avoid deadlock)
    if sync_blockchain and entry.on_chain and entry.threat_type == "DEVICE":
        try:
            svc = ThreatService()
            svc.update_threat_profile(
                device_id=entry.device_id,
                threat_level=entry.threat_level,
                attack_count=entry.attack_count,
                risk_score=entry.risk_score,
            )
            logger.info("update_threat | synced to blockchain | threat_id=%s", threat_id)
        except BlockchainBaseError as exc:
            logger.error("update_threat | blockchain sync failed | %s: %s", type(exc).__name__, exc)

    logger.info("update_threat | threat_id=%s | status=%s", threat_id, entry.status)
    return entry


def remove_threat(
    threat_id: str,
    remove_from_blockchain: bool = True,
) -> ThreatEntry:
    """
    Remove a threat entry from the in-memory store.
    Optionally removes the device from the on-chain blacklist.

    Args:
        threat_id:               ID of the entry to remove.
        remove_from_blockchain:  If True and entry is on-chain, calls removeBlacklist().

    Returns:
        The removed ThreatEntry (for audit logging).

    Raises:
        KeyError: If threat_id does not exist.
    """
    with _lock:
        entry = get_threat(threat_id)    # raises KeyError if not found
        entry.status = STATUS_REVOKED
        entry.updated_at = _now_iso()
        removed = _store.pop(threat_id)

    # Blockchain removal outside lock
    if remove_from_blockchain and removed.on_chain and removed.threat_type == "DEVICE":
        try:
            svc = ThreatService()
            svc.remove_blacklist(removed.device_id)
            logger.info(
                "remove_threat | device removed from on-chain blacklist | device=%s",
                removed.device_id,
            )
        except BlockchainBaseError as exc:
            logger.warning(
                "remove_threat | blockchain removal failed (entry already removed from memory) | %s",
                exc,
            )

    logger.warning("remove_threat | threat_id=%s | device=%s", threat_id, removed.device_id)
    return removed


def get_threat(threat_id: str) -> ThreatEntry:
    """
    Retrieve a threat entry by ID.

    Raises:
        KeyError: If the threat ID does not exist.
    """
    with _lock:
        entry = _store.get(threat_id)
        if entry is None:
            raise KeyError(f"Threat '{threat_id}' not found in threat intelligence store.")
        return entry


def list_threats(
    status: str | None = None,
    threat_type: str | None = None,
    min_risk_score: int = 0,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """
    List threat entries, optionally filtered.

    Args:
        status:          Filter by status (ACTIVE | INVESTIGATING | RESOLVED | REVOKED).
        threat_type:     Filter by type (DEVICE | IOC | SIGNATURE | …).
        min_risk_score:  Minimum risk score to include (0–100).
        limit:           Maximum entries to return.

    Returns:
        List of ThreatEntry dicts sorted by risk_score descending.
    """
    with _lock:
        entries = list(_store.values())

    if status:
        entries = [e for e in entries if e.status == status]
    if threat_type:
        entries = [e for e in entries if e.threat_type == threat_type]
    entries = [e for e in entries if e.risk_score >= min_risk_score]

    entries.sort(key=lambda e: e.risk_score, reverse=True)
    return [e.to_dict() for e in entries[:limit]]


def get_attack_statistics() -> dict[str, Any]:
    """Return aggregated attack statistics across all threat entries."""
    with _lock:
        entries = list(_store.values())

    if not entries:
        return {
            "total_threats": 0,
            "active_threats": 0,
            "on_chain_threats": 0,
            "avg_risk_score": 0,
            "avg_threat_level": 0,
            "by_type": {},
            "by_category": {},
            "by_status": {},
            "high_risk_count": 0,
        }

    by_type: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_status: dict[str, int] = {}

    for e in entries:
        by_type[e.threat_type] = by_type.get(e.threat_type, 0) + 1
        by_category[e.threat_category] = by_category.get(e.threat_category, 0) + 1
        by_status[e.status] = by_status.get(e.status, 0) + 1

    return {
        "total_threats": len(entries),
        "active_threats": sum(1 for e in entries if e.status == STATUS_ACTIVE),
        "on_chain_threats": sum(1 for e in entries if e.on_chain),
        "avg_risk_score": round(sum(e.risk_score for e in entries) / len(entries), 1),
        "avg_threat_level": round(sum(e.threat_level for e in entries) / len(entries), 1),
        "by_type": by_type,
        "by_category": by_category,
        "by_status": by_status,
        "high_risk_count": sum(1 for e in entries if e.risk_score >= 80),
    }
