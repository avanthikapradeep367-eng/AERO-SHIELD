"""
AERO-SHIELD X — Threat Intelligence REST API

Routes (prefixed /threat by router.py):
    POST   /threat/publish          — publish a new threat IOC
    PUT    /threat/update           — update an existing threat entry
    GET    /threat/list             — list all threats (filterable)
    GET    /threat/stats            — aggregated attack statistics
    DELETE /threat/remove/{id}      — remove a threat entry
    GET    /threat/{id}             — get a specific threat by ID

IMPORTANT route ordering: /threat/list and /threat/stats MUST be declared
BEFORE /threat/{id} to prevent literal paths from being swallowed by the
parameterised route.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Request, Query
from fastapi.responses import JSONResponse

from app.core.logger import get_logger
from app.forensics import threat_intelligence as ti
from app.schemas.forensics import PublishThreatRequest, UpdateThreatRequest
from app.blockchain.utils import now_iso

logger = get_logger("api.forensics.threat_intelligence")

router = APIRouter(tags=["Threat Intelligence"])


# ── Helpers ─────────────────────────────────────────────────────────────────────

def _ok(message: str, data: dict | None = None, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "timestamp": now_iso(),
            "verificationStatus": None,
            "blockchainHash": None,
            "currentHash": None,
            "transactionHash": data.get("blockchain_tx") if data else None,
            "data": data,
        },
    )


def _err(message: str, code: str, details: dict | None = None, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message, "errorCode": code, "details": details},
    )


# ── POST /threat/publish ────────────────────────────────────────────────────────

@router.post(
    "/publish",
    summary="Publish a threat intelligence entry",
    description=(
        "Publish a new threat IOC to the Threat Intelligence Engine. "
        "For DEVICE-type threats, also blacklists the device on the immutable Ethereum ledger "
        "when ``publish_to_blockchain=true``. Supports IOC patterns, attack signatures, "
        "replay attack detection, and custom threat categories."
    ),
    responses={
        201: {"description": "Threat published successfully"},
        422: {"description": "Validation error (threat_level/risk_score out of range, unknown type)"},
        503: {"description": "Blockchain node unreachable (threat still stored in-memory)"},
    },
)
def publish_threat(
    request: Request,
    payload: PublishThreatRequest,
) -> JSONResponse:
    """
    Publish a new threat.

    **curl example:**
    ```bash
    curl -X POST http://localhost:8000/threat/publish \\
      -H "Content-Type: application/json" \\
      -d '{
        "device_id": "UAV-ALPHA-001",
        "threat_type": "DEVICE",
        "threat_level": 8,
        "risk_score": 95,
        "threat_category": "GPS_SPOOFING",
        "attack_signatures": ["sig-001", "sig-002"],
        "ioc_patterns": ["0xdeadbeef"],
        "description": "SentinelX AI detected GPS spoofing attack",
        "published_by": "SENTINELX-AI",
        "publish_to_blockchain": true
      }'
    ```
    """
    t0 = time.monotonic()
    logger.warning(
        "POST /threat/publish | ip=%s | device=%s | type=%s | level=%d | risk=%d",
        request.client.host if request.client else "unknown",
        payload.device_id,
        payload.threat_type,
        payload.threat_level,
        payload.risk_score,
    )

    try:
        entry = ti.publish_threat(
            device_id=payload.device_id,
            threat_type=payload.threat_type,
            threat_level=payload.threat_level,
            risk_score=payload.risk_score,
            threat_category=payload.threat_category,
            attack_signatures=payload.attack_signatures,
            ioc_patterns=payload.ioc_patterns,
            description=payload.description,
            published_by=payload.published_by,
            publish_to_blockchain=payload.publish_to_blockchain,
            threat_id=payload.threat_id,
        )

        elapsed = round((time.monotonic() - t0) * 1000, 2)
        logger.warning(
            "threat published | id=%s | device=%s | on_chain=%s | elapsed=%.1fms",
            entry.threat_id, entry.device_id, entry.on_chain, elapsed,
        )

        return _ok(
            message=(
                f"Threat '{entry.threat_id}' published for device '{entry.device_id}' "
                f"(on_chain={entry.on_chain})."
            ),
            data={**entry.to_dict(), "elapsed_ms": elapsed},
            status_code=201,
        )

    except ValueError as exc:
        return _err(str(exc), "ValidationError", status_code=422)
    except Exception as exc:
        logger.exception("Unexpected error in /threat/publish")
        return _err(f"Unexpected error: {exc}", type(exc).__name__, status_code=500)


# ── PUT /threat/update ──────────────────────────────────────────────────────────

@router.put(
    "/update",
    summary="Update a threat intelligence entry",
    description=(
        "Update an existing threat entry's metadata. "
        "Set ``sync_blockchain=true`` to propagate level/score changes to the on-chain profile."
    ),
    responses={
        200: {"description": "Threat updated successfully"},
        404: {"description": "Threat ID not found"},
        422: {"description": "Validation error"},
    },
)
def update_threat(
    request: Request,
    payload: UpdateThreatRequest,
) -> JSONResponse:
    """
    Update an existing threat entry.

    **curl example:**
    ```bash
    curl -X PUT http://localhost:8000/threat/update \\
      -H "Content-Type: application/json" \\
      -d '{"threat_id":"<uuid>","threat_level":9,"risk_score":98,"status":"INVESTIGATING"}'
    ```
    """
    logger.info(
        "PUT /threat/update | ip=%s | threat_id=%s",
        request.client.host if request.client else "unknown",
        payload.threat_id,
    )

    try:
        entry = ti.update_threat(
            threat_id=payload.threat_id,
            threat_level=payload.threat_level,
            risk_score=payload.risk_score,
            attack_signatures=payload.attack_signatures,
            ioc_patterns=payload.ioc_patterns,
            threat_category=payload.threat_category,
            description=payload.description,
            status=payload.status,
            attack_count=payload.attack_count,
            sync_blockchain=payload.sync_blockchain,
        )
        return _ok(
            f"Threat '{payload.threat_id}' updated successfully.",
            data=entry.to_dict(),
        )

    except KeyError:
        return _err(
            f"Threat '{payload.threat_id}' not found in the threat intelligence store.",
            "ThreatNotFound",
            status_code=404,
        )
    except ValueError as exc:
        return _err(str(exc), "ValidationError", status_code=422)
    except Exception as exc:
        logger.exception("Unexpected error in /threat/update")
        return _err(f"Unexpected error: {exc}", type(exc).__name__, status_code=500)


# ── GET /threat/list ────────────────────────────────────────────────────────────
# MUST be declared BEFORE /{id} to avoid route shadowing

@router.get(
    "/list",
    summary="List all threat intelligence entries",
    description=(
        "Return threat entries sorted by risk_score descending. "
        "Optionally filter by status, threat_type, or minimum risk score."
    ),
    responses={
        200: {"description": "Threat list returned"},
    },
)
def list_threats(
    request: Request,
    status: str | None = Query(None, description="Filter by status (ACTIVE|INVESTIGATING|RESOLVED)"),
    threat_type: str | None = Query(None, description="Filter by type (DEVICE|IOC|SIGNATURE|…)"),
    min_risk_score: int = Query(0, ge=0, le=100, description="Minimum risk score"),
    limit: int = Query(100, ge=1, le=500, description="Maximum entries to return"),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl "http://localhost:8000/threat/list?status=ACTIVE&min_risk_score=80"
    ```
    """
    logger.info(
        "GET /threat/list | ip=%s | status=%s | type=%s | min_risk=%d",
        request.client.host if request.client else "unknown",
        status, threat_type, min_risk_score,
    )
    entries = ti.list_threats(
        status=status,
        threat_type=threat_type,
        min_risk_score=min_risk_score,
        limit=limit,
    )
    return JSONResponse(
        content={
            "success": True,
            "message": f"Retrieved {len(entries)} threat entry(ies).",
            "timestamp": now_iso(),
            "verificationStatus": None,
            "blockchainHash": None,
            "currentHash": None,
            "transactionHash": None,
            "data": {
                "threats": entries,
                "total": len(entries),
                "filters": {
                    "status": status,
                    "threat_type": threat_type,
                    "min_risk_score": min_risk_score,
                },
            },
        }
    )


