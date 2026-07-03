"""
api/blockchain/authentication.py — Blockchain Authentication Ledger REST API (Module 2).

Primary integration point for Member 1 (Rolling Key Authentication).  Every
authentication event — success or failure — is committed here to build an
immutable audit trail on the Ethereum blockchain.

Routes (all prefixed /blockchain/authentication by router.py):
    POST   /              — record a rolling-key authentication event
    GET    /count         — total authentication event count
    GET    /latest        — retrieve the most recent authentication record
    GET    /history/{id}  — all authentication event IDs for a device
    GET    /{id}          — retrieve a specific authentication record

IMPORTANT: /count and /latest MUST be declared before /{authenticationId}
to prevent FastAPI from consuming literal path segments as parameter values.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.blockchain.services import AuthenticationService
from app.core.logger import get_logger
from app.schemas.authentication import RecordAuthenticationRequest
from .dependencies import (
    get_authentication_service,
    success_response,
    tx_success_response,
    blockchain_error_json,
)

logger = get_logger("api.blockchain.authentication")

router = APIRouter(tags=["Blockchain — Authentication Ledger"])


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post(
    "/",
    summary="Record a rolling-key authentication event",
    description=(
        "Commits an authentication event to the immutable on-chain Authentication Ledger. "
        "Every call — successful or failed authentication — must be recorded to maintain "
        "a complete audit trail. The auth_id must be globally unique across all events."
    ),
    response_description="Authentication event recorded on-chain.",
    responses={
        200: {"description": "Authentication event recorded successfully"},
        409: {"description": "Duplicate auth_id already exists on-chain"},
        422: {"description": "Validation error or contract revert (GasEstimationError)"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def record_authentication(
    request: Request,
    payload: RecordAuthenticationRequest,
    service: AuthenticationService = Depends(get_authentication_service),
) -> JSONResponse:
    """
    Record a rolling-key authentication event on-chain.

    **curl example:**
    ```bash
    curl -X POST http://localhost:8000/blockchain/authentication \\
      -H "Content-Type: application/json" \\
      -d '{
        "auth_id": "0xabc123...",
        "device_id": "UAV-ALPHA-001",
        "key_version": 42,
        "success": true,
        "session_id": "0xdef456..."
      }'
    ```

    **Python requests example:**
    ```python
    import requests
    resp = requests.post(
        "http://localhost:8000/blockchain/authentication",
        json={
            "auth_id": "0xabc123...",
            "device_id": "UAV-ALPHA-001",
            "key_version": 42,
            "success": True,
            "session_id": "0xdef456...",
        },
    )
    print(resp.json())
    ```
    """
    t0 = time.monotonic()
    status_label = "SUCCESS" if payload.success else "FAILED"
    logger.info(
        "POST /blockchain/authentication | ip=%s | device=%s | key_v=%d | status=%s",
        request.client.host if request.client else "unknown",
        payload.device_id,
        payload.key_version,
        status_label,
    )
    try:
        result = service.record_authentication(
            auth_id=payload.auth_id,
            device_id=payload.device_id,
            key_version=payload.key_version,
            success=payload.success,
            session_id=payload.session_id,
        )
        elapsed = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "Auth recorded | device=%s | tx=%s | elapsed=%.1fms",
            payload.device_id,
            result.tx_hash,
            elapsed,
        )
        return JSONResponse(
            status_code=201,
            content=tx_success_response(
                message=f"Authentication event recorded on-chain (status={status_label}).",
                result=result,
                data={
                    "auth_id": payload.auth_id,
                    "device_id": payload.device_id,
                    "key_version": payload.key_version,
                    "success": payload.success,
                    "auth_status": status_label,
                },
            ),
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.get(
    "/count",
    summary="Get total authentication event count",
    description="Returns the total number of authentication events recorded on-chain.",
    responses={
        200: {"description": "Count returned successfully"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def get_authentication_count(
    request: Request,
    service: AuthenticationService = Depends(get_authentication_service),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/blockchain/authentication/count
    ```
    """
    logger.info(
        "GET /blockchain/authentication/count | ip=%s",
        request.client.host if request.client else "unknown",
    )
    try:
        count = service.total_authentications()
        return JSONResponse(
            content=success_response(
                message="Authentication count retrieved successfully.",
                data={"count": count},
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.get(
    "/latest",
    summary="Retrieve the most recent authentication record",
    description=(
        "Returns the most recently committed authentication event. "
        "Returns data=null if no events have been recorded yet."
    ),
    responses={
        200: {"description": "Latest authentication record returned (may be null)"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def get_latest_authentication(
    request: Request,
    service: AuthenticationService = Depends(get_authentication_service),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/blockchain/authentication/latest
    ```
    """
    logger.info(
        "GET /blockchain/authentication/latest | ip=%s",
        request.client.host if request.client else "unknown",
    )
    try:
        record = service.latest_authentication()
        if record is None:
            return JSONResponse(
                content=success_response(
                    message="No authentication events recorded yet.",
                    data=None,
                )
            )
        return JSONResponse(
            content=success_response(
                message="Latest authentication record retrieved successfully.",
                data=record.to_dict(),
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.get(
    "/history/{deviceId}",
    summary="Get authentication history for a device",
    description=(
        "Returns all authentication event IDs (hex strings) recorded for a specific device. "
        "Returns an empty list if the device has no authentication events on-chain."
    ),
    responses={
        200: {"description": "Authentication history returned"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def get_authentication_history(
    request: Request,
    deviceId: str,
    service: AuthenticationService = Depends(get_authentication_service),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/blockchain/authentication/history/UAV-ALPHA-001
    ```
    """
    device_id = deviceId.strip().upper()
    logger.info(
        "GET /blockchain/authentication/history/%s | ip=%s",
        device_id,
        request.client.host if request.client else "unknown",
    )
    try:
        auth_ids = service.get_authentication_history(device_id)
        return JSONResponse(
            content=success_response(
                message=f"Retrieved {len(auth_ids)} authentication event(s) for '{device_id}'.",
                data={
                    "device_id": device_id,
                    "auth_ids": auth_ids,
                    "count": len(auth_ids),
                },
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.get(
    "/{authenticationId}",
    summary="Get authentication record by ID",
    description=(
        "Retrieve the full on-chain AuthRecord for a specific authentication event. "
        "The authenticationId must match the auth_id used when the event was recorded."
    ),
    responses={
        200: {"description": "Authentication record returned successfully"},
        404: {"description": "Authentication record not found (AuthRecordNotFoundError)"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def get_authentication(
    request: Request,
    authenticationId: str,
    service: AuthenticationService = Depends(get_authentication_service),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/blockchain/authentication/0xabc123...
    ```
    """
    auth_id = authenticationId.strip()
    logger.info(
        "GET /blockchain/authentication/%s | ip=%s",
        auth_id,
        request.client.host if request.client else "unknown",
    )
    try:
        record = service.get_authentication(auth_id)
        return JSONResponse(
            content=success_response(
                message="Authentication record retrieved successfully.",
                data=record.to_dict(),
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)
