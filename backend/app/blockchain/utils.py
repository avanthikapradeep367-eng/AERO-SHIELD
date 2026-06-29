"""
AERO-SHIELD X — Blockchain Utilities
Type-conversion helpers used across all service layers.

Key conversions
---------------
• hex_to_bytes32   — "0xabc..." / "abc..." → 32-byte object for Solidity bytes32 params
• bytes32_to_hex   — bytes32 result back to "0x..." hex string
• str_to_bytes32   — UTF-8 string → 32-byte left-aligned (use only for short labels)
• bytes32_to_str   — reverse of str_to_bytes32 (strips null padding)
• device_id_to_bytes32  — canonical mapping: string device ID → keccak256 bytes32
                          Modules 2, 3, 4 use bytes32 device IDs; use this function
                          to create a deterministic key from a Module 1 string device ID.

Timestamp helpers
-----------------
• timestamp_to_iso — Unix timestamp (int) → ISO-8601 string
• now_iso          — current UTC time as ISO-8601

Other helpers
-------------
• validate_address     — checksum-validate and return normalised address
• format_gas_cost_eth  — (gas_used, gas_price_wei) → human-readable ETH string
• format_tx_result     — AttributeDict receipt → plain dict for logging / JSON
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from web3 import Web3
from web3.types import TxReceipt


# ──────────────────────────────────────────────────────────────────
#  bytes32 helpers
# ──────────────────────────────────────────────────────────────────

def hex_to_bytes32(hex_str: str) -> bytes:
    """
    Convert a hex string (with or without 0x prefix) to a bytes32 object.
    If the hex value is shorter than 32 bytes it is RIGHT-zero-padded.
    If it is longer it is truncated to the leftmost 32 bytes.

    Use this for: authenticationId, sessionId, incidentId, evidenceHash —
    anything that was originally created as an opaque 32-byte identifier or hash.
    """
    clean = hex_str.replace("0x", "").replace("0X", "").strip()
    if len(clean) % 2:
        clean = "0" + clean
    raw = bytes.fromhex(clean)
    # Pad right or truncate to exactly 32 bytes
    return raw[:32].ljust(32, b"\x00")


def bytes32_to_hex(value: bytes | str) -> str:
    """Return a 0x-prefixed 64-character hex representation of a bytes32 value."""
    if isinstance(value, (bytes, bytearray)):
        return "0x" + value.hex()
    # HexBytes or str already
    s = str(value)
    if not s.startswith("0x"):
        s = "0x" + s
    return s


def str_to_bytes32(text: str) -> bytes:
    """
    Encode a short UTF-8 string into 32 bytes (left-aligned, null-padded).
    Maximum 32 characters; longer strings are silently truncated.

    For a canonical, collision-resistant mapping from an arbitrary string ID
    to bytes32, use device_id_to_bytes32() instead.
    """
    encoded = text.encode("utf-8")[:32]
    return encoded.ljust(32, b"\x00")


def bytes32_to_str(value: bytes | str) -> str:
    """
    Reverse of str_to_bytes32: decode bytes32 back to a UTF-8 string,
    stripping trailing null bytes.
    """
    if isinstance(value, str):
        value = bytes.fromhex(value.replace("0x", ""))
    return value.rstrip(b"\x00").decode("utf-8", errors="replace")


def device_id_to_bytes32(device_id: str) -> bytes:
    """
    Deterministic mapping: human-readable string device ID → 32-byte keccak256 hash.

    Module 1 (Device Registry) stores devices under their string IDs.
    Modules 2, 3, 4 reference devices via bytes32. Use this function to compute
    the canonical bytes32 key from a string device ID so that cross-module
    lookups are consistent.

    Example:
        key = device_id_to_bytes32("UAV-ALPHA-001")
        # pass key to record_authentication(), record_incident(), blacklist_device()
    """
    return Web3.keccak(text=device_id)


# ──────────────────────────────────────────────────────────────────
#  Address helpers
# ──────────────────────────────────────────────────────────────────

_ETH_ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")


def validate_address(address: str) -> str:
    """
    Validate and return the EIP-55 checksummed Ethereum address.
    Raises ValueError if the address is malformed.
    """
    if not _ETH_ADDRESS_RE.match(address):
        raise ValueError(
            f"Invalid Ethereum address: '{address}'. "
            "Expected '0x' followed by 40 hex characters."
        )
    return Web3.to_checksum_address(address)


# ──────────────────────────────────────────────────────────────────
#  Timestamp helpers
# ──────────────────────────────────────────────────────────────────

def timestamp_to_iso(unix_ts: int) -> str:
    """Convert a Unix timestamp (seconds) to an ISO-8601 UTC string."""
    if unix_ts == 0:
        return "1970-01-01T00:00:00+00:00"
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).isoformat()


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(tz=timezone.utc).isoformat()


# ──────────────────────────────────────────────────────────────────
#  Gas / cost helpers
# ──────────────────────────────────────────────────────────────────

def format_gas_cost_eth(gas_used: int, gas_price_wei: int) -> str:
    """
    Return the human-readable ETH cost for a transaction.
    Example: format_gas_cost_eth(21000, 20_000_000_000) → "0.000420000 ETH"
    """
    cost_wei = gas_used * gas_price_wei
    cost_eth = cost_wei / 10**18
    return f"{cost_eth:.9f} ETH"


# ──────────────────────────────────────────────────────────────────
#  Transaction result formatter
# ──────────────────────────────────────────────────────────────────

def format_tx_result(receipt: TxReceipt, gas_price_wei: int = 0) -> dict[str, Any]:
    """
    Convert a Web3.py TxReceipt AttributeDict into a plain dict suitable
    for JSON serialisation and structured logging.
    """
    tx_hash = (
        receipt["transactionHash"].hex()
        if hasattr(receipt.get("transactionHash"), "hex")
        else str(receipt.get("transactionHash", ""))
    )
    gas_used: int = receipt.get("gasUsed", 0)

    result: dict[str, Any] = {
        "tx_hash": tx_hash,
        "block_number": receipt.get("blockNumber"),
        "gas_used": gas_used,
        "status": receipt.get("status"),  # 1 = success, 0 = reverted
        "from": receipt.get("from"),
        "to": receipt.get("to"),
        "contract_address": receipt.get("contractAddress"),
    }
    if gas_price_wei:
        result["gas_cost_eth"] = format_gas_cost_eth(gas_used, gas_price_wei)
    return result


# ──────────────────────────────────────────────────────────────────
#  Auth-status helpers
# ──────────────────────────────────────────────────────────────────

def bool_to_auth_status(success: bool) -> int:
    """
    Convert a Python bool to the uint8 AUTH_SUCCESS / AUTH_FAILED constant
    expected by the EvidenceVault contract (AUTH_FAILED=0, AUTH_SUCCESS=1).
    """
    return 1 if success else 0


def auth_status_to_bool(status: int) -> bool:
    """Reverse of bool_to_auth_status."""
    return status == 1


# ──────────────────────────────────────────────────────────────────
#  Incident status constants (mirrors Solidity contract constants)
# ──────────────────────────────────────────────────────────────────

INCIDENT_OPEN: int          = 0
INCIDENT_INVESTIGATING: int = 1
INCIDENT_RESOLVED: int      = 2
INCIDENT_CLOSED: int        = 3

INCIDENT_STATUS_LABELS: dict[int, str] = {
    INCIDENT_OPEN:          "OPEN",
    INCIDENT_INVESTIGATING: "INVESTIGATING",
    INCIDENT_RESOLVED:      "RESOLVED",
    INCIDENT_CLOSED:        "CLOSED",
}


def incident_status_label(status: int) -> str:
    """Return a human-readable label for an incident status code."""
    return INCIDENT_STATUS_LABELS.get(status, f"UNKNOWN({status})")
