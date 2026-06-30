"""
exceptions/ai.py — AI / SentinelX service exceptions.

Raised by Member 1's mock today; will be raised by the real
SentinelX inference integration (Member 3) once that layer is live.

HTTP 503 — engine unavailable (Member 3 service not running).
HTTP 502 — engine reachable but inference failed (bad gateway).
HTTP 422 — input was malformed for the model.
"""

from fastapi import HTTPException, status


class AIServiceError(HTTPException):
    """Base class for all AI service failures."""

    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
    ):
        super().__init__(status_code=status_code, detail=detail)


class AIUnavailableError(AIServiceError):
    """Raised when the SentinelX inference endpoint cannot be reached."""

    def __init__(self) -> None:
        super().__init__(
            detail=(
                "AI service (SentinelX) is currently unavailable. "
                "Threat analysis cannot be performed. Please retry later."
            )
        )


class AIAnalysisError(AIServiceError):
    """Raised when the AI engine is reachable but inference fails."""

    def __init__(self, reason: str = "") -> None:
        detail = "AI threat analysis failed."
        if reason:
            detail += f" Reason: {reason}"
        super().__init__(
            detail=detail,
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class AIInvalidInputError(AIServiceError):
    """Raised when the payload sent to the AI engine fails validation."""

    def __init__(self, field: str = "", reason: str = "") -> None:
        detail = "AI engine rejected the input payload."
        if field:
            detail += f" Field: '{field}'."
        if reason:
            detail += f" Reason: {reason}"
        super().__init__(
            detail=detail,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
