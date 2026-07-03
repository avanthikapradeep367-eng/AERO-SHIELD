"""
api/blockchain/device.py — Blockchain Device Registry REST API (Module 1).

Exposes the five device endpoints that wrap DeviceService without duplicating
any blockchain logic.  All service calls are synchronous (Web3.py HTTP provider);
FastAPI automatically runs sync route functions in a thread pool.

Routes (all prefixed /blockchain/device by router.py):
    POST   /register         — register a new aerospace device on-chain
    GET    /count            — total registered device count
    GET    /all              — list all registered device IDs
    PUT    /status           — activate / deactivate a device
    GET    /{deviceId}       — retrieve full device record by ID

IMPORTANT: /count and /all MUST be declared before /{deviceId} so FastAPI
matches their literal path segments before attempting the parameterised route.
"""

from __future__ import annotations

import logging
import time
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.blockchain.services import DeviceService
from app.core.logger import get_logger
from .dependencies import (
    get_device_service,
    success_response,
    tx_success_response,
    blockchain_error_json,
)

logger = get_logger("api.blockchain.device")

router = APIRouter(tags=["Blockchain — Device Registry"])


# ── Request schemas (blockchain-specific, separate from PostgreSQL device) ──────

VALID_DEVICE_TYPES: set[str] = {
    "UAV",
    "AIRCRAFT",
    "GROUND_STATION",
    "SATELLITE_GW",
    "IOT_NODE",
}


class RegisterBlockchainDeviceRequest(BaseModel):
    """
    Request body for POST /blockchain/device/register.

    device_type must be one of the recognised aerospace device categories.
    public_key is the hex-encoded public key used by Member 1's rolling-key
    authentication system to sign communications.
    """

    device_id: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Human-readable unique device ID (e.g. UAV-ALPHA-001)",
        examples=["UAV-ALPHA-001"],
    )
    device_type: str = Field(
        ...,
        description=(
            f"Device category. Accepted values: {', '.join(sorted(VALID_DEVICE_TYPES))}."
        ),
        examples=["UAV"],
    )
    public_key: str = Field(
        ...,
        min_length=10,
        description=(
            "Hex-encoded public key used for rolling-key authentication. "
            "Provide as '0x04...' (uncompressed) or '0x02/0x03...' (compressed)."
        ),
        examples=["0x04abc123def456abc123def456abc123def456abc123def456abc123def456abc12345"],
    )

    @field_validator("device_id")
    @classmethod
    def sanitize_device_id(cls, v: str) -> str:
        sanitized = v.strip().upper()
        if not sanitized:
            raise ValueError("device_id must not be empty.")
        return sanitized

    @field_validator("device_type")
    @classmethod
    def validate_device_type(cls, v: str) -> str:
        sanitized = v.strip().upper()
        if sanitized not in VALID_DEVICE_TYPES:
            raise ValueError(
                f"Invalid device_type '{sanitized}'. "
                f"Must be one of: {', '.join(sorted(VALID_DEVICE_TYPES))}."
            )
        return sanitized

    @field_validator("public_key")
    @classmethod
    def sanitize_public_key(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("public_key must not be empty.")
        return cleaned

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "device_id": "UAV-ALPHA-001",
                    "device_type": "UAV",
                    "public_key": "0x04abc123def456abc123def456abc123def456abc123def456abc123def456abc12345",
                }
            ]
        }
    }


