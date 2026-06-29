"""
AERO-SHIELD X — Contract Loader
Reads the ABI and deployment JSON produced by Hardhat deploy.js and returns
a Web3 Contract instance ready for use by all service modules.

The loader validates the ABI structure, resolves the contract address
(from deployment file or CONTRACT_ADDRESS env var), and caches the
contract instance per process to avoid redundant file I/O.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from web3 import Web3
from web3.contract import Contract

from .config import BlockchainConfig, load_config
from .exceptions import ABIError, ContractNotFoundError
from .web3_client import get_web3

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
#  ABI / deployment JSON readers
# ──────────────────────────────────────────────────────────────────

def load_abi(abi_path: Path) -> list[dict]:
    """
    Read and return the ABI array from an ABI JSON file.

    The file may be in either of two formats:
      • {"abi": [...], ...}  — produced by deploy.js (metadata wrapper)
      • [...]                — bare ABI array
    """
    try:
        raw = abi_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ABIError(
            f"Cannot read ABI file at {abi_path}: {exc}",
            details={"path": str(abi_path), "error": str(exc)},
        ) from exc

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ABIError(
            f"ABI file at {abi_path} is not valid JSON: {exc}",
            details={"path": str(abi_path)},
        ) from exc

    # Handle both formats
    if isinstance(parsed, list):
        abi = parsed
    elif isinstance(parsed, dict) and "abi" in parsed:
        abi = parsed["abi"]
    else:
        raise ABIError(
            f"Unexpected ABI file structure in {abi_path}. "
            "Expected a JSON array or an object with an 'abi' key.",
            details={"path": str(abi_path), "top_level_keys": list(parsed.keys())},
        )

    if not isinstance(abi, list) or len(abi) == 0:
        raise ABIError(
            f"ABI in {abi_path} is empty or not an array.",
            details={"path": str(abi_path)},
        )

    logger.debug("Loaded ABI with %d entries from %s", len(abi), abi_path)
    return abi


def load_deployment(deployment_path: Path) -> dict:
    """
    Read and return the deployment record JSON.
    The file must contain a 'contractAddress' key.
    """
    try:
        raw = deployment_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ContractNotFoundError(
            f"Cannot read deployment file at {deployment_path}: {exc}",
            details={"path": str(deployment_path), "error": str(exc)},
        ) from exc

    try:
        record: dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ContractNotFoundError(
            f"Deployment file at {deployment_path} is not valid JSON: {exc}",
            details={"path": str(deployment_path)},
        ) from exc

    if "contractAddress" not in record:
        raise ContractNotFoundError(
            f"Deployment file at {deployment_path} is missing 'contractAddress' key. "
            "Re-deploy with 'npm run deploy:ganache' in the blockchain/ directory.",
            details={"path": str(deployment_path), "keys_found": list(record.keys())},
        )

    logger.debug(
        "Loaded deployment record: address=%s network=%s",
        record["contractAddress"],
        record.get("network", "unknown"),
    )
    return record


# ──────────────────────────────────────────────────────────────────
#  Contract factory
# ──────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _cached_contract(abi_path_str: str, deployment_path_str: str) -> tuple[Contract, str]:
    """
    Internal cached factory.
    Returns (contract, contract_address) after the first call.
    lru_cache keys on the string paths so a fresh deployment (new path) busts the cache.
    """
    abi_path = Path(abi_path_str)
    deployment_path = Path(deployment_path_str)
    w3 = get_web3()

    abi = load_abi(abi_path)

    deployment = load_deployment(deployment_path)
    raw_address = deployment["contractAddress"]

    try:
        address = Web3.to_checksum_address(raw_address)
    except Exception as exc:
        raise ContractNotFoundError(
            f"Invalid contractAddress in deployment file: '{raw_address}'",
            details={"address": raw_address, "error": str(exc)},
        ) from exc

    contract: Contract = w3.eth.contract(address=address, abi=abi)
    logger.info("Contract loaded: EvidenceVault @ %s", address)
    return contract, address


def get_contract(config: BlockchainConfig | None = None) -> tuple[Contract, str]:
    """
    Return a (contract, address) pair for EvidenceVault.

    The contract instance is cached for the process lifetime.
    The CONTRACT_ADDRESS env var overrides the deployment file when set.

    Args:
        config: BlockchainConfig instance; loads from env if None.

    Returns:
        (web3.contract.Contract, checksummed_address)
    """
    cfg = config or load_config()

    # If CONTRACT_ADDRESS is set in env, patch the deployment file value at runtime
    # without modifying the file.  We do this by loading the contract directly.
    if cfg.contract_address:
        try:
            address = Web3.to_checksum_address(cfg.contract_address)
        except Exception as exc:
            raise ContractNotFoundError(
                f"CONTRACT_ADDRESS env var is invalid: '{cfg.contract_address}'",
                details={"error": str(exc)},
            ) from exc

        w3 = get_web3()
        abi = load_abi(cfg.abi_path)
        contract: Contract = w3.eth.contract(address=address, abi=abi)
        logger.info(
            "Contract loaded from CONTRACT_ADDRESS env var: EvidenceVault @ %s",
            address,
        )
        return contract, address

    return _cached_contract(
        str(cfg.abi_path),
        str(cfg.deployment_path),
    )
