"""
AERO-SHIELD X — Dashboard Pydantic Schemas
"""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel


class DashboardResponse(BaseModel):
    success: bool = True
    message: str
    timestamp: str
    data: dict[str, Any] | list[Any]


class OverviewResponse(BaseModel):
    success: bool = True
    message: str
    timestamp: str
    overview: dict[str, Any]
    blockchain: dict[str, Any]
    elapsed_ms: float


class ChartResponse(BaseModel):
    success: bool = True
    message: str
    timestamp: str
    chart_type: str
    title: str
    labels: list[Any]
    datasets: list[dict[str, Any]]
    summary: dict[str, Any]


class TimelineResponse(BaseModel):
    success: bool = True
    message: str
    timestamp: str
    count: int
    events: list[dict[str, Any]]


class HealthResponse(BaseModel):
    success: bool
    message: str
    timestamp: str
    overall_status: Literal["HEALTHY", "DEGRADED", "CRITICAL"]
    components: list[dict[str, Any]]
    summary: dict[str, int]
    elapsed_ms: float


class KPIResponse(BaseModel):
    success: bool = True
    message: str
    timestamp: str
    kpis: dict[str, Any]
