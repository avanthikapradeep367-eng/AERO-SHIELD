"""
AERO-SHIELD X — Analytics API Routes

GET /analytics/device-growth
GET /analytics/incident-growth
GET /analytics/threat-distribution
GET /analytics/authentication-success
GET /analytics/risk-distribution
GET /analytics/activity-heatmap
GET /analytics/statistics
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.dashboard import analytics as an
from app.dashboard import statistics as stats

router = APIRouter(tags=["Analytics"])


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _chart(title: str, chart_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "success":    True,
        "message":    f"{title} chart data retrieved",
        "timestamp":  _now(),
        "chart_type": chart_data.get("chart_type", "unknown"),
        "title":      chart_data.get("title", title),
        "labels":     chart_data.get("labels", []),
        "datasets":   chart_data.get("datasets", []),
        "summary":    chart_data.get("summary", {}),
    }


@router.get("/device-growth")
def device_growth(days: int = Query(7, ge=1, le=30)):
    """Bar + line chart: device registration growth over the specified number of days."""
    return _chart("Device Growth", an.device_growth_chart(days=days))


@router.get("/incident-growth")
def incident_growth(days: int = Query(7, ge=1, le=30)):
    """Area chart: security incident growth over the specified number of days."""
    return _chart("Incident Growth", an.incident_growth_chart(days=days))


@router.get("/threat-distribution")
def threat_distribution():
    """Doughnut chart: threats broken down by attack category."""
    return _chart("Threat Distribution", an.threat_distribution_chart())


@router.get("/authentication-success")
def authentication_success():
    """Pie chart: authentication success vs failure rate."""
    return _chart("Authentication Success Rate", an.authentication_success_chart())


@router.get("/risk-distribution")
def risk_distribution():
    """Horizontal bar chart: threats grouped by risk level (CRITICAL/HIGH/MEDIUM/LOW)."""
    return _chart("Risk Distribution", an.risk_distribution_chart())


@router.get("/activity-heatmap")
def activity_heatmap():
    """
    Heatmap: activity intensity by day-of-week × hour-of-day.
    Returns 7×24 matrix of event counts.
    """
    data = an.activity_heatmap()
    return {
        "success":   True,
        "message":   "Activity heatmap retrieved",
        "timestamp": _now(),
        "chart_type": "heatmap",
        "title":     data.get("title", "Activity Heatmap"),
        "x_labels":  data.get("x_labels", []),
        "y_labels":  data.get("y_labels", []),
        "data":      data.get("data", []),
        "summary":   data.get("summary", {}),
    }


@router.get("/statistics")
def get_statistics():
    """All platform statistics: KPIs, threat stats, device stats."""
    return {
        "success":      True,
        "message":      "Platform statistics retrieved",
        "timestamp":    _now(),
        "platform_kpis":  stats.compute_platform_kpis(),
        "threat_stats":   stats.compute_threat_stats(),
        "device_stats":   stats.compute_device_stats(),
    }
