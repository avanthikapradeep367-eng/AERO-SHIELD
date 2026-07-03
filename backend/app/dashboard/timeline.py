"""
AERO-SHIELD X — Event Timeline Assembler

Aggregates events from all platform sources into a unified chronological feed
suitable for the React dashboard timeline component.

Each TimelineEvent has:
    time        — ISO-8601 timestamp
    title       — human-readable event title
    description — optional detail text
    status      — Blocked | Detected | Verified | Registered | Failed | Resolved
    type        — INCIDENT | AUTHENTICATION | DEVICE | THREAT | CUSTODY | SYSTEM
    severity    — critical | high | medium | low | info
    icon        — shield | key | device | alert | document | check
    data        — optional extra dict
"""

from __future__ import annotations

import threading
import time
from typing import Any

from app.blockchain.services.evidence_service import EvidenceService
from app.blockchain.services.authentication_service import AuthenticationService
from app.forensics import chain_of_custody, threat_intelligence
from app.core.logger import get_logger

logger = get_logger("dashboard.timeline")

_cache: dict[str, tuple[Any, float]] = {}
_lock = threading.RLock()


def _cget(k: str) -> Any | None:
    with _lock:
        e = _cache.get(k)
        if e and time.monotonic() < e[1]:
            return e[0]
    return None


def _cset(k: str, v: Any, ttl: float = 15.0) -> None:
    with _lock:
        _cache[k] = (v, time.monotonic() + ttl)


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _severity(risk_score: int) -> str:
    if risk_score >= 90:
        return "critical"
    if risk_score >= 70:
        return "high"
    if risk_score >= 50:
        return "medium"
    return "low"


def get_timeline(limit: int = 50) -> list[dict[str, Any]]:
    """
    Assemble a unified event timeline from all platform sources.

    Sources:
        1. Chain-of-custody events (forensics layer)
        2. Latest blockchain incident (Evidence Vault)
        3. Latest authentication event (Authentication Ledger)
        4. In-memory threat intelligence entries

    Returns:
        List of TimelineEvent dicts sorted newest-first, up to ``limit``.
    """
    if r := _cget(f"timeline:{limit}"):
        return r

    events: list[dict[str, Any]] = []

    # ── 1. Chain-of-custody events ───────────────────────────────────────────────
    try:
        records = chain_of_custody.list_records(limit=200)
        for rec in records:
            for evt in rec.get("verification_history", []):
                status = evt.get("status", "")
                severity = "critical" if status == "TAMPERED" else "low" if status == "VERIFIED" else "medium"
                events.append({
                    "time":        evt.get("timestamp", ""),
                    "title":       f"Evidence {evt.get('event_type', 'UPDATE')} — {status}",
                    "description": f"Evidence '{rec.get('evidence_id', '')[:20]}…' — {evt.get('notes', '')}",
                    "status":      status,
                    "type":        "CUSTODY",
                    "severity":    severity,
                    "icon":        "document",
                    "data": {
                        "evidence_id":  rec.get("evidence_id"),
                        "actor":        evt.get("actor"),
                        "event_id":     evt.get("event_id"),
                    },
                })
    except Exception:
        pass

    # ── 2. Latest blockchain incident ────────────────────────────────────────────
    try:
        ev = EvidenceService().latest_incident()
        if ev:
            events.append({
                "time":        ev.timestamp_iso,
                "title":       f"Incident Detected — {ev.attack_type}",
                "description": f"Risk {ev.risk_score}% | AI Confidence {ev.ai_confidence}% | {ev.action_taken}",
                "status":      "Blocked" if "QUARANTINE" in ev.action_taken else "Detected",
                "type":        "INCIDENT",
                "severity":    _severity(ev.risk_score),
                "icon":        "shield",
                "data":        ev.to_dict(),
            })
    except Exception:
        pass

    # ── 3. Latest authentication event ──────────────────────────────────────────
    try:
        auth = AuthenticationService().latest_authentication()
        if auth:
            success = getattr(auth, "success", True)
            events.append({
                "time":        auth.timestamp_iso,
                "title":       f"Authentication {'Verified' if success else 'Failed'}",
                "description": f"Key version {auth.rolling_key_version} — {'SUCCESS' if success else 'FAILED'}",
                "status":      "Verified" if success else "Failed",
                "type":        "AUTHENTICATION",
                "severity":    "low" if success else "high",
                "icon":        "key",
                "data":        auth.to_dict(),
            })
    except Exception:
        pass

    # ── 4. Threat intelligence entries ───────────────────────────────────────────
    try:
        threats = threat_intelligence.list_threats(limit=20)
        for t in threats:
            events.append({
                "time":        t.get("published_at", ""),
                "title":       f"Threat Published — {t.get('threat_category', 'UNKNOWN')}",
                "description": f"Device {t.get('device_id')} | Level {t.get('threat_level')}/10 | Risk {t.get('risk_score')}%",
                "status":      "Blocked" if t.get("on_chain") else "Detected",
                "type":        "THREAT",
                "severity":    _severity(t.get("risk_score", 0)),
                "icon":        "alert",
                "data": {
                    "threat_id":    t.get("threat_id"),
                    "device_id":    t.get("device_id"),
                    "threat_level": t.get("threat_level"),
                    "risk_score":   t.get("risk_score"),
                    "on_chain":     t.get("on_chain"),
                },
            })
    except Exception:
        pass

    # ── Sort newest first and trim ───────────────────────────────────────────────
    def _ts(ev: dict) -> str:
        return ev.get("time", "") or ""

    events.sort(key=_ts, reverse=True)
    result = events[:limit]
    _cset(f"timeline:{limit}", result)
    return result