# ── GET /threat/stats ────────────────────────────────────────────────────────────
# MUST be declared BEFORE /{id}

@router.get(
    "/stats",
    summary="Get aggregated threat intelligence statistics",
    description="Returns attack counts, average risk scores, distribution by type and category.",
    responses={200: {"description": "Statistics returned"}},
)
def get_threat_stats(request: Request) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/threat/stats
    ```
    """
    logger.info("GET /threat/stats | ip=%s", request.client.host if request.client else "unknown")
    stats = ti.get_attack_statistics()
    return JSONResponse(
        content={
            "success": True,
            "message": "Threat intelligence statistics retrieved.",
            "timestamp": now_iso(),
            "verificationStatus": None,
            "blockchainHash": None,
            "currentHash": None,
            "transactionHash": None,
            "data": stats,
        }
    )


# ── DELETE /threat/remove/{id} ───────────────────────────────────────────────────

@router.delete(
    "/remove/{threatId}",
    summary="Remove a threat entry",
    description=(
        "Remove a threat intelligence entry from the in-memory store. "
        "If the device was blacklisted on-chain, it is also removed from the "
        "blockchain blacklist (unless remove_from_blockchain=false)."
    ),
    responses={
        200: {"description": "Threat removed successfully"},
        404: {"description": "Threat ID not found"},
    },
)
def remove_threat(
    request: Request,
    threatId: str,
    remove_from_blockchain: bool = Query(True, description="Also remove from on-chain blacklist"),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl -X DELETE "http://localhost:8000/threat/remove/<threat-id>?remove_from_blockchain=true"
    ```
    """
    logger.warning(
        "DELETE /threat/remove/%s | ip=%s | remove_blockchain=%s",
        threatId,
        request.client.host if request.client else "unknown",
        remove_from_blockchain,
    )

    try:
        removed = ti.remove_threat(
            threat_id=threatId,
            remove_from_blockchain=remove_from_blockchain,
        )
        return _ok(
            f"Threat '{threatId}' removed successfully (on_chain_removal={remove_from_blockchain and removed.on_chain}).",
            data={**removed.to_dict(), "removed": True},
        )

    except KeyError:
        return _err(
            f"Threat '{threatId}' not found in the threat intelligence store.",
            "ThreatNotFound",
            status_code=404,
        )
    except Exception as exc:
        logger.exception("Unexpected error in /threat/remove")
        return _err(f"Unexpected error: {exc}", type(exc).__name__, status_code=500)


# ── GET /threat/{id} ─────────────────────────────────────────────────────────────
# MUST be declared LAST in this router

@router.get(
    "/{threatId}",
    summary="Get a specific threat by ID",
    description="Retrieve a single threat intelligence entry by its threat_id.",
    responses={
        200: {"description": "Threat entry returned"},
        404: {"description": "Threat ID not found"},
    },
)
def get_threat(
    request: Request,
    threatId: str,
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/threat/<threat-id>
    ```
    """
    logger.info(
        "GET /threat/%s | ip=%s",
        threatId,
        request.client.host if request.client else "unknown",
    )

    try:
        entry = ti.get_threat(threatId)
        return _ok(
            f"Threat '{threatId}' retrieved successfully.",
            data=entry.to_dict(),
        )
    except KeyError:
        return _err(
            f"Threat '{threatId}' not found in the threat intelligence store.",
            "ThreatNotFound",
            status_code=404,
        )
