"""
AERO-SHIELD X — Device Registry Service (Module 1)
Python wrapper for the EvidenceVault Device Registry on-chain module.

All device IDs are plain strings (e.g. "UAV-ALPHA-001") as stored by the
Solidity mapping(string => DeviceRecord).  No bytes32 conversion is needed
for Module 1.

Caller (Member 1 / Member 3) example:
    svc = DeviceService()
    svc.register_device("UAV-ALPHA-001", "UAV", "0x04abc...")
    info = svc.get_device("UAV-ALPHA-001")
    print(info.device_type, info.active)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..blockchain_service import BlockchainService, TransactionResult
from ..exceptions import (
    DeviceNotFoundError,
    DuplicateDeviceError,
    ContractError,
)
from ..utils import timestamp_to_iso

logger = logging.getLogger(__name__)


@dataclass
class DeviceRecord:
    """Python representation of the on-chain DeviceRecord struct."""
    device_id: str
    device_type: str
    public_key: str
    owner: str            # Ethereum address of the registering account
    active: bool
    registered_at: int    # Unix timestamp
    updated_at: int       # Unix timestamp of last status change
    # registered_at_iso / updated_at_iso are derived for convenience
    registered_at_iso: str
    updated_at_iso: str

    @classmethod
    def from_tuple(cls, t: tuple) -> "DeviceRecord":
        """
        Build from the tuple returned by EvidenceVault.getDevice().
        Solidity struct field order:
          (deviceId, deviceType, publicKey, owner, active, registeredAt, updatedAt, exists)
        """
        registered_at = int(t[5])
        updated_at = int(t[6])
        return cls(
            device_id=t[0],
            device_type=t[1],
            public_key=t[2],
            owner=t[3],
            active=bool(t[4]),
            registered_at=registered_at,
            updated_at=updated_at,
            registered_at_iso=timestamp_to_iso(registered_at),
            updated_at_iso=timestamp_to_iso(updated_at),
        )

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "public_key": self.public_key,
            "owner": self.owner,
            "active": self.active,
            "registered_at": self.registered_at,
            "updated_at": self.updated_at,
            "registered_at_iso": self.registered_at_iso,
            "updated_at_iso": self.updated_at_iso,
        }


class DeviceService:
    """
    Service for Module 1 — Device Registry.
    All methods that change state require the wallet to be the contract owner
    (set during deployment).
    """

    def __init__(self, blockchain_service: BlockchainService | None = None) -> None:
        self._svc = blockchain_service or BlockchainService()

    # ──────────────────────────────────────────────────────────────
    #  Write operations (onlyOwner)
    # ──────────────────────────────────────────────────────────────

    def register_device(
        self,
        device_id: str,
        device_type: str,
        public_key: str,
    ) -> TransactionResult:
        """
        Register a new aerospace device on-chain.

        Args:
            device_id:   Human-readable unique identifier, e.g. "UAV-ALPHA-001".
                         Must not already exist; raises DuplicateDeviceError otherwise.
            device_type: Category string — "UAV" | "AIRCRAFT" | "GROUND_STATION"
                         | "SATELLITE_GW" | "IOT_NODE" (or any custom string).
            public_key:  Hex-encoded public key used for rolling-key authentication.

        Returns:
            TransactionResult with tx hash, block number, gas used.

        Raises:
            DuplicateDeviceError: If device_id already exists on-chain.
            GasEstimationError:   If the transaction would revert for any other reason.
            TransactionError:     If the on-chain transaction fails.
        """
        if not device_id or not device_id.strip():
            raise ValueError("device_id must not be empty.")
        if not device_type or not device_type.strip():
            raise ValueError("device_type must not be empty.")
        if not public_key or not public_key.strip():
            raise ValueError("public_key must not be empty.")

        if self.device_exists(device_id):
            raise DuplicateDeviceError(
                f"Device '{device_id}' is already registered on-chain.",
                details={"device_id": device_id},
            )

        logger.info("Registering device: %s type=%s", device_id, device_type)
        return self._svc.send_transaction(
            "registerDevice",
            device_id,
            device_type,
            public_key,
        )

    def update_device_status(
        self,
        device_id: str,
        active: bool,
    ) -> TransactionResult:
        """
        Activate or deactivate a registered device.

        Args:
            device_id: Must already exist; raises DeviceNotFoundError otherwise.
            active:    True = activate, False = deactivate/suspend.

        Returns:
            TransactionResult
        """
        if not self.device_exists(device_id):
            raise DeviceNotFoundError(
                f"Device '{device_id}' not found in the registry.",
                details={"device_id": device_id},
            )

        action = "Activating" if active else "Deactivating"
        logger.info("%s device: %s", action, device_id)
        return self._svc.send_transaction(
            "updateDeviceStatus",
            device_id,
            active,
        )

    # ──────────────────────────────────────────────────────────────
    #  Read operations (free, no gas)
    # ──────────────────────────────────────────────────────────────

    def get_device(self, device_id: str) -> DeviceRecord:
        """
        Retrieve the full DeviceRecord for a registered device.

        Raises:
            DeviceNotFoundError: If no device with this ID exists.
        """
        raw = self._svc.call_function("getDevice", device_id)
        # raw is a tuple; check the 'exists' flag (index 7)
        try:
            exists_flag = bool(raw[7])
        except (IndexError, TypeError) as exc:
            raise ContractError(
                f"Unexpected return shape from getDevice('{device_id}'): {raw}",
                details={"raw": str(raw)},
            ) from exc

        if not exists_flag:
            raise DeviceNotFoundError(
                f"Device '{device_id}' not found in the registry.",
                details={"device_id": device_id},
            )

        return DeviceRecord.from_tuple(raw)

    def device_exists(self, device_id: str) -> bool:
        """Return True if the device ID is already registered on-chain."""
        try:
            return bool(self._svc.call_function("deviceExists", device_id))
        except Exception as exc:
            logger.warning("deviceExists check failed for '%s': %s", device_id, exc)
            return False

    def is_registered_owner(self, address: str) -> bool:
        """
        Return True if the given Ethereum address has registered at least one device.
        Useful for access-control checks on the Python side.
        """
        try:
            return bool(
                self._svc.call_function(
                    "isRegisteredOwner",
                    self._svc.w3.to_checksum_address(address),
                )
            )
        except Exception as exc:
            logger.warning("isRegisteredOwner failed for '%s': %s", address, exc)
            return False

    def total_devices(self) -> int:
        """Return the total number of registered devices."""
        return int(self._svc.call_function("totalDevices"))

    def get_registered_devices(self) -> list[str]:
        """Return the complete list of all registered device IDs."""
        result = self._svc.call_function("getRegisteredDevices")
        return list(result) if result else []
