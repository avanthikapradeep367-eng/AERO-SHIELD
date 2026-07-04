"""
services/blockchain_service.py — Blockchain integration interface layer.

This module was originally a MOCK / PLACEHOLDER owned by Member 1 (Backend),
pending Member 2's real Hardhat + Solidity layer. That layer (app.blockchain.*)
is now complete, and log_attack() — the method the attack-simulation pipeline
uses for its high-risk automated response — delegates to it: a detected
attack is sealed on-chain via the real EvidenceVault contract
(app.blockchain.services.evidence_service.EvidenceService.record_incident()),
returning a genuine transaction hash instead of a fabricated one.

log_authentication(), register_device(), and get_status() below are still
mocks — this file's other callers (device/auth logging, health status) were
not part of this integration and are unchanged.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from app.blockchain.services.evidence_service import EvidenceService
from app.forensics.hashing import hash_json
from app.interfaces.blockchain_interface import IBlockchainService
from app.core.logger import blockchain_logger as logger


class BlockchainService(IBlockchainService):
    """
    Interface layer for blockchain interactions.

    All methods are async to match the eventual real implementation,
    which will perform I/O against a Web3 provider.
    """

    async def log_authentication(
        self,
        device_id: str,
        success: bool,
        key_version: int = 1,
        session_id: str | None = None,
    ) -> dict:
        """
        Log a device authentication event to the blockchain.

        Args:
            device_id:   Unique device identifier.
            success:     Whether authentication succeeded.
            key_version: Rolling key version used for this auth.
            session_id:  Optional session identifier.

        Returns:
            Mocked transaction receipt dict.
        """
        mock_tx = f"0x{uuid.uuid4().hex}{uuid.uuid4().hex[:32]}"
        logger.info(
            "[MOCK] blockchain.log_authentication | device=%s success=%s tx=%s",
            device_id,
            success,
            mock_tx,
        )
        return {
            "mocked": True,
            "tx_hash": mock_tx,
            "device_id": device_id,
            "success": success,
            "key_version": key_version,
            "session_id": session_id or str(uuid.uuid4()),
            "block_number": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def log_attack(
        self,
        device_id: str,
        attack_type: str,
        risk_score: float,
        ai_confidence: float = 0.0,
        evidence_hash: str | None = None,
    ) -> dict:
        """
        Seal a detected attack/threat event on-chain via the real
        EvidenceVault contract (app.blockchain.services.evidence_service).

        The attack-simulation pipeline has no separate "source device" —
        AttackRequest only identifies the device under analysis — so both
        source_device and target_device are recorded as device_id.

        Args:
            device_id:     Target device identifier.
            attack_type:   Category of attack (e.g. "DDOS", "INJECTION").
            risk_score:    AI-determined risk level (0–100).
            ai_confidence: Confidence percentage of the AI model.
            evidence_hash: Optional SHA-256 hash of captured evidence. When
                           omitted, a genuine hash is computed (via the
                           existing forensics hashing utility) from the
                           analysis payload itself.

        Returns:
            Real transaction receipt dict (see IBlockchainService.log_attack).
        """
        action_taken = "Rolling key rotated; attack logged to blockchain."
        computed_hash = evidence_hash or hash_json(
            {
                "device_id": device_id,
                "attack_type": attack_type,
                "risk_score": risk_score,
                "ai_confidence": ai_confidence,
            }
        )["hash"]
        # 32-byte on-chain incident ID; hex_to_bytes32() right-pads a shorter
        # hex value, so a single UUID4 (16 bytes) is a valid, unique input —
        # see app/blockchain/services/evidence_service.py's docstring.
        incident_id = f"0x{uuid.uuid4().hex}"

        evidence_service = EvidenceService()
        # Web3.py's HTTP provider is synchronous; run it in a thread so this
        # async method doesn't block the event loop — the documented
        # integration pattern from app/blockchain/blockchain_service.py's
        # own "FastAPI integration note".
        result = await asyncio.to_thread(
            evidence_service.record_incident,
            incident_id=incident_id,
            attack_type=attack_type,
            source_device=device_id,
            target_device=device_id,
            risk_score=round(risk_score),
            ai_confidence=round(ai_confidence),
            action_taken=action_taken,
            evidence_hash=computed_hash,
        )

        logger.warning(
            "blockchain.log_attack | device=%s type=%s risk=%.1f tx=%s block=%s",
            device_id,
            attack_type,
            risk_score,
            result.tx_hash,
            result.block_number,
        )
        return {
            "mocked": False,
            "tx_hash": result.tx_hash,
            "incident_id": incident_id,
            "device_id": device_id,
            "attack_type": attack_type,
            "risk_score": risk_score,
            "ai_confidence": ai_confidence,
            "evidence_hash": computed_hash,
            "block_number": result.block_number,
            "timestamp": result.timestamp,
        }

    async def register_device(
        self,
        device_id: str,
        device_type: str = "UAV",
        public_key: str | None = None,
    ) -> dict:
        """
        Register a device on the blockchain ledger.

        Args:
            device_id:   Unique device identifier.
            device_type: Hardware category (e.g. "UAV", "SENSOR").
            public_key:  Optional device public key for on-chain identity.

        Returns:
            Mocked transaction receipt dict.
        """
        mock_tx = f"0x{uuid.uuid4().hex}{uuid.uuid4().hex[:32]}"
        logger.info(
            "[MOCK] blockchain.register_device | device=%s type=%s tx=%s",
            device_id,
            device_type,
            mock_tx,
        )
        return {
            "mocked": True,
            "tx_hash": mock_tx,
            "device_id": device_id,
            "device_type": device_type,
            "public_key": public_key,
            "block_number": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_status(self) -> dict:
        """
        Return mocked blockchain connectivity status.
        Used by the health-check endpoint.
        """
        return {
            "mocked": True,
            "status": "reachable",
            "provider": "mock://ganache",
            "chain_id": 1337,
            "latest_block": 0,
        }
