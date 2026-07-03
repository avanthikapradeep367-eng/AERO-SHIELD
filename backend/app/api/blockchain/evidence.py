"""
api/blockchain/evidence.py — Blockchain Evidence Vault REST API (Module 3).

Integration point for Member 3 (SentinelX AI / CUDA detection engine).
When SentinelX detects a security incident, it submits the incident data
and evidence hash here to create an immutable, tamper-evident forensic record.

Routes (all prefixed /blockchain/evidence by router.py):
    POST   /             — record a new security incident and seal its evidence hash
    GET    /count        — total incident count
    GET    /latest       — most recently recorded incident
    GET    /{incidentId} — retrieve a specific incident record

IMPORTANT: /count and /latest MUST be declared before /{incidentId}.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.blockchain.services import EvidenceService
from app.core.logger import get_logger
from app.schemas.evidence import RecordEvidenceRequest
from .dependencies import (
    get_evidence_service,
    success_response,
    tx_success_response,
    blockchain_error_json,
)

logger = get_logger("api.blockchain.evidence")

router = APIRouter(tags=["Blockchain — Evidence Vault"])


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post(
    "/",
    summary="Record a security incident and seal its evidence hash on-chain",
    description=(
        "Anchors a security incident to the EvidenceVault by sealing its evidence hash "
        "immutably on-chain. Once committed, the hash cannot be altered — any tampering "
        "with the original evidence file is detectable via the /verify endpoint. "
        "The incident_id must be globally unique."
    ),
    response_description="Incident recorded and evidence hash sealed on-chain.",
    responses={
        201: {"description": "Incident recorded successfully"},
        409: {"description": "Duplicate incident_id already on-chain (DuplicateIncidentError)"},
        422: {"description": "Validation error (invalid risk scores, contract revert)"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def record_evidence(
    request: Request,
    payload: RecordEvidenceRequest,
    service: EvidenceService = Depends(get_evidence_service),
) -> JSONResponse:
    """
    Seal a forensic evidence record on-chain.

    **curl example:**
    ```bash
    curl -X POST http://localhost:8000/blockchain/evidence \\
      -H "Content-Type: application/json" \\
      -d '{
        "incident_id": "0xdeadbeef...",
        "attack_type": "GPS_SPOOFING",
        "source_device": "UAV-ALPHA-001",
        "target_device": "GROUND-GCS-001",
        "risk_score": 87,
        "ai_confidence": 94,
        "action_taken": "QUARANTINE_ISSUED",
        "evidence_hash": "0xe3b0c44..."
      }'
    ```

    **Python requests example:**
    ```python
    import requests
    resp = requests.post(
        "http://localhost:8000/blockchain/evidence",
        json={
            "incident_id": "0xdeadbeef...",
            "attack_type": "GPS_SPOOFING",
            "source_device": "UAV-ALPHA-001",
            "target_device": "GROUND-GCS-001",
            "risk_score": 87,
            "ai_confidence": 94,
            "action_taken": "QUARANTINE_ISSUED",
            "evidence_hash": "0xe3b0c44...",
        },
    )
    print(resp.json())
    ```
    """
    t0 = time.monotonic()
    logger.info(
        "POST /blockchain/evidence | ip=%s | incident_id=%s | attack=%s | risk=%d",
        request.client.host if request.client else "unknown",
        payload.incident_id,
        payload.attack_type,
        payload.risk_score,
    )
    try:
        result = service.record_incident(
            incident_id=payload.incident_id,
            attack_type=payload.attack_type,
            source_device=payload.source_device,
            target_device=payload.target_device,
            risk_score=payload.risk_score,
            ai_confidence=payload.ai_confidence,
            action_taken=payload.action_taken,
            evidence_hash=payload.evidence_hash,
        )
        elapsed = round((time.monotonic() - t0) * 1000, 2)
        logger.warning(
            "Incident sealed on-chain | incident_id=%s | attack=%s | risk=%d | tx=%s | elapsed=%.1fms",
            payload.incident_id,
            payload.attack_type,
            payload.risk_score,
            result.tx_hash,
            elapsed,
        )
        return JSONResponse(
            status_code=201,
            content=tx_success_response(
                message=(
                    f"Incident '{payload.incident_id}' recorded and evidence hash sealed on-chain."
                ),
                result=result,
                data={
                    "incident_id": payload.incident_id,
                    "attack_type": payload.attack_type,
                    "source_device": payload.source_device,
                    "target_device": payload.target_device,
                    "risk_score": payload.risk_score,
                    "ai_confidence": payload.ai_confidence,
                    "action_taken": payload.action_taken,
                    "tamper_protected": True,
                },
            ),
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.get(
    "/count",
    summary="Get total incident count",
    description="Returns the total number of security incidents recorded in the Evidence Vault.",
    responses={
        200: {"description": "Count returned successfully"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def get_evidence_count(
    request: Request,
    service: EvidenceService = Depends(get_evidence_service),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/blockchain/evidence/count
    ```
    """
    logger.info(
        "GET /blockchain/evidence/count | ip=%s",
        request.client.host if request.client else "unknown",
    )
    try:
        count = service.total_incidents()
        return JSONResponse(
            content=success_response(
                message="Evidence count retrieved successfully.",
                data={"count": count},
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.get(
    "/latest",
    summary="Retrieve the most recently recorded incident",
    description=(
        "Returns the most recently sealed incident record from the Evidence Vault. "
        "Returns data=null if no incidents have been recorded yet."
    ),
    responses={
        200: {"description": "Latest incident returned (may be null)"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def get_latest_evidence(
    request: Request,
    service: EvidenceService = Depends(get_evidence_service),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/blockchain/evidence/latest
    ```
    """
    logger.info(
        "GET /blockchain/evidence/latest | ip=%s",
        request.client.host if request.client else "unknown",
    )
    try:
        record = service.latest_incident()
        if record is None:
            return JSONResponse(
                content=success_response(
                    message="No incidents recorded yet.",
                    data=None,
                )
            )
        return JSONResponse(
            content=success_response(
                message="Latest incident retrieved successfully.",
                data=record.to_dict(),
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.get(
    "/{incidentId}",
    summary="Get incident record by ID",
    description=(
        "Retrieve the full on-chain IncidentRecord for a specific security incident. "
        "Includes the sealed evidence hash, AI confidence scores, attack metadata, "
        "and current workflow status."
    ),
    responses={
        200: {"description": "Incident record returned successfully"},
        404: {"description": "Incident not found (IncidentNotFoundError)"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def get_evidence(
    request: Request,
    incidentId: str,
    service: EvidenceService = Depends(get_evidence_service),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/blockchain/evidence/0xdeadbeef...
    ```
    """
    incident_id = incidentId.strip()
    logger.info(
        "GET /blockchain/evidence/%s | ip=%s",
        incident_id,
        request.client.host if request.client else "unknown",
    )
    try:
        record = service.get_incident(incident_id)
        return JSONResponse(
            content=success_response(
                message="Incident record retrieved successfully.",
                data=record.to_dict(),
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)
