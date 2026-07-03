"""
api/blockchain/threat.py — Blockchain Threat Intelligence REST API (Module 4).

Integration point for Member 3 (SentinelX AI / CUDA detection engine).
When a device is flagged as a threat, SentinelX calls /blacklist here to
publish the indicator-of-compromise (IOC) to the immutable on-chain ledger,
making it visible to all participating aerospace network nodes.

Routes (all prefixed /blockchain/threat by router.py):
    POST   /blacklist         — add device to on-chain threat blacklist
    DELETE /remove/{deviceId} — remove device from blacklist
    GET    /count             — total threat profile count
    GET    /{deviceId}        — retrieve threat profile for a device

IMPORTANT: /count MUST be declared before /{deviceId}.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.blockchain.services import ThreatService
from app.core.logger import get_logger
from app.schemas.threat import BlacklistDeviceRequest
from .dependencies import (
    get_threat_service,
    success_response,
    tx_success_response,
    blockchain_error_json,
)

logger = get_logger("api.blockchain.threat")

router = APIRouter(tags=["Blockchain — Threat Intelligence"])


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post(
    "/blacklist",
    summary="Add a device to the on-chain threat blacklist",
    description=(
        "Publishes a threat indicator of compromise (IOC) by blacklisting a device "
        "on the immutable Ethereum ledger. Simultaneously creates or updates the "
        "device's on-chain ThreatProfile with the supplied threat level and risk score. "
        "Called by SentinelX AI when a device exceeds the configured threat threshold."
    ),
    response_description="Device blacklisted on-chain successfully.",
    responses={
        201: {"description": "Device blacklisted successfully"},
        422: {"description": "Device already blacklisted or contract would revert"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def blacklist_device(
    request: Request,
    payload: BlacklistDeviceRequest,
    service: ThreatService = Depends(get_threat_service),
) -> JSONResponse:
    """
    Blacklist a device on the on-chain Threat Intelligence ledger.

    **curl example:**
    ```bash
    curl -X POST http://localhost:8000/blockchain/threat/blacklist \\
      -H "Content-Type: application/json" \\
      -d '{"device_id":"UAV-ALPHA-001","threat_level":8,"risk_score":95}'
    ```

    **Python requests example:**
    ```python
    import requests
    resp = requests.post(
        "http://localhost:8000/blockchain/threat/blacklist",
        json={"device_id": "UAV-ALPHA-001", "threat_level": 8, "risk_score": 95},
    )
    print(resp.json())
    ```
    """
    t0 = time.monotonic()
    logger.warning(
        "POST /blockchain/threat/blacklist | ip=%s | device_id=%s | level=%d | risk=%d",
        request.client.host if request.client else "unknown",
        payload.device_id,
        payload.threat_level,
        payload.risk_score,
    )
    try:
        result = service.blacklist_device(
            device_id=payload.device_id,
            threat_level=payload.threat_level,
            risk_score=payload.risk_score,
        )
        elapsed = round((time.monotonic() - t0) * 1000, 2)
        logger.warning(
            "DEVICE BLACKLISTED | device_id=%s | level=%d | tx=%s | elapsed=%.1fms",
            payload.device_id,
            payload.threat_level,
            result.tx_hash,
            elapsed,
        )
        return JSONResponse(
            status_code=201,
            content=tx_success_response(
                message=(
                    f"Device '{payload.device_id}' blacklisted on-chain "
                    f"(threat_level={payload.threat_level}, risk_score={payload.risk_score})."
                ),
                result=result,
                data={
                    "device_id": payload.device_id,
                    "threat_level": payload.threat_level,
                    "risk_score": payload.risk_score,
                    "blacklisted": True,
                },
            ),
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.delete(
    "/remove/{deviceId}",
    summary="Remove a device from the on-chain blacklist",
    description=(
        "Removes a previously blacklisted device from the on-chain Threat Intelligence ledger. "
        "The device must currently be blacklisted; raises 404 (DeviceNotBlacklistedError) "
        "if it is not. The ThreatProfile record remains on-chain as historical data — "
        "only the blacklist flag is cleared."
    ),
    responses={
        200: {"description": "Device removed from blacklist successfully"},
        404: {"description": "Device is not blacklisted (DeviceNotBlacklistedError)"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def remove_blacklist(
    request: Request,
    deviceId: str,
    service: ThreatService = Depends(get_threat_service),
) -> JSONResponse:
    """
    Remove a device from the on-chain blacklist.

    **curl example:**
    ```bash
    curl -X DELETE http://localhost:8000/blockchain/threat/remove/UAV-ALPHA-001
    ```
    """
    device_id = deviceId.strip().upper()
    logger.info(
        "DELETE /blockchain/threat/remove/%s | ip=%s",
        device_id,
        request.client.host if request.client else "unknown",
    )
    try:
        result = service.remove_blacklist(device_id)
        return JSONResponse(
            content=tx_success_response(
                message=f"Device '{device_id}' removed from the on-chain blacklist.",
                result=result,
                data={
                    "device_id": device_id,
                    "blacklisted": False,
                },
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.get(
    "/count",
    summary="Get total threat profile count",
    description="Returns the total number of devices with a threat profile on-chain.",
    responses={
        200: {"description": "Count returned successfully"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def get_threat_count(
    request: Request,
    service: ThreatService = Depends(get_threat_service),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/blockchain/threat/count
    ```
    """
    logger.info(
        "GET /blockchain/threat/count | ip=%s",
        request.client.host if request.client else "unknown",
    )
    try:
        count = service.total_threat_devices()
        return JSONResponse(
            content=success_response(
                message="Threat profile count retrieved successfully.",
                data={"count": count},
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.get(
    "/{deviceId}",
    summary="Get threat profile for a device",
    description=(
        "Retrieve the on-chain ThreatProfile for a specific device. "
        "Returns the device's threat level, risk score, attack count, last seen timestamp, "
        "and current blacklist status."
    ),
    responses={
        200: {"description": "Threat profile returned successfully"},
        404: {"description": "No threat profile found (ThreatProfileNotFoundError)"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def get_threat_profile(
    request: Request,
    deviceId: str,
    service: ThreatService = Depends(get_threat_service),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/blockchain/threat/UAV-ALPHA-001
    ```
    """
    device_id = deviceId.strip().upper()
    logger.info(
        "GET /blockchain/threat/%s | ip=%s",
        device_id,
        request.client.host if request.client else "unknown",
    )
    try:
        profile = service.get_threat_profile(device_id)
        return JSONResponse(
            content=success_response(
                message=f"Threat profile for '{device_id}' retrieved successfully.",
                data=profile.to_dict(),
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)
