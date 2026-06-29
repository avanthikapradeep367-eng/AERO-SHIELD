"""
AERO-SHIELD X — Blockchain Exception Hierarchy
Custom exceptions for every failure mode in the blockchain integration layer.
All exceptions inherit from BlockchainBaseError so callers can catch them
with a single broad clause when appropriate.
"""


class BlockchainBaseError(Exception):
    """
    Root exception for all blockchain-related errors.
    Carries an optional `details` dict for structured error context that
    can be serialised into API error responses.
    """
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} | details={self.details}"
        return self.message


# ──────────────────────────────────────────────────────────────────
#  Infrastructure exceptions
# ──────────────────────────────────────────────────────────────────

class BlockchainConnectionError(BlockchainBaseError):
    """
    Raised when the Web3 provider (Ganache) cannot be reached, or when
    the chain ID returned by the node does not match the configured value.
    """


class ContractNotFoundError(BlockchainBaseError):
    """
    Raised when the ABI file or deployment JSON cannot be located on disk.
    Run 'npm run deploy:ganache' in the blockchain/ directory first.
    """


class ABIError(BlockchainBaseError):
    """
    Raised when the ABI file exists but is missing, malformed, or does not
    contain a valid ABI array that Web3.py can parse.
    """


# ──────────────────────────────────────────────────────────────────
#  Transaction exceptions
# ──────────────────────────────────────────────────────────────────

class GasEstimationError(BlockchainBaseError):
    """
    Raised when eth_estimateGas fails.
    This almost always means the transaction would revert — the Solidity
    require() message is included in the exception detail when available.
    """


class TransactionError(BlockchainBaseError):
    """
    Raised when a signed transaction is rejected by the node or when the
    on-chain receipt shows status == 0 (reverted).
    Carries the transaction hash in `tx_hash` when available.
    """
    def __init__(
        self,
        message: str,
        tx_hash: str | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message, details)
        self.tx_hash = tx_hash


class ContractError(BlockchainBaseError):
    """
    General-purpose smart contract interaction error.
    Used as a base for module-specific exceptions below.
    """


# ──────────────────────────────────────────────────────────────────
#  Module 1 — Device Registry
# ──────────────────────────────────────────────────────────────────

class DeviceNotFoundError(ContractError):
    """Raised when getDevice() is called for an ID that is not registered."""


class DuplicateDeviceError(ContractError):
    """Raised when registerDevice() is called for an ID that already exists."""


# ──────────────────────────────────────────────────────────────────
#  Module 2 — Authentication Ledger
# ──────────────────────────────────────────────────────────────────

class AuthRecordNotFoundError(ContractError):
    """Raised when getAuthentication() is called for an ID that does not exist."""


class DuplicateAuthRecordError(ContractError):
    """Raised when recordAuthentication() is called for an ID already on-chain."""


# ──────────────────────────────────────────────────────────────────
#  Module 3 — Evidence Vault
# ──────────────────────────────────────────────────────────────────

class IncidentNotFoundError(ContractError):
    """Raised when getIncident() is called for an ID that has not been recorded."""


class DuplicateIncidentError(ContractError):
    """Raised when recordIncident() is called for an ID already in the vault."""


class EvidenceTamperingError(ContractError):
    """
    Raised by verify_evidence() when the supplied hash does not match the
    hash sealed in the on-chain IncidentRecord — indicating tampering.
    """


# ──────────────────────────────────────────────────────────────────
#  Module 4 — Threat Intelligence
# ──────────────────────────────────────────────────────────────────

class ThreatProfileNotFoundError(ContractError):
    """Raised when getThreatProfile() is called for a device with no threat entry."""


class DeviceNotBlacklistedError(ContractError):
    """Raised when removeBlacklist() is called for a device that is not blacklisted."""
