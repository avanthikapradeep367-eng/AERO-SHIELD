"""
AERO-SHIELD X — Statistics & KPI Engine

Computes aggregated KPIs and summary statistics across all platform data.
Used by both the dashboard cards and the analytics endpoints.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

from app.blockchain.services.device_service import DeviceService
from app.blockchain.services.evidence_service import EvidenceService
from app.blockchain.services.threat_service import ThreatService
from app.blockchain.services.authentication_service import AuthenticationService
from app.forensics import threat_intelligence, chain_of_custody
from app.core.logger import get_logger

logger = get_logger("dashboard.statistics")

_cache: dict[str, tuple[Any, float]] = {}
_lock = threading.RLock()


def _cget(k: str) -> Any | None:
    with _lock:
        e = _cache.get(k)
        if e and time.monotonic() < e[1]:
            return e[0]
    return None


def _cset(k: str, v: Any, ttl: float = 60.0) -> None:
    with _lock:
        _cache[k] = (v, time.monotonic() + ttl)


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def compute_platform_kpis() -> dict[str, Any]:
    """
    Compute all platform KPIs in a single pass.
    Returns a dict suitable for the /analytics/overview endpoint.
    Cached for 60 seconds.
    """
    if r := _cget("platform_kpis"):
        return r

    devices       = _safe(DeviceService().total_devices, 0)
    incidents     = _safe(EvidenceService().total_incidents, 0)
    threats       = _safe(ThreatService().total_threat_devices, 0)
    authentications = _safe(AuthenticationService().total_authentications, 0)

    # Threat intel stats
    ti_stats = _safe(threat_intelligence.get_attack_statistics, {})
    active_threats     = ti_stats.get("active_threats", 0)
    avg_risk_score     = ti_stats.get("avg_risk_score", 0)
    avg_threat_level   = ti_stats.get("avg_threat_level", 0)
    on_chain_threats   = ti_stats.get("on_chain_threats", 0)
    high_risk_count    = ti_stats.get("high_risk_count", 0)

    # Chain of custody
    coc_records = _safe(lambda: chain_of_custody.list_records(limit=1000), [])
    verified   = sum(1 for r in coc_records if r.get("current_status") == "VERIFIED")
    tampered   = sum(1 for r in coc_records if r.get("current_status") == "TAMPERED")
    integrity_pct = round(verified / len(coc_records) * 100, 1) if coc_records else 100.0

    result = {
        # --- Platform counters
        "registered_devices":    devices,
        "total_incidents":       incidents,
        "total_threats":         threats,
        "total_authentications": authentications,
        # --- Threat intelligence
        "active_threats":        active_threats,
        "on_chain_threats":      on_chain_threats,
        "high_risk_threats":     high_risk_count,
        "avg_risk_score":        avg_risk_score,
        "avg_threat_level":      avg_threat_level,
        # --- Evidence integrity
        "verified_evidence":     verified,
        "tampered_evidence":     tampered,
        "integrity_score":       integrity_pct,
        "custody_records":       len(coc_records),
        # --- Summary badges
        "platform_health": (
            "CRITICAL" if tampered > 0 or active_threats > 2
            else "WARNING" if active_threats > 0 or avg_risk_score >= 70
            else "HEALTHY"
        ),
        "computed_at": _now_iso(),
    }

    _cset("platform_kpis", result)
    return result


def compute_threat_stats() -> dict[str, Any]:
    """Threat-focused statistics (by_type, by_category, by_status counts)."""
    if r := _cget("threat_stats"):
        return r
    stats = _safe(threat_intelligence.get_attack_statistics, {
        "total_threats": 0, "by_type": {}, "by_category": {}, "by_status": {}
    })
    _cset("threat_stats", stats)
    return stats


def compute_device_stats() -> dict[str, Any]:
    """Device registry statistics."""
    if r := _cget("device_stats"):
        return r

    total = _safe(DeviceService().total_devices, 0)
    device_ids = _safe(DeviceService().get_registered_devices, [])
    active_count = 0
    type_distribution: dict[str, int] = {}

    for did in device_ids[:20]:
        try:
            rec = DeviceService().get_device(did)
            if rec.active:
                active_count += 1
            type_distribution[rec.device_type] = type_distribution.get(rec.device_type, 0) + 1
        except Exception:
            pass

    result = {
        "total": total,
        "active": active_count,
        "inactive": total - active_count,
        "type_distribution": type_distribution,
    }
    _cset("device_stats", result)
    return result
