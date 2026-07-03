"""
AERO-SHIELD X — Forensics Evidence Verification & Hashing API

Routes (all prefixed /forensics by router.py):
    POST /hash                    — compute SHA-256 of text / JSON / bytes
    POST /verify                  — verify current hash against blockchain
    POST /report                  — generate a full forensic report
    GET  /history/{evidenceId}    — retrieve chain-of-custody history

IMPORTANT: GET /history/{evidenceId} is a parameterised route — declare any
future literal paths (e.g. /history/stats) BEFORE this route.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.blockchain.services.evidence_service import EvidenceService
from app.blockchain.exceptions import BlockchainBaseError
from app.core.logger import get_logger
from app.forensics import hashing, verifier, chain_of_custody, evidence_utils, integrity_checker
from app.schemas.forensics import (
    HashRequest,
    VerifyEvidenceRequest,
    GenerateReportRequest,
)
from app.blockchain.utils import now_iso

logger = get_logger("api.forensics.evidence_verification")

router = APIRouter(tags=["Digital Forensics — Evidence & Verification"])


# ── Dependency ──────────────────────────────────────────────────────────────────

def get_evidence_service() -> EvidenceService:
    return EvidenceService()


# ── Shared response builders ────────────────────────────────────────────────────

def _forensics_response(
    success: bool,
    message: str,
    verification_status: str | None = None,
    blockchain_hash: str | None = None,
    current_hash: str | None = None,
    transaction_hash: str | None = None,
    data: dict | None = None,
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": success,
            "message": message,
            "timestamp": now_iso(),
            "verificationStatus": verification_status,
            "blockchainHash": blockchain_hash,
            "currentHash": current_hash,
            "transactionHash": transaction_hash,
            "data": data,
        },
    )


def _error_response(message: str, error_code: str, details: dict | None = None, status_code: int = 500) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": message,
            "errorCode": error_code,
            "details": details,
        },
    )


# ── POST /forensics/hash ────────────────────────────────────────────────────────

@router.post(
    "/hash",
    summary="Generate SHA-256 hash of evidence",
    description=(
        "Compute a SHA-256 hash of a plain-text string, a JSON object, or base64-encoded "
        "binary data. Returns the 0x-prefixed hex digest, algorithm, size, and timestamp. "
        "Use this hash as ``evidence_hash`` when calling POST /blockchain/evidence to seal "
        "the evidence on-chain before any potential modification."
    ),
    responses={
        200: {"description": "Hash generated successfully"},
        422: {"description": "Validation error (unknown type or missing payload)"},
    },
)
def generate_hash(
    request: Request,
    payload: HashRequest,
) -> JSONResponse:
    """
    Generate a SHA-256 hash.

    **curl example (text):**
    ```bash
    curl -X POST http://localhost:8000/forensics/hash \\
      -H "Content-Type: application/json" \\
      -d '{"type":"text","text":"GPS signal anomaly detected on UAV-ALPHA-001","label":"incident-log"}'
    ```

    **curl example (JSON):**
    ```bash
    curl -X POST http://localhost:8000/forensics/hash \\
      -H "Content-Type: application/json" \\
      -d '{"type":"json","data":{"device":"UAV-ALPHA-001","attack":"GPS_SPOOFING","risk":87}}'
    ```
    """
    t0 = time.monotonic()
    logger.info(
        "POST /forensics/hash | ip=%s | type=%s | label=%s",
        request.client.host if request.client else "unknown",
        payload.type,
        payload.label,
    )

    try:
        if payload.type == "text":
            result = hashing.hash_text(payload.text, label=payload.label)
        elif payload.type == "json":
            result = hashing.hash_json(payload.data, label=payload.label)
        else:
            result = hashing.hash_bytes_from_base64(payload.data_base64, label=payload.label)

        elapsed = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "hash generated | type=%s | hash=%.10s… | elapsed=%.1fms",
            payload.type, result["hash"], elapsed,
        )

        return _forensics_response(
            success=True,
            message=f"SHA-256 hash generated successfully for input type '{payload.type}'.",
            verification_status=None,
            blockchain_hash=None,
            current_hash=result["hash"],
            transaction_hash=None,
            data={**result, "elapsed_ms": elapsed},
        )

    except (ValueError, FileNotFoundError) as exc:
        return _error_response(str(exc), type(exc).__name__, status_code=422)
    except Exception as exc:
        logger.exception("Unexpected error in /forensics/hash")
        return _error_response(f"Unexpected error: {exc}", type(exc).__name__, status_code=500)


# ── POST /forensics/verify ──────────────────────────────────────────────────────

@router.post(
    "/verify",
    summary="Verify evidence against blockchain sealed hash",
    description=(
        "Retrieve the SHA-256 hash sealed on-chain for the given incident and compare "
        "it with the supplied current hash (or compute it from supplied text / JSON). "
        "Returns VERIFIED (hashes match), TAMPERED (hashes differ), MISSING (not found), "
        "or ERROR (blockchain unreachable). Also auto-creates a chain-of-custody event."
    ),
    responses={
        200: {"description": "Verification result returned (check verificationStatus field)"},
        422: {"description": "Validation error"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def verify_evidence_endpoint(
    request: Request,
    payload: VerifyEvidenceRequest,
    svc: EvidenceService = Depends(get_evidence_service),
) -> JSONResponse:
    """
    Verify a piece of evidence against the blockchain sealed hash.

    **curl example:**
    ```bash
    curl -X POST http://localhost:8000/forensics/verify \\
      -H "Content-Type: application/json" \\
      -d '{"incident_id":"0xdeadbeef...","current_hash":"0xe3b0c44..."}'
    ```
    """
    t0 = time.monotonic()
    logger.info(
        "POST /forensics/verify | ip=%s | incident_id=%s",
        request.client.host if request.client else "unknown",
        payload.incident_id,
    )

    try:
        # Resolve the current hash from whichever input form was supplied
        current_hash: str | None = payload.current_hash
        if not current_hash and payload.current_text:
            h = hashing.hash_text(payload.current_text)
            current_hash = h["hash"]
        elif not current_hash and payload.current_data:
            h = hashing.hash_json(payload.current_data)
            current_hash = h["hash"]

        if not current_hash:
            return _error_response(
                "Provide at least one of: current_hash, current_text, current_data.",
                "ValidationError",
                status_code=422,
            )

        result = verifier.verify_evidence(payload.incident_id, current_hash, svc)

        # Auto-record a custody event
        custody_status = result.verification_status
        try:
            if not chain_of_custody.record_exists(payload.incident_id):
                chain_of_custody.create_record(
                    evidence_id=payload.incident_id,
                    collected_by="FORENSICS_API",
                    evidence_type="INCIDENT",
                    description="Auto-created on first verification.",
                )
            chain_of_custody.update_verification(
                evidence_id=payload.incident_id,
                verified_by="FORENSICS_API",
                status=custody_status if custody_status in chain_of_custody.VALID_STATUSES else "INVESTIGATING",
                notes=result.message,
            )
        except Exception as coc_exc:
            logger.warning("Chain-of-custody update failed (non-fatal): %s", coc_exc)

        elapsed = round((time.monotonic() - t0) * 1000, 2)
        is_verified = result.verification_status == verifier.VERIFIED

        logger.warning(
            "verify_evidence | incident=%s | status=%s | score=%d | elapsed=%.1fms",
            payload.incident_id, result.verification_status, result.integrity_score, elapsed,
        )

        return _forensics_response(
            success=True,
            message=result.message,
            verification_status=result.verification_status,
            blockchain_hash=result.blockchain_hash,
            current_hash=result.current_hash,
            transaction_hash=result.transaction_hash,
            data={
                **result.to_dict(),
                "elapsed_ms": elapsed,
            },
        )

    except Exception as exc:
        logger.exception("Unexpected error in /forensics/verify")
        return _error_response(f"Verification failed: {exc}", type(exc).__name__, status_code=500)


# ── POST /forensics/report ──────────────────────────────────────────────────────

@router.post(
    "/report",
    summary="Generate a full forensic report",
    description=(
        "Generate a comprehensive forensic report for an incident. "
        "Fetches the on-chain IncidentRecord, verifies the current hash (if supplied), "
        "attaches the chain-of-custody history, and computes a 0–100 integrity score. "
        "Suitable for legal proceedings and incident response handoffs."
    ),
    responses={
        200: {"description": "Forensic report generated successfully"},
        422: {"description": "Validation error"},
    },
)
def generate_report(
    request: Request,
    payload: GenerateReportRequest,
    svc: EvidenceService = Depends(get_evidence_service),
) -> JSONResponse:
    """
    Generate a full forensic report.

    **curl example:**
    ```bash
    curl -X POST http://localhost:8000/forensics/report \\
      -H "Content-Type: application/json" \\
      -d '{"incident_id":"0xdeadbeef...","current_hash":"0xe3b0c44...","analyst":"member2"}'
    ```
    """
    t0 = time.monotonic()
    logger.info(
        "POST /forensics/report | ip=%s | incident_id=%s | analyst=%s",
        request.client.host if request.client else "unknown",
        payload.incident_id,
        payload.analyst,
    )

    try:
        report = evidence_utils.generate_forensic_report(
            incident_id=payload.incident_id,
            current_hash=payload.current_hash,
            include_chain_of_custody=payload.include_chain_of_custody,
            include_incident_record=payload.include_incident_record,
            analyst=payload.analyst,
            evidence_service=svc,
        )

        elapsed = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "forensic report | incident=%s | status=%s | score=%d | elapsed=%.1fms",
            payload.incident_id,
            report.get("verification_status"),
            report.get("integrity_score", 0),
            elapsed,
        )

        return _forensics_response(
            success=True,
            message=f"Forensic report generated for incident '{payload.incident_id}'.",
            verification_status=report.get("verification_status"),
            blockchain_hash=report.get("blockchain_hash"),
            current_hash=report.get("current_hash"),
            transaction_hash=report.get("transaction_hash"),
            data={**report, "elapsed_ms": elapsed},
        )

    except Exception as exc:
        logger.exception("Unexpected error in /forensics/report")
        return _error_response(f"Report generation failed: {exc}", type(exc).__name__, status_code=500)


# ── GET /forensics/history/{evidenceId} ────────────────────────────────────────

@router.get(
    "/history/{evidenceId}",
    summary="Get chain-of-custody history for an evidence item",
    description=(
        "Retrieve the complete chain-of-custody audit trail for a given evidence ID. "
        "Returns all collection and verification events in chronological order. "
        "Returns an empty history (not a 404) if no custody record exists yet."
    ),
    responses={
        200: {"description": "Chain-of-custody history returned"},
    },
)
def get_custody_history(
    request: Request,
    evidenceId: str,
) -> JSONResponse:
    """
    Retrieve chain-of-custody history.

    **curl example:**
    ```bash
    curl http://localhost:8000/forensics/history/0xdeadbeef...
    ```
    """
    evidence_id = evidenceId.strip()
    logger.info(
        "GET /forensics/history/%s | ip=%s",
        evidence_id,
        request.client.host if request.client else "unknown",
    )

    try:
        record = chain_of_custody.get_record(evidence_id)
        history = chain_of_custody.get_history(evidence_id)
        return _forensics_response(
            success=True,
            message=f"Chain-of-custody history retrieved for '{evidence_id}' ({len(history)} event(s)).",
            verification_status=record.current_status,
            blockchain_hash=record.transaction_hash,
            current_hash=None,
            transaction_hash=record.transaction_hash,
            data={
                "evidence_id": evidence_id,
                "custody_record": record.to_dict(),
                "history": history,
                "event_count": len(history),
            },
        )
    except KeyError:
        return _forensics_response(
            success=True,
            message=f"No chain-of-custody record exists yet for '{evidence_id}'.",
            verification_status=None,
            blockchain_hash=None,
            current_hash=None,
            transaction_hash=None,
            data={
                "evidence_id": evidence_id,
                "custody_record": None,
                "history": [],
                "event_count": 0,
            },
        )
