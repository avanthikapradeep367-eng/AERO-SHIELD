"""
AERO-SHIELD X — Chain of Custody Management API

Routes (prefixed /forensics by router.py):
    POST /custody/create    — create a chain-of-custody record
    PUT  /custody/update    — record a verification event
    GET  /custody/list      — list all custody records

These endpoints expose direct custody management for cases where
records need to be created or updated independently of the
/forensics/verify workflow.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.core.logger import get_logger
from app.forensics import chain_of_custody
from app.schemas.forensics import CreateCustodyRequest, UpdateCustodyRequest
from app.blockchain.utils import now_iso

logger = get_logger("api.forensics.chain_of_custody")

router = APIRouter(tags=["Digital Forensics — Chain of Custody"])


def _ok(message: str, data: dict | None = None, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "timestamp": now_iso(),
            "verificationStatus": data.get("current_status") if data else None,
            "blockchainHash": data.get("transaction_hash") if data else None,
            "currentHash": None,
            "transactionHash": data.get("transaction_hash") if data else None,
            "data": data,
        },
    )


def _err(message: str, code: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "message": message, "errorCode": code, "details": None},
    )


@router.post(
    "/custody/create",
    summary="Create a chain-of-custody record",
    description=(
        "Manually create a chain-of-custody record for a piece of evidence. "
        "If a record already exists for the supplied evidence_id, the existing "
        "record is returned (idempotent)."
    ),
    responses={
        201: {"description": "Custody record created"},
    },
)
def create_custody_record(
    request: Request,
    payload: CreateCustodyRequest,
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl -X POST http://localhost:8000/forensics/custody/create \\
      -H "Content-Type: application/json" \\
      -d '{"evidence_id":"0xdeadbeef...","collected_by":"analyst-01","evidence_type":"INCIDENT"}'
    ```
    """
    logger.info(
        "POST /forensics/custody/create | ip=%s | evidence_id=%s",
        request.client.host if request.client else "unknown",
        payload.evidence_id,
    )
    record = chain_of_custody.create_record(
        evidence_id=payload.evidence_id,
        collected_by=payload.collected_by,
        evidence_type=payload.evidence_type,
        description=payload.description,
        transaction_hash=payload.transaction_hash,
        blockchain_block=payload.blockchain_block,
    )
    return _ok(
        f"Chain-of-custody record created for '{payload.evidence_id}'.",
        data=record.to_dict(),
        status_code=201,
    )


@router.put(
    "/custody/update",
    summary="Record a verification event",
    description=(
        "Append a verification event to an existing chain-of-custody record. "
        "Updates the current_status and preserves the full event history."
    ),
    responses={
        200: {"description": "Verification event recorded"},
        404: {"description": "No record found for evidence_id"},
    },
)
def update_custody_record(
    request: Request,
    payload: UpdateCustodyRequest,
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl -X PUT http://localhost:8000/forensics/custody/update \\
      -H "Content-Type: application/json" \\
      -d '{"evidence_id":"0xdeadbeef...","verified_by":"analyst-01","status":"VERIFIED"}'
    ```
    """
    logger.info(
        "PUT /forensics/custody/update | ip=%s | evidence_id=%s | status=%s",
        request.client.host if request.client else "unknown",
        payload.evidence_id,
        payload.status,
    )
    try:
        record = chain_of_custody.update_verification(
            evidence_id=payload.evidence_id,
            verified_by=payload.verified_by,
            status=payload.status,
            notes=payload.notes,
            transaction_hash=payload.transaction_hash,
            blockchain_block=payload.blockchain_block,
        )
        return _ok(
            f"Verification event recorded for '{payload.evidence_id}' — status={payload.status}.",
            data=record.to_dict(),
        )
    except KeyError as exc:
        return _err(str(exc), "RecordNotFound", status_code=404)
    except ValueError as exc:
        return _err(str(exc), "ValidationError", status_code=422)


@router.get(
    "/custody/list",
    summary="List all chain-of-custody records",
    description="Return all chain-of-custody records in the system (newest first).",
    responses={
        200: {"description": "Custody records returned"},
    },
)
def list_custody_records(request: Request) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/forensics/custody/list
    ```
    """
    records = chain_of_custody.list_records(limit=200)
    return JSONResponse(
        content={
            "success": True,
            "message": f"Retrieved {len(records)} custody record(s).",
            "timestamp": now_iso(),
            "verificationStatus": None,
            "blockchainHash": None,
            "currentHash": None,
            "transactionHash": None,
            "data": {"records": records, "total": len(records)},
        }
    )
