"""
AERO-SHIELD X — Dashboard Aggregation Service

Aggregates data from all blockchain services into clean, React-ready JSON.

Design principles
-----------------
• All returns are plain Python dicts — no Web3 objects, no bytes, no tuples.
• Thread-safe in-memory cache (30-second TTL) keeps response times <100ms.
• Every method degrades gracefully when the blockchain node is unavailable.
• No new blockchain calls are added — all reads reuse existing service methods.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

from app.blockchain.blockchain_service import BlockchainService
from app.blockchain.services.device_service import DeviceService
from app.blockchain.services.authentication_service import AuthenticationService
from app.blockchain.services.evidence_service import EvidenceService
from app.blockchain.services.threat_service import ThreatService
from app.blockchain.exceptions import BlockchainBaseError
from app.forensics import chain_of_custody, threat_intelligence
from app.core.logger import get_logger

logger = get_logger("dashboard.service")

# ── Simple TTL cache ─────────────────────────────────────────────────────────────
_cache: dict[str, tuple[Any, float]] = {}
_cache_lock = threading.RLock()


def _cache_get(key: str) -> Any | None:
    with _cache_lock:
        entry = _cache.get(key)
        if entry and time.monotonic() < entry[1]:
            return entry[0]
    return None


def _cache_set(key: str, value: Any, ttl: float = 30.0) -> None:
    with _cache_lock:
        _cache[key] = (value, time.monotonic() + ttl)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _safe(fn, default=None):
    """Call fn(); return default on any exception."""
    try:
        return fn()
    except Exception as exc:
        logger.debug("dashboard safe-call failed: %s: %s", type(exc).__name__, exc)
        return default


# ── Overview ─────────────────────────────────────────────────────────────────────

def get_overview() -> dict[str, Any]:
    """
    Aggregate all blockchain counters + node status into a single dashboard card.
    Cached for 30 seconds.
    """
    cached = _cache_get("overview")
    if cached:
        return cached

    t0 = time.monotonic()

    device_svc = DeviceService()
    auth_svc   = AuthenticationService()
    ev_svc     = EvidenceService()
    threat_svc = ThreatService()
    bc_svc     = BlockchainService()

    # ── Blockchain counters ──────────────────────────────────────────────────────
    registered_devices  = _safe(device_svc.total_devices, 0)
    authentication_count = _safe(auth_svc.total_authentications, 0)
    evidence_count       = _safe(ev_svc.total_incidents, 0)
    threat_count         = _safe(threat_svc.total_threat_devices, 0)

    # ── Chain of custody stats ───────────────────────────────────────────────────
    coc_records = _safe(lambda: chain_of_custody.list_records(limit=1000), [])
    verified_evidence = sum(1 for r in coc_records if r.get("current_status") == "VERIFIED")
    tampered_evidence = sum(1 for r in coc_records if r.get("current_status") == "TAMPERED")

    # ── Threat intelligence stats ────────────────────────────────────────────────
    active_threats = _safe(
        lambda: len(threat_intelligence.list_threats(status="ACTIVE")), 0
    )

    # ── Blockchain node ──────────────────────────────────────────────────────────
    node_info: dict[str, Any] = {
        "connected": False,
        "node_status": "unreachable",
        "latest_block": None,
        "chain_id": None,
        "network": "Unknown",
        "wallet_address": None,
        "wallet_balance": "0.000000 ETH",
        "contract_address": None,
        "gas_price": None,
        "rpc_url": None,
    }
    try:
        status = bc_svc.verify_connection()
        chain_id = status.get("chain_id")
        _network_labels = {1337: "Ganache Local", 31337: "Hardhat Local", 1: "Ethereum Mainnet"}
        gas_price_wei = None
        try:
            gas_price_wei = bc_svc.w3.eth.gas_price
        except Exception:
            pass
        node_info = {
            "connected":       bool(status.get("connected")),
            "node_status":     "operational" if status.get("connected") else "unreachable",
            "latest_block":    status.get("block_number"),
            "chain_id":        chain_id,
            "network":         _network_labels.get(chain_id, f"Chain {chain_id}"),
            "wallet_address":  status.get("wallet_address"),
            "wallet_balance":  status.get("wallet_balance", "0 ETH"),
            "contract_address": status.get("contract_address"),
            "gas_price":       f"{gas_price_wei / 1e9:.2f} Gwei" if gas_price_wei else None,
            "rpc_url":         status.get("rpc_url"),
        }
    except BlockchainBaseError as exc:
        logger.warning("overview: blockchain unavailable: %s", exc)

    result = {
        "overview": {
            "registered_devices":   registered_devices,
            "authentication_count": authentication_count,
            "evidence_count":       evidence_count,
            "threat_count":         threat_count,
            "verified_evidence":    verified_evidence,
            "tampered_evidence":    tampered_evidence,
            "active_threats":       active_threats,
            "custody_records":      len(coc_records),
        },
        "blockchain": node_info,
        "elapsed_ms": round((time.monotonic() - t0) * 1000, 2),
    }

    _cache_set("overview", result, ttl=30.0)
    return result


# ── Recent Transactions ──────────────────────────────────────────────────────────

def get_recent_transactions(limit: int = 10) -> list[dict[str, Any]]:
    """
    Assemble a recent-activity feed from the latest blockchain events.
    Returns a unified list sorted newest-first.
    """
    cached = _cache_get(f"recent_tx:{limit}")
    if cached:
        return cached

    transactions: list[dict[str, Any]] = []

    # Latest evidence
    try:
        ev = EvidenceService().latest_incident()
        if ev:
            transactions.append({
                "type":         "EVIDENCE_RECORDED",
                "title":        f"Evidence Sealed — {ev.attack_type}",
                "incident_id":  ev.incident_id,
                "attack_type":  ev.attack_type,
                "risk_score":   ev.risk_score,
                "ai_confidence": ev.ai_confidence,
                "status":       ev.status_label,
                "timestamp":    ev.timestamp_iso,
                "icon":         "shield",
                "severity":     "high" if ev.risk_score >= 80 else "medium" if ev.risk_score >= 50 else "low",
            })
    except Exception:
        pass

    # Latest authentication
    try:
        auth = AuthenticationService().latest_authentication()
        if auth:
            success = getattr(auth, "success", True)
            transactions.append({
                "type":      "AUTHENTICATION",
                "title":     f"Authentication {'SUCCESS' if success else 'FAILED'}",
                "auth_id":   auth.authentication_id,
                "auth_status": "SUCCESS" if success else "FAILED",
                "key_version": auth.rolling_key_version,
                "timestamp": auth.timestamp_iso,
                "icon":      "key",
                "severity":  "low" if success else "high",
            })
    except Exception:
        pass

    # Recent custody events
    try:
        coc_records = chain_of_custody.list_records(limit=5)
        for rec in coc_records:
            if rec.get("verification_history"):
                last = rec["verification_history"][-1]
                transactions.append({
                    "type":       "CUSTODY_EVENT",
                    "title":      f"Custody {last.get('event_type', 'UPDATE')} — {last.get('status', '')}",
                    "evidence_id": rec.get("evidence_id", ""),
                    "status":     last.get("status", ""),
                    "actor":      last.get("actor", "SYSTEM"),
                    "timestamp":  last.get("timestamp", ""),
                    "icon":       "document",
                    "severity":   "critical" if last.get("status") == "TAMPERED" else "low",
                })
    except Exception:
        pass

    # Sort newest first by timestamp
    transactions.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    result = transactions[:limit]
    _cache_set(f"recent_tx:{limit}", result, ttl=15.0)
    return result


# ── Recent Incidents ─────────────────────────────────────────────────────────────

def get_recent_incidents(limit: int = 10) -> list[dict[str, Any]]:
    """Return recent security incidents from the Evidence Vault."""
    cached = _cache_get(f"recent_incidents:{limit}")
    if cached:
        return cached

    incidents: list[dict[str, Any]] = []
    try:
        total = EvidenceService().total_incidents()
        if total > 0:
            ev = EvidenceService().latest_incident()
            if ev:
                d = ev.to_dict()
                d["risk_badge"] = "CRITICAL" if d["risk_score"] >= 90 else "HIGH" if d["risk_score"] >= 70 else "MEDIUM" if d["risk_score"] >= 50 else "LOW"
                incidents.append(d)
    except Exception as exc:
        logger.debug("get_recent_incidents: %s", exc)

    _cache_set(f"recent_incidents:{limit}", incidents, ttl=15.0)
    return incidents


# ── Recent Authentication ─────────────────────────────────────────────────────────

def get_recent_authentication(limit: int = 10) -> list[dict[str, Any]]:
    """Return recent authentication events."""
    cached = _cache_get(f"recent_auth:{limit}")
    if cached:
        return cached

    auth_records: list[dict[str, Any]] = []
    try:
        auth = AuthenticationService().latest_authentication()
        if auth:
            d = auth.to_dict()
            d["success_label"] = "SUCCESS" if d.get("success") else "FAILED"
            auth_records.append(d)
    except Exception as exc:
        logger.debug("get_recent_authentication: %s", exc)

    _cache_set(f"recent_auth:{limit}", auth_records, ttl=15.0)
    return auth_records


# ── Threat Feed ──────────────────────────────────────────────────────────────────

def get_threat_feed(limit: int = 20) -> list[dict[str, Any]]:
    """
    Merge in-memory threat intelligence entries with on-chain threat profiles.
    Returns an enriched threat feed sorted by risk_score descending.
    """
    cached = _cache_get(f"threat_feed:{limit}")
    if cached:
        return cached

    feed: list[dict[str, Any]] = []

    # In-memory threat intelligence
    try:
        entries = threat_intelligence.list_threats(limit=limit)
        for e in entries:
            e["source"] = "threat_intelligence"
            e["risk_badge"] = (
                "CRITICAL" if e.get("risk_score", 0) >= 90
                else "HIGH" if e.get("risk_score", 0) >= 70
                else "MEDIUM" if e.get("risk_score", 0) >= 50
                else "LOW"
            )
            feed.append(e)
    except Exception:
        pass

    # On-chain threat profiles for all registered devices (up to 5)
    try:
        device_ids = DeviceService().get_registered_devices()
        threat_svc = ThreatService()
        for did in device_ids[:5]:
            try:
                profile = threat_svc.get_threat_profile(did)
                if profile.blacklisted:
                    d = profile.to_dict()
                    d["device_id"] = did
                    d["source"] = "blockchain"
                    d["risk_badge"] = "CRITICAL" if d["risk_score"] >= 90 else "HIGH" if d["risk_score"] >= 70 else "MEDIUM"
                    feed.append(d)
            except Exception:
                pass
    except Exception:
        pass

    feed.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
    result = feed[:limit]
    _cache_set(f"threat_feed:{limit}", result, ttl=15.0)
    return result


# ── Device Status ─────────────────────────────────────────────────────────────────

def get_device_status(limit: int = 20) -> list[dict[str, Any]]:
    """
    Return status for all registered devices (up to limit).
    Each entry is enriched with on-chain data and threat status.
    """
    cached = _cache_get(f"device_status:{limit}")
    if cached:
        return cached

    devices: list[dict[str, Any]] = []
    try:
        device_svc  = DeviceService()
        threat_svc  = ThreatService()
        device_ids  = device_svc.get_registered_devices()

        for did in device_ids[:limit]:
            try:
                rec  = device_svc.get_device(did)
                d    = rec.to_dict()
                d["blacklisted"]   = _safe(lambda: threat_svc.is_blacklisted(did), False)
                d["status_label"]  = "ACTIVE" if d["active"] else "INACTIVE"
                d["threat_badge"]  = "BLACKLISTED" if d["blacklisted"] else "CLEAN"
                devices.append(d)
            except Exception:
                pass
    except Exception as exc:
        logger.debug("get_device_status: %s", exc)

    _cache_set(f"device_status:{limit}", devices, ttl=30.0)
    return devices


# ── Cache control ─────────────────────────────────────────────────────────────────

def invalidate_cache() -> None:
    """Clear the entire dashboard cache (call after write operations)."""
    with _cache_lock:
        _cache.clear()
    logger.debug("Dashboard cache invalidated")
