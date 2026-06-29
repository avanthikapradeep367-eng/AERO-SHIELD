"""
AERO-SHIELD X — Blockchain Configuration
Loads and validates all blockchain-related environment variables.
Provides a single immutable BlockchainConfig object used throughout the layer.

Required env vars:
    PRIVATE_KEY      — Ganache account private key (0x-prefixed hex)
    WALLET_ADDRESS   — Corresponding Ethereum address (or derived from PRIVATE_KEY)

Optional env vars (have sensible defaults):
    GANACHE_RPC_URL  — defaults to http://127.0.0.1:7545
    CHAIN_ID         — defaults to 1337
    CONTRACT_ADDRESS — read from deployment/EvidenceVault.json if absent
    ABI_PATH         — override ABI file location
    DEPLOYMENT_PATH  — override deployment file location
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .exceptions import BlockchainConnectionError, ContractNotFoundError

# Repo root is 3 levels above this file:
#   AERO-SHIELD/backend/app/blockchain/config.py
#                         ↑          ↑        ↑
#              .parent  .parent  .parent  → AERO-SHIELD/
_THIS_DIR = Path(__file__).parent
_REPO_ROOT = _THIS_DIR.parent.parent.parent


@dataclass(frozen=True)
class BlockchainConfig:
    """Immutable configuration snapshot used by all blockchain services."""

    ganache_rpc_url: str
    private_key: str
    wallet_address: str
    chain_id: int
    contract_address: str   # may be empty string; contract_loader fills this
    abi_path: Path
    deployment_path: Path
    gas_buffer: float       # multiplier on estimated gas (default 1.2 = 20 % safety margin)
    tx_timeout: int         # seconds to wait for a transaction receipt


def _resolve_abi_path() -> Path:
    """
    Search order for the ABI file:
    1. ABI_PATH environment variable (absolute or relative to CWD)
    2. backend/app/blockchain/abi/EvidenceVault.json  (local copy)
    3. blockchain/abi/EvidenceVault.json               (Hardhat output)
    """
    env_path = os.getenv("ABI_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        raise ContractNotFoundError(
            f"ABI_PATH is set but file not found: {p}",
            details={"ABI_PATH": env_path},
        )

    local = _THIS_DIR / "abi" / "EvidenceVault.json"
    if local.exists():
        return local

    hardhat = _REPO_ROOT / "blockchain" / "abi" / "EvidenceVault.json"
    if hardhat.exists():
        return hardhat

    raise ContractNotFoundError(
        "EvidenceVault ABI not found. Run 'npm run deploy:ganache' in the "
        "blockchain/ directory, or set the ABI_PATH environment variable.\n"
        f"  Tried: {local}\n"
        f"  Tried: {hardhat}",
    )


def _resolve_deployment_path() -> Path:
    """
    Search order for the deployment record:
    1. DEPLOYMENT_PATH environment variable
    2. backend/app/blockchain/deployment/EvidenceVault.json  (local copy)
    3. blockchain/deployment/EvidenceVault.json               (Hardhat output)
    """
    env_path = os.getenv("DEPLOYMENT_PATH")
    if env_path:
        p = Path(env_path)
        if p.exists():
            return p
        raise ContractNotFoundError(
            f"DEPLOYMENT_PATH is set but file not found: {p}",
            details={"DEPLOYMENT_PATH": env_path},
        )

    local = _THIS_DIR / "deployment" / "EvidenceVault.json"
    if local.exists():
        return local

    hardhat = _REPO_ROOT / "blockchain" / "deployment" / "EvidenceVault.json"
    if hardhat.exists():
        return hardhat

    raise ContractNotFoundError(
        "EvidenceVault deployment record not found. Run 'npm run deploy:ganache' "
        "in the blockchain/ directory, or set the DEPLOYMENT_PATH environment variable.\n"
        f"  Tried: {local}\n"
        f"  Tried: {hardhat}",
    )


def _derive_address_from_key(private_key: str) -> str:
    """Derive the checksummed Ethereum address from a private key."""
    try:
        from eth_account import Account  # bundled with web3
        acct = Account.from_key(private_key)
        return acct.address
    except Exception as exc:
        raise BlockchainConnectionError(
            f"Cannot derive wallet address from PRIVATE_KEY: {exc}",
            details={"error": str(exc)},
        ) from exc


def load_config() -> BlockchainConfig:
    """
    Load and validate blockchain configuration from environment variables.
    Raises BlockchainConnectionError or ContractNotFoundError on failure.
    """
    private_key = os.getenv("PRIVATE_KEY", "").strip()
    if not private_key:
        raise BlockchainConnectionError(
            "PRIVATE_KEY environment variable is not set. "
            "Copy backend/.env.example to backend/.env and fill in your "
            "Ganache private key."
        )
    if not private_key.startswith("0x"):
        private_key = "0x" + private_key

    # Wallet address can be supplied explicitly or derived from the private key.
    wallet_address = os.getenv("WALLET_ADDRESS", "").strip()
    if not wallet_address:
        wallet_address = _derive_address_from_key(private_key)

    ganache_rpc_url = os.getenv("GANACHE_RPC_URL", "http://127.0.0.1:7545").strip()
    chain_id = int(os.getenv("CHAIN_ID", "1337"))
    contract_address = os.getenv("CONTRACT_ADDRESS", "").strip()

    gas_buffer = float(os.getenv("BLOCKCHAIN_GAS_BUFFER", "1.2"))
    tx_timeout = int(os.getenv("BLOCKCHAIN_TX_TIMEOUT", "120"))

    abi_path = _resolve_abi_path()
    deployment_path = _resolve_deployment_path()

    return BlockchainConfig(
        ganache_rpc_url=ganache_rpc_url,
        private_key=private_key,
        wallet_address=wallet_address,
        chain_id=chain_id,
        contract_address=contract_address,
        abi_path=abi_path,
        deployment_path=deployment_path,
        gas_buffer=gas_buffer,
        tx_timeout=tx_timeout,
    )
