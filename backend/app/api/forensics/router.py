"""
AERO-SHIELD X — Forensics API Router

Assembles all forensics sub-routers under their respective prefixes:

    /forensics/hash                      ← evidence_verification.py
    /forensics/verify                    ← evidence_verification.py
    /forensics/report                    ← evidence_verification.py
    /forensics/history/{evidenceId}      ← evidence_verification.py
    /forensics/custody/*                 ← chain_of_custody.py
    /threat/publish                      ← threat_intelligence.py
    /threat/update                       ← threat_intelligence.py
    /threat/list                         ← threat_intelligence.py
    /threat/stats                        ← threat_intelligence.py
    /threat/remove/{id}                  ← threat_intelligence.py
    /threat/{id}                         ← threat_intelligence.py
"""

from __future__ import annotations

from fastapi import APIRouter

from .evidence_verification import router as evidence_router
from .chain_of_custody import router as custody_router
from .threat_intelligence import router as threat_router

# ── /forensics/* ────────────────────────────────────────────────────────────────
forensics_router = APIRouter(prefix="/forensics")
forensics_router.include_router(evidence_router)
forensics_router.include_router(custody_router)

# ── /threat/* ───────────────────────────────────────────────────────────────────
threat_api_router = APIRouter(prefix="/threat")
threat_api_router.include_router(threat_router)
