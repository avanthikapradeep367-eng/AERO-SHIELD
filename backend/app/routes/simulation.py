"""
routes/simulation.py — Attack simulation HTTP endpoint.

This route contains NO business logic.
It only wires the HTTP layer to SimulationService:

    Receive AttackRequest
        ↓
    Delegate to SimulationService.process_attack()
        ↓
    Return AttackResponse
"""

from fastapi import APIRouter, Depends, status

from app.schemas.attack import AttackRequest, AttackResponse
from app.services.ai_service import AIService
from app.services.blockchain_service import BlockchainService
from app.services.rolling_key_service import RollingKeyService
from app.services.simulation_service import SimulationService

router = APIRouter(
    prefix="/api/v1",
    tags=["Simulation"],
)


# ── Dependency Providers ──────────────────────────────────────────────────────

def get_ai_service() -> AIService:
    return AIService()


def get_blockchain_service() -> BlockchainService:
    return BlockchainService()


def get_rolling_key_service() -> RollingKeyService:
    return RollingKeyService()


def get_simulation_service(
    ai: AIService = Depends(get_ai_service),
    blockchain: BlockchainService = Depends(get_blockchain_service),
    rolling_key: RollingKeyService = Depends(get_rolling_key_service),
) -> SimulationService:
    return SimulationService(ai=ai, blockchain=blockchain, rolling_key=rolling_key)


# ── POST /api/v1/simulate-attack ──────────────────────────────────────────────

@router.post(
    "/simulate-attack",
    response_model=AttackResponse,
    status_code=status.HTTP_200_OK,
    summary="Simulate an attack and trigger automated threat response",
    description=(
        "Submits a simulated attack event through the full threat-response "
        "pipeline:\n\n"
        "1. **AI analysis** — SentinelX scores the risk (0-100).\n"
        "2. **High-risk path** (risk > 90) — The event is logged to the "
        "blockchain and the device rolling key is rotated.\n"
        "3. **Low-risk path** — Event is analysed only; no further action.\n\n"
        "AI analysis runs on the real SentinelX pipeline, and the high-risk path "
        "seals evidence on the real EvidenceVault contract — both return genuine, "
        "non-mocked results."
    ),
    responses={
        200: {"description": "Simulation completed; see response body for outcome"},
        422: {"description": "Invalid request body"},
        503: {"description": "AI or blockchain service unavailable"},
    },
)
async def simulate_attack(
    payload: AttackRequest,
    service: SimulationService = Depends(get_simulation_service),
) -> AttackResponse:
    """
    Trigger the attack simulation pipeline.

    All orchestration is handled by SimulationService — this function
    only receives the request and returns the result.
    """
    return await service.process_attack(payload)