class UpdateDeviceStatusRequest(BaseModel):
    """Request body for PUT /blockchain/device/status."""

    device_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Module 1 string device ID of the device to update",
        examples=["UAV-ALPHA-001"],
    )
    active: bool = Field(
        ...,
        description="True = activate the device. False = deactivate / suspend.",
        examples=[False],
    )

    @field_validator("device_id")
    @classmethod
    def sanitize_device_id(cls, v: str) -> str:
        return v.strip().upper()

    model_config = {
        "json_schema_extra": {
            "examples": [{"device_id": "UAV-ALPHA-001", "active": False}]
        }
    }


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    summary="Register a new aerospace device on-chain",
    description=(
        "Commits a new device to the EvidenceVault Device Registry (Module 1). "
        "The device_id must not already exist on-chain; raises 409 if it does. "
        "Returns the transaction hash and gas usage of the mined transaction."
    ),
    response_description="Device successfully registered on-chain.",
    responses={
        200: {"description": "Device registered successfully"},
        409: {"description": "Device already registered (DuplicateDeviceError)"},
        422: {"description": "Validation error or contract would revert (GasEstimationError)"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def register_device(
    request: Request,
    payload: RegisterBlockchainDeviceRequest,
    service: DeviceService = Depends(get_device_service),
) -> JSONResponse:
    """
    Register a new aerospace device on the Ethereum blockchain.

    **curl example:**
    ```bash
    curl -X POST http://localhost:8000/blockchain/device/register \\
      -H "Content-Type: application/json" \\
      -d '{"device_id":"UAV-ALPHA-001","device_type":"UAV","public_key":"0x04abc..."}'
    ```
    """
    t0 = time.monotonic()
    logger.info(
        "POST /blockchain/device/register | ip=%s | device_id=%s",
        request.client.host if request.client else "unknown",
        payload.device_id,
    )
    try:
        result = service.register_device(
            device_id=payload.device_id,
            device_type=payload.device_type,
            public_key=payload.public_key,
        )
        elapsed = round((time.monotonic() - t0) * 1000, 2)
        logger.info(
            "Device registered | device_id=%s | tx=%s | elapsed=%.1fms",
            payload.device_id,
            result.tx_hash,
            elapsed,
        )
        return JSONResponse(
            status_code=201,
            content=tx_success_response(
                message=f"Device '{payload.device_id}' registered on-chain successfully.",
                result=result,
                data={
                    "device_id": payload.device_id,
                    "device_type": payload.device_type,
                },
            ),
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.get(
    "/count",
    summary="Get total registered device count",
    description="Returns the total number of devices registered in the on-chain Device Registry.",
    responses={
        200: {"description": "Count returned successfully"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def get_device_count(
    request: Request,
    service: DeviceService = Depends(get_device_service),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/blockchain/device/count
    ```
    """
    logger.info(
        "GET /blockchain/device/count | ip=%s",
        request.client.host if request.client else "unknown",
    )
    try:
        count = service.total_devices()
        return JSONResponse(
            content=success_response(
                message="Device count retrieved successfully.",
                data={"count": count},
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.get(
    "/all",
    summary="List all registered device IDs",
    description=(
        "Returns the complete list of all device IDs currently registered "
        "in the on-chain Device Registry."
    ),
    responses={
        200: {"description": "Device list returned successfully"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def get_all_devices(
    request: Request,
    service: DeviceService = Depends(get_device_service),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/blockchain/device/all
    ```
    """
    logger.info(
        "GET /blockchain/device/all | ip=%s",
        request.client.host if request.client else "unknown",
    )
    try:
        devices = service.get_registered_devices()
        return JSONResponse(
            content=success_response(
                message=f"Retrieved {len(devices)} registered device(s).",
                data={"devices": devices, "total": len(devices)},
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.put(
    "/status",
    summary="Activate or deactivate a registered device",
    description=(
        "Update the operational status of a registered device. "
        "Set active=true to activate or active=false to deactivate/suspend. "
        "The device must already exist in the registry."
    ),
    responses={
        200: {"description": "Status updated successfully"},
        404: {"description": "Device not found (DeviceNotFoundError)"},
        422: {"description": "Contract would revert"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def update_device_status(
    request: Request,
    payload: UpdateDeviceStatusRequest,
    service: DeviceService = Depends(get_device_service),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl -X PUT http://localhost:8000/blockchain/device/status \\
      -H "Content-Type: application/json" \\
      -d '{"device_id":"UAV-ALPHA-001","active":false}'
    ```
    """
    action = "activate" if payload.active else "deactivate"
    logger.info(
        "PUT /blockchain/device/status | ip=%s | device_id=%s | action=%s",
        request.client.host if request.client else "unknown",
        payload.device_id,
        action,
    )
    try:
        result = service.update_device_status(
            device_id=payload.device_id,
            active=payload.active,
        )
        status_label = "activated" if payload.active else "deactivated"
        return JSONResponse(
            content=tx_success_response(
                message=f"Device '{payload.device_id}' {status_label} successfully.",
                result=result,
                data={
                    "device_id": payload.device_id,
                    "active": payload.active,
                    "status": "ACTIVE" if payload.active else "INACTIVE",
                },
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)


@router.get(
    "/{deviceId}",
    summary="Get device record by ID",
    description=(
        "Retrieve the full on-chain DeviceRecord for a registered device. "
        "Returns device type, public key, owner address, registration timestamps, "
        "and active status."
    ),
    responses={
        200: {"description": "Device record returned successfully"},
        404: {"description": "Device not found (DeviceNotFoundError)"},
        503: {"description": "Blockchain node unreachable"},
    },
)
def get_device(
    request: Request,
    deviceId: str,
    service: DeviceService = Depends(get_device_service),
) -> JSONResponse:
    """
    **curl example:**
    ```bash
    curl http://localhost:8000/blockchain/device/UAV-ALPHA-001
    ```
    """
    device_id = deviceId.strip().upper()
    logger.info(
        "GET /blockchain/device/%s | ip=%s",
        device_id,
        request.client.host if request.client else "unknown",
    )
    try:
        record = service.get_device(device_id)
        return JSONResponse(
            content=success_response(
                message=f"Device '{device_id}' retrieved successfully.",
                data=record.to_dict(),
            )
        )
    except Exception as exc:
        return blockchain_error_json(exc)
