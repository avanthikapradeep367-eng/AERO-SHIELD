"""
AERO-SHIELD X — Dashboard API Router Assembly

Mounts all dashboard sub-routers under their prefixes:

    /dashboard/*    — overview, transactions, incidents, devices
    /analytics/*    — chart data, statistics
    /timeline/*     — event timeline
    /system/*       — health probes
"""

from fastapi import APIRouter

from .dashboard import router as _dashboard_router
from .analytics import router as _analytics_router
from .timeline  import router as _timeline_router
from .health    import router as _health_router

dashboard_api_router  = APIRouter(prefix="/dashboard")
analytics_api_router  = APIRouter(prefix="/analytics")
timeline_api_router   = APIRouter(prefix="/timeline")
system_api_router     = APIRouter(prefix="/system")

dashboard_api_router.include_router(_dashboard_router)
analytics_api_router.include_router(_analytics_router)
timeline_api_router.include_router(_timeline_router)
system_api_router.include_router(_health_router)
