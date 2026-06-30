"""
exceptions/authentication.py — Authentication and rolling-key exceptions.

All exceptions inherit from FastAPI's HTTPException so they are handled
automatically by FastAPI's exception machinery and produce well-formed
JSON error responses without additional handler registration.
"""

from fastapi import HTTPException, status


class AuthenticationError(HTTPException):
    """Base class for all authentication-related failures."""

    def __init__(self, detail: str, status_code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(status_code=status_code, detail=detail)


class InvalidKeyError(AuthenticationError):
    """Raised when a device presents a rolling key that does not match the stored value."""

    def __init__(self, device_id: str):
        super().__init__(
            detail=f"Invalid rolling key for device '{device_id}'. "
                   "Key mismatch — authentication denied."
        )


class KeyExpiredError(AuthenticationError):
    """Raised when a device's rolling key has exceeded its TTL."""

    def __init__(self, device_id: str):
        super().__init__(
            detail=f"Rolling key for device '{device_id}' has expired. "
                   "Request a new key and retry."
        )


class KeyRotationError(HTTPException):
    """Raised when key rotation cannot be completed."""

    def __init__(self, device_id: str, reason: str = ""):
        detail = f"Rolling key rotation failed for device '{device_id}'."
        if reason:
            detail += f" Reason: {reason}"
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
        )


class DeviceNotAuthenticatedError(AuthenticationError):
    """Raised when a request arrives without valid authentication credentials."""

    def __init__(self, device_id: str = ""):
        msg = "Device authentication required."
        if device_id:
            msg = f"Device '{device_id}' is not authenticated."
        super().__init__(detail=msg)
