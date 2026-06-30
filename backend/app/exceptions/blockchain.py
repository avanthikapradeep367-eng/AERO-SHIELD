"""
exceptions/blockchain.py — Blockchain integration exceptions.

Raised by Member 1's mock service today; will be raised by the real
Web3/Hardhat integration (Member 2) once that layer is live.

HTTP 503 — provider unreachable (client can retry later).
HTTP 502 — provider reachable but transaction reverted (bad gateway).
"""

from fastapi import HTTPException, status


class BlockchainError(HTTPException):
    """Base class for all blockchain-related failures."""

    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
    ):
        super().__init__(status_code=status_code, detail=detail)


class BlockchainConnectionError(BlockchainError):
    """Raised when the Web3 provider (Ganache / mainnet) is unreachable."""

    def __init__(self, provider: str = ""):
        detail = "Blockchain provider is unreachable. The service will retry automatically."
        if provider:
            detail += f" Provider: {provider}"
        super().__init__(detail=detail)


class BlockchainTransactionError(BlockchainError):
    """Raised when a transaction is submitted but reverts or fails to mine."""

    def __init__(self, function_name: str, reason: str = ""):
        detail = f"Blockchain transaction failed in '{function_name}'."
        if reason:
            detail += f" Reason: {reason}"
        super().__init__(
            detail=detail,
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class BlockchainContractError(BlockchainError):
    """Raised when the smart contract rejects a call (e.g. duplicate record, onlyOwner)."""

    def __init__(self, contract: str, reason: str = ""):
        detail = f"Smart contract '{contract}' rejected the call."
        if reason:
            detail += f" Reason: {reason}"
        super().__init__(
            detail=detail,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
