"""
AERO-SHIELD X — System Health API Routes

GET /system/health          — Full component health check
GET /system/health/summary  — Overall status only (fast, for load balancers)
GET /system/health/live     — Liveness probe (always 200 if API is running)
GET /system/health/ready    — Readiness probe (200 only if blockchain is connected)
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Response

from app.dashboard import health_monitor as hm

router = APIRouter(tags=["System Health"])


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@router.get("/health")
def full_health_check():
    """
    Full system health check — runs all component checks concurrently.
    Returns per-component status: ONLINE | DEGRADED | OFFLINE | UNKNOWN
    """
    report = hm.check_all()
    return {
        "success":        report["overall_status"] != "CRITICAL",
        "message":        f"System status: {report['overall_status']}",
        "timestamp":      _now(),
        "overall_status": report["overall_status"],
        "components":     report["components"],
        "summary":        report["summary"],
        "elapsed_ms":     report["elapsed_ms"],
    }


@router.get("/health/summary")
def health_summary():
    """Quick overall status badge — optimised for dashboard header chips."""
    report = hm.check_all()
    return {
        "success":        True,
        "overall_status": report["overall_status"],
        "summary":        report["summary"],
        "timestamp":      _now(),
    }


@router.get("/health/live")
def liveness_probe(response: Response):
    """
    Kubernetes/Docker liveness probe.
    Always returns 200 as long as the FastAPI process is running.
    """
    return {"status": "alive", "timestamp": _now()}


@router.get("/health/ready")
def readiness_probe(response: Response):
    """
    Kubernetes/Docker readiness probe.
    Returns 200 only when the blockchain node is connected and the contract is loaded.
    """
    report = hm.check_all()
    components = {c["component"]: c["status"] for c in report.get("components", [])}

    blockchain_ok = components.get("blockchain") == "ONLINE"
    contract_ok   = components.get("contract")   == "ONLINE"

    if blockchain_ok and contract_ok:
        return {"status": "ready", "timestamp": _now()}

    response.status_code = 503
    return {
        "status":     "not_ready",
        "timestamp":  _now(),
        "reason":     "Blockchain or contract unavailable",
        "blockchain": components.get("blockchain", "UNKNOWN"),
        "contract":   components.get("contract",   "UNKNOWN"),
    }
