"""
services/blockchain_service.py — Blockchain integration interface layer.

This module is a MOCK / PLACEHOLDER owned by Member 1 (Backend).
It defines the contract that the real blockchain client (Member 2)
will fulfil once the Hardhat + Solidity layer is ready for integration.

DO NOT implement real blockchain logic here.
DO NOT import from app.blockchain.*  — that package belongs to Member 2.

When Member 2 is ready, replace the return values with actual calls to
the authentication_service, threat_service, and device_service that
live in app/blockchain/services/.
"""

import logging
import uuid
from datetime import datetime, timezone

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
        Log a detected attack / threat event to the blockchain.

        Args:
            device_id:     Target device identifier.
            attack_type:   Category of attack (e.g. "DDOS", "INJECTION").
            risk_score:    AI-determined risk level (0–100).
            ai_confidence: Confidence percentage of the AI model.
            evidence_hash: Optional SHA-256 hash of captured evidence.

        Returns:
            Mocked transaction receipt dict.
        """
        mock_tx = f"0x{uuid.uuid4().hex}{uuid.uuid4().hex[:32]}"
        incident_id = str(uuid.uuid4())
        logger.warning(
            "[MOCK] blockchain.log_attack | device=%s type=%s risk=%.1f tx=%s",
            device_id,
            attack_type,
            risk_score,
            mock_tx,
        )
        return {
            "mocked": True,
            "tx_hash": mock_tx,
            "incident_id": incident_id,
            "device_id": device_id,
            "attack_type": attack_type,
            "risk_score": risk_score,
            "ai_confidence": ai_confidence,
            "evidence_hash": evidence_hash or f"0x{uuid.uuid4().hex}",
            "block_number": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
