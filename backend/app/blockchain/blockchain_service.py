"""
AERO-SHIELD X — Core Blockchain Service
Low-level interface for building, signing, sending, and logging transactions.
All four domain service modules (device, authentication, evidence, threat)
delegate every blockchain operation to this class.

Architecture
------------
• BlockchainService owns the Web3 connection, the signing account, and the
  EvidenceVault contract instance.
• send_transaction()  → state-changing calls (onlyOwner functions)
• call_function()     → view / pure reads (no gas, no signing)
• estimate_gas()      → pre-flight gas check (reveals revert reasons early)
• Structured logging  → every transaction logs: timestamp, function, tx hash,
                        gas used, status, execution time, wallet address.

FastAPI integration note
------------------------
Web3.py's HTTP provider is synchronous.  In a FastAPI async route, wrap calls
with asyncio.get_event_loop().run_in_executor() or use a thread-pool to avoid
blocking the event loop:

    import asyncio
    result = await asyncio.get_event_loop().run_in_executor(
        None, device_service.register_device, "UAV-001", "UAV", "0x..."
    )
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from eth_account.signers.local import LocalAccount
from web3 import Web3
from web3.contract import Contract
from web3.exceptions import ContractLogicError

from .config import BlockchainConfig, load_config
from .contract_loader import get_contract
from .exceptions import (
    BlockchainConnectionError,
    GasEstimationError,
    TransactionError,
)
from .utils import format_gas_cost_eth, format_tx_result, now_iso
from .web3_client import get_account, get_web3

logger = logging.getLogger(__name__)


@dataclass
class TransactionResult:
    """Structured result returned by every state-changing blockchain call."""
    tx_hash: str
    block_number: int
    gas_used: int
    status: int           # 1 = success, 0 = reverted
    gas_cost_eth: str
    timestamp: str        # ISO-8601 UTC of when the receipt was received
    function_name: str
    wallet_address: str
    execution_time_ms: float


class BlockchainService:
    """
    Core blockchain service.  Instantiate once and share across domain services.

    Example:
        svc = BlockchainService()
        receipt = svc.send_transaction("registerDevice", "UAV-001", "UAV", "0x...")
    """

    def __init__(self, config: BlockchainConfig | None = None) -> None:
        self._config: BlockchainConfig = config or load_config()
        self._w3: Web3 = get_web3()
        self._account: LocalAccount = get_account()
        self._contract: Contract
        self._contract_address: str
        self._contract, self._contract_address = get_contract(self._config)

        logger.info(
            "BlockchainService initialised | network=%s chain=%d contract=%s wallet=%s",
            self._config.ganache_rpc_url,
            self._config.chain_id,
            self._contract_address,
            self._account.address,
        )

    # ──────────────────────────────────────────────────────────────
    #  Public properties
    # ──────────────────────────────────────────────────────────────

    @property
    def contract(self) -> Contract:
        return self._contract

    @property
    def contract_address(self) -> str:
        return self._contract_address

    @property
    def wallet_address(self) -> str:
        return self._account.address

    @property
    def w3(self) -> Web3:
        return self._w3

    # ──────────────────────────────────────────────────────────────
    #  Core transaction pipeline
    # ──────────────────────────────────────────────────────────────

    def estimate_gas(self, contract_func_call: Any) -> int:
        """
        Estimate gas for a contract function call.
        Raises GasEstimationError if the transaction would revert.
        """
        try:
            gas = contract_func_call.estimate_gas({"from": self._account.address})
            return int(gas * self._config.gas_buffer)
        except ContractLogicError as exc:
            raise GasEstimationError(
                f"Gas estimation failed — transaction would revert: {exc}",
                details={"revert_reason": str(exc)},
            ) from exc
        except Exception as exc:
            raise GasEstimationError(
                f"Gas estimation failed: {exc}",
                details={"error": str(exc)},
            ) from exc

    def send_transaction(
        self,
        function_name: str,
        *args: Any,
    ) -> TransactionResult:
        """
        Build, sign, and send a state-changing transaction.
        Waits for the receipt and returns a TransactionResult.

        Args:
            function_name: Name of the EvidenceVault contract function.
            *args: Positional arguments forwarded to the contract function.

        Returns:
            TransactionResult with tx hash, gas used, block number, etc.

        Raises:
            GasEstimationError: If the transaction would revert.
            TransactionError: If the transaction fails on-chain or times out.
        """
        start = time.monotonic()

        func_call = getattr(self._contract.functions, function_name)(*args)

        gas_limit = self.estimate_gas(func_call)
        gas_price = self._w3.eth.gas_price
        nonce = self._w3.eth.get_transaction_count(self._account.address)

        tx = func_call.build_transaction(
            {
                "from": self._account.address,
                "nonce": nonce,
                "gas": gas_limit,
                "gasPrice": gas_price,
                "chainId": self._config.chain_id,
            }
        )

        signed = self._account.sign_transaction(tx)

        try:
            tx_hash = self._w3.eth.send_raw_transaction(signed.raw_transaction)
        except Exception as exc:
            raise TransactionError(
                f"Failed to send transaction for {function_name}: {exc}",
                details={"function": function_name, "error": str(exc)},
            ) from exc

        tx_hash_hex = tx_hash.hex()
        logger.debug("Tx sent: %s function=%s", tx_hash_hex, function_name)

        try:
            receipt = self._w3.eth.wait_for_transaction_receipt(
                tx_hash,
                timeout=self._config.tx_timeout,
            )
        except Exception as exc:
            raise TransactionError(
                f"Timed out waiting for receipt of {function_name} ({tx_hash_hex}): {exc}",
                tx_hash=tx_hash_hex,
                details={"function": function_name, "timeout_s": self._config.tx_timeout},
            ) from exc

        elapsed_ms = (time.monotonic() - start) * 1000
        gas_used: int = receipt.get("gasUsed", 0)
        status: int = receipt.get("status", 0)
        gas_cost_eth = format_gas_cost_eth(gas_used, gas_price)
        received_at = now_iso()

        result = TransactionResult(
            tx_hash=tx_hash_hex,
            block_number=receipt.get("blockNumber", 0),
            gas_used=gas_used,
            status=status,
            gas_cost_eth=gas_cost_eth,
            timestamp=received_at,
            function_name=function_name,
            wallet_address=self._account.address,
            execution_time_ms=round(elapsed_ms, 2),
        )

        self._log_transaction(result)

        if status == 0:
            raise TransactionError(
                f"Transaction reverted on-chain: {function_name} ({tx_hash_hex})",
                tx_hash=tx_hash_hex,
                details=format_tx_result(receipt, gas_price),
            )

        return result

    def call_function(self, function_name: str, *args: Any) -> Any:
        """
        Call a view or pure contract function (no signing, no gas cost).

        Args:
            function_name: Name of the EvidenceVault contract function.
            *args: Positional arguments forwarded to the contract function.

        Returns:
            The decoded return value from the contract.
        """
        try:
            return getattr(self._contract.functions, function_name)(*args).call()
        except ContractLogicError as exc:
            from .exceptions import ContractError
            raise ContractError(
                f"Contract call reverted: {function_name} — {exc}",
                details={"function": function_name, "revert": str(exc)},
            ) from exc
        except Exception as exc:
            from .exceptions import ContractError
            raise ContractError(
                f"Contract call failed: {function_name} — {exc}",
                details={"function": function_name, "error": str(exc)},
            ) from exc

    # ──────────────────────────────────────────────────────────────
    #  Infrastructure helpers
    # ──────────────────────────────────────────────────────────────

    def verify_connection(self) -> dict[str, Any]:
        """
        Check connection status and return a diagnostic snapshot.
        Safe to call at application startup or in a health-check endpoint.
        """
        try:
            connected = self._w3.is_connected()
            block_number = self._w3.eth.block_number if connected else None
            chain_id = self._w3.eth.chain_id if connected else None
            balance_wei = (
                self._w3.eth.get_balance(self._account.address) if connected else None
            )
            balance_eth = f"{balance_wei / 10 ** 18:.6f} ETH" if balance_wei is not None else None
        except Exception as exc:
            raise BlockchainConnectionError(
                f"Connection verification failed: {exc}",
                details={"error": str(exc)},
            ) from exc

        return {
            "connected": connected,
            "rpc_url": self._config.ganache_rpc_url,
            "chain_id": chain_id,
            "block_number": block_number,
            "contract_address": self._contract_address,
            "wallet_address": self._account.address,
            "wallet_balance": balance_eth,
            "timestamp": now_iso(),
        }

    def get_balance(self, address: str | None = None) -> str:
        """Return the ETH balance of address (defaults to wallet address)."""
        addr = address or self._account.address
        try:
            wei = self._w3.eth.get_balance(self._w3.to_checksum_address(addr))
        except Exception as exc:
            raise BlockchainConnectionError(
                f"Cannot fetch balance for {addr}: {exc}",
                details={"address": addr},
            ) from exc
        return f"{wei / 10 ** 18:.6f} ETH"

    def get_block_number(self) -> int:
        """Return the latest confirmed block number."""
        try:
            return self._w3.eth.block_number
        except Exception as exc:
            raise BlockchainConnectionError(
                f"Cannot fetch block number: {exc}",
                details={"error": str(exc)},
            ) from exc

    def get_transaction(self, tx_hash: str) -> dict[str, Any]:
        """Return raw transaction details by hash."""
        try:
            tx = self._w3.eth.get_transaction(tx_hash)
            return dict(tx)
        except Exception as exc:
            raise TransactionError(
                f"Cannot fetch transaction {tx_hash}: {exc}",
                tx_hash=tx_hash,
                details={"error": str(exc)},
            ) from exc

    # ──────────────────────────────────────────────────────────────
    #  Structured transaction logging
    # ──────────────────────────────────────────────────────────────

    @staticmethod
    def _log_transaction(result: TransactionResult) -> None:
        log_level = logging.INFO if result.status == 1 else logging.ERROR
        logger.log(
            log_level,
            "TX | function=%-30s status=%s tx=%s block=%s gas=%d (%s) time=%.1fms wallet=%s",
            result.function_name,
            "SUCCESS" if result.status == 1 else "REVERTED",
            result.tx_hash,
            result.block_number,
            result.gas_used,
            result.gas_cost_eth,
            result.execution_time_ms,
            result.wallet_address,
        )
