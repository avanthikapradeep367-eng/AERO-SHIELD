"""
AERO-SHIELD X — Dashboard API Routes

GET /dashboard/overview
GET /dashboard/recent-transactions
GET /dashboard/recent-incidents
GET /dashboard/recent-authentication
GET /dashboard/threat-feed
GET /dashboard/device-status
GET /dashboard/kpis
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.dashboard import dashboard_service as svc
from app.dashboard import statistics as stats

router = APIRouter(tags=["Dashboard"])


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _ok(message: str, **kwargs: Any) -> dict[str, Any]:
    return {"success": True, "message": message, "timestamp": _now(), **kwargs}


@router.get("/overview")
def get_overview():
    """Aggregated platform overview — device counts, blockchain node status, custody stats."""
    data = svc.get_overview()
    return _ok("Dashboard overview retrieved", **data)


@router.get("/recent-transactions")
def get_recent_transactions(limit: int = Query(10, ge=1, le=50)):
    """Recent blockchain events: evidence recordings, authentications, custody updates."""
    data = svc.get_recent_transactions(limit=limit)
    return _ok(f"{len(data)} recent transactions retrieved", transactions=data, count=len(data))


@router.get("/recent-incidents")
def get_recent_incidents(limit: int = Query(10, ge=1, le=50)):
    """Recent security incidents from the Evidence Vault."""
    data = svc.get_recent_incidents(limit=limit)
    return _ok(f"{len(data)} recent incidents retrieved", incidents=data, count=len(data))


@router.get("/recent-authentication")
def get_recent_authentication(limit: int = Query(10, ge=1, le=50)):
    """Recent authentication events from the Authentication Ledger."""
    data = svc.get_recent_authentication(limit=limit)
    return _ok(f"{len(data)} authentication events retrieved", authentications=data, count=len(data))


@router.get("/threat-feed")
def get_threat_feed(limit: int = Query(20, ge=1, le=100)):
    """Merged threat feed: in-memory threat intelligence + on-chain blacklisted device profiles."""
    data = svc.get_threat_feed(limit=limit)
    return _ok(f"{len(data)} threat entries retrieved", threats=data, count=len(data))


@router.get("/device-status")
def get_device_status(limit: int = Query(20, ge=1, le=100)):
    """Registered device status with blacklist and health badges."""
    data = svc.get_device_status(limit=limit)
    return _ok(f"{len(data)} device records retrieved", devices=data, count=len(data))


@router.get("/kpis")
def get_kpis():
    """Platform KPIs — threat counts, integrity score, health badge, auth stats."""
    data = stats.compute_platform_kpis()
    return _ok("Platform KPIs computed", kpis=data)
