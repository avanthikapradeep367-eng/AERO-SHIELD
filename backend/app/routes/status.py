"""
routes/status.py — Backend health and service status endpoint.

This route contains NO business logic.
It only wires the HTTP layer to service status methods:

    Receive GET /api/v1/health
        ↓
    Probe database (SELECT 1)
        ↓
    Query mocked service statuses
        ↓
    Return HealthResponse
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logger import health_logger as logger
from app.database import get_db
from app.schemas.health import HealthResponse
from app.services.ai_service import AIService
from app.services.blockchain_service import BlockchainService

router = APIRouter(
    prefix="/api/v1",
    tags=["Health"],
)


# ── Dependency Providers ──────────────────────────────────────────────────────

def get_blockchain_service() -> BlockchainService:
    return BlockchainService()


def get_ai_service() -> AIService:
    return AIService()


# ── GET /api/v1/health ────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Detailed backend health check",
    description=(
        "Performs a live database connectivity probe (`SELECT 1`) and "
        "returns mocked status for blockchain and AI layers.\n\n"
        "Always returns HTTP 200 so monitoring systems receive a structured "
        "response — inspect the `status` field (`operational` | `degraded`) "
        "to determine actual health."
    ),
    responses={
        200: {"description": "Health report returned — check 'status' field"},
    },
)
async def health_check(
    db: Session = Depends(get_db),
    blockchain: BlockchainService = Depends(get_blockchain_service),
    ai: AIService = Depends(get_ai_service),
) -> HealthResponse:
    """
    Return a structured health report for all backend subsystems.

    - **database**: Verified by a real `SELECT 1` against PostgreSQL.
    - **blockchain**: Mocked until Member 2 integration is complete.
    - **ai_engine**: Mocked until Member 3 integration is complete.
    """
    # ── Real database probe ───────────────────────────────────────────────────
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
        logger.debug("Health probe: database OK.")
    except Exception as exc:
        db_status = "unreachable"
        logger.error("Health probe: database FAILED — %s", exc)

    # ── Mocked external service statuses ─────────────────────────────────────
    bc_info = await blockchain.get_status()
    ai_info = await ai.get_status()

    overall = "operational" if db_status == "connected" else "degraded"

    logger.info(
        "Health check | status=%s db=%s blockchain=%s ai=%s",
        overall,
        db_status,
        bc_info["status"],
        ai_info["status"],
    )

    return HealthResponse(
        status=overall,
        version="1.0.0",
        database=db_status,
        blockchain=bc_info["status"],
        ai_engine=ai_info["status"],
        timestamp=datetime.now(timezone.utc),
    )
