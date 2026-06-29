"""
AERO-SHIELD X — Web3 Client
Singleton Web3 connection with chain-ID verification and auto-reconnect.

Usage (anywhere in the blockchain layer):
    from app.blockchain.web3_client import get_web3, get_account

    w3   = get_web3()          # connected Web3 instance
    acct = get_account()       # loaded eth_account.Account for signing
"""

from __future__ import annotations

import logging
import time
from functools import lru_cache

from eth_account import Account
from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from .config import BlockchainConfig, load_config
from .exceptions import BlockchainConnectionError

logger = logging.getLogger(__name__)

# Maximum connection attempts before raising BlockchainConnectionError
_MAX_RETRIES = 3
# Seconds between retry attempts (exponential: 1, 2, 4)
_RETRY_BACKOFF_BASE = 1.0


@lru_cache(maxsize=1)
def _load_config_once() -> BlockchainConfig:
    """Load config once per process lifetime."""
    return load_config()


def _build_web3(config: BlockchainConfig) -> Web3:
    """
    Create and return a connected Web3 instance.
    Adds PoA middleware — required for Ganache and Clique-based networks whose
    block headers use a non-standard 97-byte extraData field.
    """
    provider = Web3.HTTPProvider(
        config.ganache_rpc_url,
        request_kwargs={"timeout": 30},
    )
    w3 = Web3(provider)

    # Ganache / Clique PoA compatibility
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    return w3


def _verify_chain_id(w3: Web3, expected: int) -> None:
    """Raise BlockchainConnectionError if the node's chain ID does not match config."""
    try:
        actual = w3.eth.chain_id
    except Exception as exc:
        raise BlockchainConnectionError(
            f"Cannot read chain ID from node at {w3.provider}",
            details={"error": str(exc)},
        ) from exc

    if actual != expected:
        raise BlockchainConnectionError(
            f"Chain ID mismatch — config expects {expected} but node reports {actual}. "
            "Check CHAIN_ID in your .env and the Ganache network settings.",
            details={"expected": expected, "actual": actual},
        )


def connect(config: BlockchainConfig | None = None) -> Web3:
    """
    Connect to the Ethereum node with automatic retry.
    Returns a verified, connected Web3 instance.

    Retries up to _MAX_RETRIES times with exponential back-off.
    Raises BlockchainConnectionError if all attempts fail.
    """
    cfg = config or _load_config_once()

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            w3 = _build_web3(cfg)
            if not w3.is_connected():
                raise BlockchainConnectionError(
                    f"Web3.is_connected() returned False for {cfg.ganache_rpc_url}. "
                    "Make sure Ganache is running."
                )
            _verify_chain_id(w3, cfg.chain_id)
            if attempt > 0:
                logger.info("Connected to Ganache on attempt %d", attempt + 1)
            else:
                logger.debug("Connected to Ganache at %s", cfg.ganache_rpc_url)
            return w3

        except BlockchainConnectionError:
            raise  # don't retry configuration errors
        except Exception as exc:
            last_exc = exc
            wait = _RETRY_BACKOFF_BASE * (2 ** attempt)
            logger.warning(
                "Connection attempt %d/%d failed: %s — retrying in %.1fs",
                attempt + 1,
                _MAX_RETRIES,
                exc,
                wait,
            )
            if attempt < _MAX_RETRIES - 1:
                time.sleep(wait)

    raise BlockchainConnectionError(
        f"Failed to connect to Ganache at {cfg.ganache_rpc_url} "
        f"after {_MAX_RETRIES} attempts.",
        details={"last_error": str(last_exc), "rpc_url": cfg.ganache_rpc_url},
    ) from last_exc


def load_account(config: BlockchainConfig | None = None) -> LocalAccount:
    """
    Load the signing account from the configured PRIVATE_KEY.
    Returns an eth_account LocalAccount used to sign transactions.
    """
    cfg = config or _load_config_once()
    try:
        account: LocalAccount = Account.from_key(cfg.private_key)
    except Exception as exc:
        raise BlockchainConnectionError(
            f"Cannot load account from PRIVATE_KEY: {exc}",
            details={"error": str(exc)},
        ) from exc

    logger.debug("Loaded signing account: %s", account.address)
    return account


# ──────────────────────────────────────────────────────────────────
#  Module-level singleton accessors
#
#  These are the primary entry points used by blockchain_service.py
#  and any service that needs a raw Web3 connection.
# ──────────────────────────────────────────────────────────────────

_web3_instance: Web3 | None = None
_account_instance: LocalAccount | None = None


def get_web3() -> Web3:
    """
    Return the module-level singleton Web3 instance, connecting if needed.
    The connection is established once per process and reused thereafter.
    If the node becomes unreachable, the next call will attempt to reconnect.
    """
    global _web3_instance
    if _web3_instance is None or not _web3_instance.is_connected():
        _web3_instance = connect()
    return _web3_instance


def get_account() -> LocalAccount:
    """
    Return the module-level singleton signing account, loading if needed.
    """
    global _account_instance
    if _account_instance is None:
        _account_instance = load_account()
    return _account_instance


def reset_connection() -> None:
    """
    Force the singleton to reconnect on the next get_web3() call.
    Useful in tests or after a known Ganache restart.
    """
    global _web3_instance, _account_instance
    _web3_instance = None
    _account_instance = None
    logger.info("Web3 connection reset; will reconnect on next access.")
