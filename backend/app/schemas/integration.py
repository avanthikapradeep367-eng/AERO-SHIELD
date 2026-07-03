"""
schemas/integration.py — Typed data contracts for inter-service communication.

These Pydantic models represent the structured data that flows between
the backend API gateway and its two external services:

  - BlockchainService  (Member 2 — Hardhat / Solidity)
  - AIService          (Member 3 — SentinelX / PyTorch)

Usage pattern:
    raw = await blockchain.log_attack(...)
    result = BlockchainAttackResult(**raw)   # type-safe parsing of dict

When Member 2 or Member 3 change their response shapes, only the model
here needs to be updated — service consumers stay unchanged.
"""

from pydantic import BaseModel, Field


# ── Blockchain Result Schemas ─────────────────────────────────────────────────

class BlockchainTxBase(BaseModel):
    """Shared fields present in every blockchain transaction result."""

    mocked: bool = Field(..., description="True while the mock service is active")
    tx_hash: str = Field(..., description="On-chain transaction hash (0x-prefixed)")
    block_number: int = Field(..., description="Block number in which the tx was mined")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp of the transaction")


class BlockchainAuthResult(BlockchainTxBase):
    """Typed result from IBlockchainService.log_authentication()."""

    device_id: str = Field(..., description="Device that performed the authentication")
    success: bool = Field(..., description="Whether the authentication succeeded")
    key_version: int = Field(..., description="Rolling key version used")
    session_id: str = Field(..., description="Session correlation identifier")


class BlockchainAttackResult(BlockchainTxBase):
    """Typed result from IBlockchainService.log_attack()."""

    incident_id: str = Field(..., description="Unique incident UUID for correlation")
    device_id: str = Field(..., description="Target device identifier")
    attack_type: str = Field(..., description="Category of the attack")
    risk_score: float = Field(..., description="AI-determined risk score 0–100")
    ai_confidence: float = Field(..., description="AI model confidence 0–100")
    evidence_hash: str = Field(..., description="SHA-256 hash of captured evidence")


class BlockchainDeviceResult(BlockchainTxBase):
    """Typed result from IBlockchainService.register_device()."""

    device_id: str = Field(..., description="Registered device identifier")
    device_type: str = Field(..., description="Hardware category of the device")
    public_key: str | None = Field(None, description="On-chain identity public key")


class BlockchainStatusResult(BaseModel):
    """Typed result from IBlockchainService.get_status()."""

    mocked: bool = Field(..., description="True while the mock service is active")
    status: str = Field(..., description="'reachable' | 'unreachable'")
    provider: str = Field(..., description="Web3 provider URL")
    chain_id: int = Field(..., description="EVM chain identifier")
    latest_block: int = Field(..., description="Most recently confirmed block number")


# ── AI Result Schemas ─────────────────────────────────────────────────────────

class AIAnalysisResult(BaseModel):
    """Typed result from IAIService.analyze_request()."""

    mocked: bool = Field(..., description="True while the mock service is active")
    analysis_id: str = Field(..., description="UUID for correlating the analysis event")
    risk_score: float = Field(..., description="Threat severity score 0–100")
    threat_detected: bool = Field(..., description="True when risk_score exceeds threshold")
    attack_labels: list[str] = Field(..., description="Predicted attack categories")
    ai_confidence: float = Field(..., description="Model confidence percentage 0–100")
    model: str = Field(..., description="Identifier of the model used for inference")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp of the analysis")


class AIStatusResult(BaseModel):
    """Typed result from IAIService.get_status()."""

    mocked: bool = Field(..., description="True while the mock service is active")
    status: str = Field(..., description="'operational' | 'unavailable'")
    model: str = Field(..., description="Active model identifier")
    cuda_available: bool = Field(..., description="Whether GPU acceleration is active")
    device: str = Field(..., description="Compute device description")
