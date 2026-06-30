"""
services/simulation_service.py — Attack simulation orchestration service.

Contains ALL business logic for the threat-response pipeline.
The route (routes/simulation.py) delegates entirely to this service
and does nothing except wire the HTTP layer to it.

Pipeline:
    1. Call IAIService.analyze_request()       → get risk assessment
    2. Parse result into AIAnalysisResult      → type-safe access
    3. If risk_score > HIGH_RISK_THRESHOLD:
         a. Call IBlockchainService.log_attack() → immutable audit trail
         b. Parse into BlockchainAttackResult
         c. Rotate device's rolling key         → reduce attack surface
    4. Return a structured AttackResponse
"""

import logging
from datetime import datetime, timezone

from app.interfaces.ai_interface import IAIService
from app.interfaces.blockchain_interface import IBlockchainService
from app.schemas.attack import AttackRequest, AttackResponse, HIGH_RISK_THRESHOLD
from app.schemas.integration import AIAnalysisResult, BlockchainAttackResult
from app.services.rolling_key_service import RollingKeyService
from app.core.logger import simulation_logger as logger


class SimulationService:
    """
    Orchestrates the full attack-simulation threat-response pipeline.

    Dependencies are injected at construction time (via FastAPI Depends),
    typed against interfaces so the real implementations can be swapped
    in without touching this class.
    """

    def __init__(
        self,
        ai: IAIService,
        blockchain: IBlockchainService,
        rolling_key: RollingKeyService,
    ) -> None:
        self._ai = ai
        self._blockchain = blockchain
        self._rolling_key = rolling_key

    async def process_attack(self, request: AttackRequest) -> AttackResponse:
        """
        Execute the full threat-response pipeline for a simulated attack.

        Args:
            request: Validated AttackRequest containing device_id, attack_type, etc.

        Returns:
            AttackResponse with analysis results and actions taken.
        """
        logger.info(
            "Simulation started | device=%s attack_type=%s source_ip=%s",
            request.device_id,
            request.attack_type,
            request.source_ip,
        )

        # ── Step 1: AI threat analysis ────────────────────────────────────────
        raw_analysis = await self._ai.analyze_request(request.model_dump())
        analysis = AIAnalysisResult(**raw_analysis)

        logger.info(
            "AI analysis complete | id=%s risk=%.1f confidence=%.1f%% threat=%s",
            analysis.analysis_id,
            analysis.risk_score,
            analysis.ai_confidence,
            analysis.threat_detected,
        )

        # ── Step 2: High-risk automated response ─────────────────────────────
        threat_detected = analysis.risk_score > HIGH_RISK_THRESHOLD
        blockchain_logged = False
        blockchain_tx: str | None = None
        key_rotated = False
        action_taken = "Threat analysed; risk below action threshold."

        if threat_detected:
            action_taken = await self._handle_high_risk(
                request=request,
                analysis=analysis,
            )
            blockchain_logged = True
            blockchain_tx = self._last_tx_hash  # set by _handle_high_risk
            key_rotated = True

        logger.info(
            "Simulation complete | device=%s risk=%.1f blockchain=%s key_rotated=%s",
            request.device_id,
            analysis.risk_score,
            blockchain_logged,
            key_rotated,
        )

        return AttackResponse(
            device_id=request.device_id,
            attack_type=request.attack_type,
            analysis_id=analysis.analysis_id,
            risk_score=analysis.risk_score,
            ai_confidence=analysis.ai_confidence,
            threat_detected=threat_detected,
            key_rotated=key_rotated,
            blockchain_logged=blockchain_logged,
            blockchain_tx=blockchain_tx,
            action_taken=action_taken,
            timestamp=datetime.now(timezone.utc),
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    _last_tx_hash: str | None = None

    async def _handle_high_risk(
        self,
        request: AttackRequest,
        analysis: AIAnalysisResult,
    ) -> str:
        """
        Execute the automated response for a high-risk event.

        a. Log the attack to the immutable blockchain ledger.
        b. Rotate the device's rolling key to limit further access.

        Returns:
            Human-readable description of the actions taken.
        """
        # 2a. Blockchain audit trail
        raw_bc = await self._blockchain.log_attack(
            device_id=request.device_id,
            attack_type=request.attack_type,
            risk_score=analysis.risk_score,
            ai_confidence=analysis.ai_confidence,
        )
        bc_result = BlockchainAttackResult(**raw_bc)
        self._last_tx_hash = bc_result.tx_hash

        logger.warning(
            "High-risk event logged to blockchain | device=%s incident=%s tx=%s",
            request.device_id,
            bc_result.incident_id,
            bc_result.tx_hash,
        )

        # 2b. Key rotation
        current_key = self._rolling_key.generate_key(request.device_id)
        self._rolling_key.rotate_key(request.device_id, current_key)

        logger.warning(
            "Rolling key rotated for device '%s' following high-risk event.",
            request.device_id,
        )

        return "Rolling key rotated; attack logged to blockchain."
