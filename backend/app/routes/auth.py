"""
routes/auth.py — Device registration and lookup API endpoints.

Handles all device-related HTTP routes for the AERO-SHIELD backend.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app import models, schemas

# ── Router ────────────────────────────────────────────────────────────────────
# Prefix /api/v1 makes it easy to version the API in the future
router = APIRouter(
    prefix="/api/v1",
    tags=["Devices"],
)


# ── POST /register-device ─────────────────────────────────────────────────────
@router.post(
    "/register-device",
    response_model=schemas.DeviceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new AERO-SHIELD device",
    description=(
        "Registers a new device in the AERO-SHIELD system. "
        "Each `device_id` must be globally unique. "
        "Returns the full device record including the auto-generated UUID and timestamp."
    ),
    responses={
        201: {"description": "Device registered successfully"},
        409: {
            "model": schemas.ErrorResponse,
            "description": "A device with this device_id already exists",
        },
        500: {
            "model": schemas.ErrorResponse,
            "description": "Internal server error",
        },
    },
)
def register_device(
    payload: schemas.DeviceRegisterRequest,
    db: Session = Depends(get_db),
) -> schemas.DeviceResponse:
    """
    Register a new device.

    - **device_id**: Unique identifier (e.g. SHIELD-001). Auto-uppercased.
    - **device_name**: Human-readable label for the device.
    - **status**: One of `active`, `inactive`, `maintenance`. Defaults to `active`.
    """
    # Check if device_id already exists (explicit check for clear error message)
    existing = (
        db.query(models.Device)
        .filter(models.Device.device_id == payload.device_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device with ID '{payload.device_id}' is already registered.",
        )

    # Create ORM instance from validated request payload
    new_device = models.Device(
        device_id=payload.device_id,
        device_name=payload.device_name,
        status=payload.status,
    )

    try:
        db.add(new_device)
        db.commit()
        db.refresh(new_device)  # Reload from DB to populate server-generated fields
    except IntegrityError:
        # Race condition guard — another request registered same device_id
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Device with ID '{payload.device_id}' is already registered.",
        )
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(exc)}",
        )

    return new_device


# ── GET /device/{device_id} ───────────────────────────────────────────────────
@router.get(
    "/device/{device_id}",
    response_model=schemas.DeviceResponse,
    status_code=status.HTTP_200_OK,
    summary="Look up a device by its device_id",
    description=(
        "Retrieves full details for a specific device using its unique `device_id`. "
        "The lookup is case-insensitive (SHIELD-001 == shield-001)."
    ),
    responses={
        200: {"description": "Device found and returned"},
        404: {
            "model": schemas.ErrorResponse,
            "description": "No device found with the given device_id",
        },
    },
)
def get_device(
    device_id: str,
    db: Session = Depends(get_db),
) -> schemas.DeviceResponse:
    """
    Look up a registered device.

    - **device_id**: The unique external identifier of the device to retrieve.
    """
    # Normalize to uppercase for case-insensitive lookup
    device = (
        db.query(models.Device)
        .filter(models.Device.device_id == device_id.strip().upper())
        .first()
    )

    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID '{device_id.upper()}' was not found.",
        )

    return device
