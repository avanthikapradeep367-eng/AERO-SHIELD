"""
AERO-SHIELD X — Timeline API Routes

GET /timeline
GET /timeline/custody
GET /timeline/threats
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.dashboard import timeline as tl
from app.forensics import chain_of_custody, threat_intelligence

router = APIRouter(tags=["Timeline"])


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@router.get("/")
def get_timeline(limit: int = Query(50, ge=1, le=200)):
    """
    Unified chronological event timeline from all platform sources.
    Sorted newest-first. Each event: time, title, description, status, type, severity, icon.
    """
    events = tl.get_timeline(limit=limit)
    return {
        "success":   True,
        "message":   f"{len(events)} timeline events retrieved",
        "timestamp": _now(),
        "count":     len(events),
        "events":    events,
    }


@router.get("/custody")
def get_custody_timeline(limit: int = Query(50, ge=1, le=200)):
    """Chain-of-custody event timeline (forensics layer only)."""
    records = chain_of_custody.list_records(limit=limit)
    events: list[dict[str, Any]] = []
    for rec in records:
        for evt in rec.get("verification_history", []):
            events.append({
                "time":        evt.get("timestamp", ""),
                "title":       f"Custody {evt.get('event_type', 'UPDATE')}",
                "description": evt.get("notes", ""),
                "status":      evt.get("status", ""),
                "type":        "CUSTODY",
                "evidence_id": rec.get("evidence_id"),
                "actor":       evt.get("actor"),
            })
    events.sort(key=lambda x: x.get("time", ""), reverse=True)
    events = events[:limit]
    return {
        "success":   True,
        "message":   f"{len(events)} custody events retrieved",
        "timestamp": _now(),
        "count":     len(events),
        "events":    events,
    }


@router.get("/threats")
def get_threat_timeline(limit: int = Query(50, ge=1, le=200)):
    """Threat intelligence timeline — all published threat entries newest-first."""
    threats = threat_intelligence.list_threats(limit=limit)
    events = [
        {
            "time":        t.get("published_at", ""),
            "title":       f"Threat Published — {t.get('threat_category', 'UNKNOWN')}",
            "description": t.get("description", ""),
            "status":      t.get("status", ""),
            "type":        "THREAT",
            "threat_id":   t.get("threat_id"),
            "device_id":   t.get("device_id"),
            "risk_score":  t.get("risk_score"),
            "on_chain":    t.get("on_chain"),
        }
        for t in threats
    ]
    events.sort(key=lambda x: x.get("time", ""), reverse=True)
    return {
        "success":   True,
        "message":   f"{len(events)} threat events retrieved",
        "timestamp": _now(),
        "count":     len(events),
        "events":    events,
    }
