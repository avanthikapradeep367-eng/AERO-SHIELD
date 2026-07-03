"""
api/blockchain/router.py — Main blockchain API router for AERO-SHIELD X.

Assembles all five blockchain sub-routers under the /blockchain prefix and
exposes a single `router` object that main.py registers on the FastAPI app.

Route map:
    /blockchain/health                   ← health.py
    /blockchain/device/...               ← device.py
    /blockchain/authentication/...       ← authentication.py
    /blockchain/evidence/...             ← evidence.py
    /blockchain/threat/...               ← threat.py
"""

from __future__ import annotations

from fastapi import APIRouter

from .device         import router as device_router
from .authentication import router as auth_router
from .evidence       import router as evidence_router
from .threat         import router as threat_router
from .health         import router as health_router

# ── Main blockchain router ──────────────────────────────────────────────────────
# All routes live under /blockchain.  Sub-routers add their own sub-prefix.

router = APIRouter(prefix="/blockchain")

# Health check — no sub-prefix (resolves to /blockchain/health)
router.include_router(health_router)

# Domain sub-routers
router.include_router(device_router,  prefix="/device")
router.include_router(auth_router,    prefix="/authentication")
router.include_router(evidence_router, prefix="/evidence")
router.include_router(threat_router,  prefix="/threat")
