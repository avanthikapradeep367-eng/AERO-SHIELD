"""
interfaces/blockchain_interface.py — Abstract contract for the blockchain service.

Defines the EXACT method signatures that any blockchain implementation
must satisfy. Member 2's real Web3/Hardhat client and Member 1's mock
both implement this interface, guaranteeing the rest of the backend can
swap them without touching a single route or service.

Rules:
  - No logic here — only abstract method stubs.
  - Signatures must match the concrete implementations exactly.
  - Return type is `dict` until Member 2 provides typed result models.
"""

from abc import ABC, abstractmethod


class IBlockchainService(ABC):
    """
    Abstract interface for all blockchain interactions.

    Concrete implementations:
      - app.services.blockchain_service.BlockchainService  (mock — Member 1)
      - app.blockchain.*                                    (real — Member 2)
    """

    @abstractmethod
    async def log_authentication(
        self,
        device_id: str,
        success: bool,
        key_version: int = 1,
        session_id: str | None = None,
    ) -> dict:
        """
        Record a device authentication attempt on the blockchain.

        Args:
            device_id:   Unique device identifier (e.g. "SHIELD-001").
            success:     True if authentication succeeded, False otherwise.
            key_version: Rolling key version number used for this attempt.
            session_id:  Optional session correlation identifier.

        Returns:
            Transaction receipt dict including at minimum:
                tx_hash     str   — on-chain transaction hash
                block_number int  — mined block number
                timestamp   str   — ISO-8601 UTC timestamp
        """

    @abstractmethod
    async def log_attack(
        self,
        device_id: str,
        attack_type: str,
        risk_score: float,
        ai_confidence: float = 0.0,
        evidence_hash: str | None = None,
    ) -> dict:
        """
        Record a detected attack / threat event on the blockchain.

        Args:
            device_id:     Target device identifier.
            attack_type:   Category of attack (e.g. "DDOS", "INJECTION").
            risk_score:    AI-determined risk level in range 0–100.
            ai_confidence: Model confidence percentage 0–100.
            evidence_hash: Optional SHA-256 hash of captured evidence payload.

        Returns:
            Transaction receipt dict including at minimum:
                tx_hash     str   — on-chain transaction hash
                incident_id str   — unique incident correlation UUID
                block_number int  — mined block number
                timestamp   str   — ISO-8601 UTC timestamp
        """

    @abstractmethod
    async def register_device(
        self,
        device_id: str,
        device_type: str = "UAV",
        public_key: str | None = None,
    ) -> dict:
        """
        Register a device on the blockchain device registry.

        Args:
            device_id:   Unique device identifier.
            device_type: Hardware category (e.g. "UAV", "SENSOR").
            public_key:  Optional on-chain identity public key (hex string).

        Returns:
            Transaction receipt dict including at minimum:
                tx_hash     str   — on-chain transaction hash
                block_number int  — mined block number
                timestamp   str   — ISO-8601 UTC timestamp
        """

    @abstractmethod
    async def get_status(self) -> dict:
        """
        Return current connectivity and chain status.

        Returns:
            Status dict including at minimum:
                status       str  — "reachable" | "unreachable"
                chain_id     int  — EVM chain ID
                latest_block int  — most recently confirmed block number
        """
