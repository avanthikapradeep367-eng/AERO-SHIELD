"""
AERO-SHIELD X — Threat Intelligence Service (Module 4)
Python wrapper for the EvidenceVault Threat Intelligence on-chain module.

Primary integration point for Member 3 (SentinelX AI / CUDA detection engine).
When SentinelX detects a threat, it calls blacklist_device() here to publish
the IOC to the immutable on-chain ledger, making it available to all
participating nodes in the aerospace network.

Caller (Member 3 — SentinelX AI) example:
    svc = ThreatService()

    # Device is detected as a threat
    svc.blacklist_device(
        device_id="UAV-ALPHA-001",  # Module 1 string ID
        threat_level=8,             # 0–10 severity scale
        risk_score=95,              # 0–100
    )

    # SentinelX refines the threat assessment
    svc.update_threat_profile(
        device_id="UAV-ALPHA-001",
        threat_level=9,
        attack_count=3,
        risk_score=98,
    )

    profile = svc.get_threat_profile("UAV-ALPHA-001")
    print(profile.blacklisted, profile.threat_level)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..blockchain_service import BlockchainService, TransactionResult
from ..exceptions import (
    DeviceNotBlacklistedError,
    ThreatProfileNotFoundError,
    ContractError,
)
from ..utils import (
    bytes32_to_hex,
    device_id_to_bytes32,
    timestamp_to_iso,
)

logger = logging.getLogger(__name__)


@dataclass
class ThreatProfile:
    """Python representation of the on-chain ThreatProfile struct."""
    device_id_bytes: str       # hex string (keccak256 of Module 1 device ID)
    attack_count: int
    last_seen: int             # Unix timestamp
    last_seen_iso: str
    threat_level: int          # 0–10
    risk_score: int            # 0–100
    blacklisted: bool

    @classmethod
    def from_tuple(cls, t: tuple) -> "ThreatProfile":
        """
        Build from the tuple returned by EvidenceVault.getThreatProfile().
        Solidity struct field order:
          (deviceId, attackCount, lastSeen, threatLevel, riskScore, blacklisted, exists)
        """
        last_seen = int(t[2])
        return cls(
            device_id_bytes=bytes32_to_hex(t[0]),
            attack_count=int(t[1]),
            last_seen=last_seen,
            last_seen_iso=timestamp_to_iso(last_seen),
            threat_level=int(t[3]),
            risk_score=int(t[4]),
            blacklisted=bool(t[5]),
        )

    def to_dict(self) -> dict:
        return {
            "device_id_bytes": self.device_id_bytes,
            "attack_count": self.attack_count,
            "last_seen": self.last_seen,
            "last_seen_iso": self.last_seen_iso,
            "threat_level": self.threat_level,
            "risk_score": self.risk_score,
            "blacklisted": self.blacklisted,
        }


class ThreatService:
    """
    Service for Module 4 — Threat Intelligence.
    All methods accept Module 1 string device IDs; bytes32 conversion is
    handled internally using keccak256 for cross-module consistency.
    """

    def __init__(self, blockchain_service: BlockchainService | None = None) -> None:
        self._svc = blockchain_service or BlockchainService()

    # ──────────────────────────────────────────────────────────────
    #  Write operations (onlyOwner)
    # ──────────────────────────────────────────────────────────────

    def blacklist_device(
        self,
        device_id: str,
        threat_level: int,
        risk_score: int,
    ) -> TransactionResult:
        """
        Add a device to the on-chain threat blacklist.
        Simultaneously creates or updates the device's ThreatProfile.

        Args:
            device_id:    Module 1 string device ID (e.g. "UAV-ALPHA-001").
            threat_level: Severity level 0–10 (10 = maximum threat).
            risk_score:   Overall risk score 0–100.

        Returns:
            TransactionResult

        Raises:
            ValueError:         If threat_level or risk_score is out of range.
            GasEstimationError: If the contract rejects the call (device already
                                blacklisted).
        """
        if not 0 <= threat_level <= 10:
            raise ValueError(f"threat_level must be 0–10, got {threat_level}.")
        if not 0 <= risk_score <= 100:
            raise ValueError(f"risk_score must be 0–100, got {risk_score}.")

        device_id_b32 = device_id_to_bytes32(device_id)

        logger.warning(
            "BLACKLISTING device: %s threat_level=%d risk_score=%d",
            device_id,
            threat_level,
            risk_score,
        )

        return self._svc.send_transaction(
            "blacklistDevice",
            device_id_b32,
            int(threat_level),
            int(risk_score),
        )

    def remove_blacklist(self, device_id: str) -> TransactionResult:
        """
        Remove a device from the on-chain blacklist.

        Args:
            device_id: Module 1 string device ID.

        Raises:
            DeviceNotBlacklistedError: If the device is not currently blacklisted.
        """
        if not self.is_blacklisted(device_id):
            raise DeviceNotBlacklistedError(
                f"Device '{device_id}' is not blacklisted.",
                details={"device_id": device_id},
            )

        device_id_b32 = device_id_to_bytes32(device_id)

        logger.info("Removing blacklist for device: %s", device_id)
        return self._svc.send_transaction("removeBlacklist", device_id_b32)

    def update_threat_profile(
        self,
        device_id: str,
        threat_level: int,
        attack_count: int,
        risk_score: int,
    ) -> TransactionResult:
        """
        Update an existing threat profile with refined intelligence data.
        The profile must already exist (created via blacklist_device).

        Args:
            device_id:    Module 1 string device ID.
            threat_level: Updated severity level 0–10.
            attack_count: Updated total confirmed attack count.
            risk_score:   Updated risk score 0–100.

        Raises:
            ValueError: If any score is out of range.
        """
        if not 0 <= threat_level <= 10:
            raise ValueError(f"threat_level must be 0–10, got {threat_level}.")
        if not 0 <= risk_score <= 100:
            raise ValueError(f"risk_score must be 0–100, got {risk_score}.")
        if attack_count < 0:
            raise ValueError(f"attack_count must be >= 0, got {attack_count}.")

        device_id_b32 = device_id_to_bytes32(device_id)

        logger.info(
            "Updating threat profile: %s level=%d attacks=%d risk=%d",
            device_id,
            threat_level,
            attack_count,
            risk_score,
        )

        return self._svc.send_transaction(
            "updateThreatProfile",
            device_id_b32,
            int(threat_level),
            int(attack_count),
            int(risk_score),
        )

    # ──────────────────────────────────────────────────────────────
    #  Read operations (free, no gas)
    # ──────────────────────────────────────────────────────────────

    def get_threat_profile(self, device_id: str) -> ThreatProfile:
        """
        Retrieve the ThreatProfile for a device.

        Raises:
            ThreatProfileNotFoundError: If the device has no threat profile.
        """
        device_id_b32 = device_id_to_bytes32(device_id)
        raw = self._svc.call_function("getThreatProfile", device_id_b32)

        try:
            exists_flag = bool(raw[6])
        except (IndexError, TypeError) as exc:
            raise ContractError(
                f"Unexpected return shape from getThreatProfile('{device_id}'): {raw}",
                details={"raw": str(raw)},
            ) from exc

        if not exists_flag:
            raise ThreatProfileNotFoundError(
                f"No threat profile found for device '{device_id}'.",
                details={"device_id": device_id},
            )

        return ThreatProfile.from_tuple(raw)

    def is_blacklisted(self, device_id: str) -> bool:
        """
        Return True if the device is currently on the on-chain blacklist.
        Safe to call even if no threat profile exists (returns False).
        """
        try:
            device_id_b32 = device_id_to_bytes32(device_id)
            return bool(self._svc.call_function("isBlacklisted", device_id_b32))
        except Exception as exc:
            logger.warning("isBlacklisted check failed for '%s': %s", device_id, exc)
            return False

    def total_threat_devices(self) -> int:
        """Return the total number of devices with a threat profile on-chain."""
        return int(self._svc.call_function("totalThreatDevices"))
