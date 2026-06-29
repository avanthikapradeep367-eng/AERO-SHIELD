"""
AERO-SHIELD X — Evidence Vault Service (Module 3)
Python wrapper for the EvidenceVault on-chain forensic evidence module.

This service anchors digital forensic evidence by storing a cryptographic
hash on-chain.  Once committed, the evidenceHash is sealed and can never
be updated — making tampering detectable.

IncidentInput struct mapping
-----------------------------
The Solidity recordIncident() function takes a single IncidentInput calldata
struct to avoid the EVM 16-slot stack limit.  In Web3.py this is passed as
a Python tuple in the exact field order defined in the struct:

    (incidentId, attackType, sourceDevice, targetDevice,
     riskScore, aiConfidence, actionTaken, evidenceHash)

Caller (Member 3 — SentinelX AI) example:
    svc = EvidenceService()

    result = svc.record_incident(
        incident_id="0xdeadbeef...",       # unique hex bytes32
        attack_type="GPS_SPOOFING",
        source_device="UAV-ALPHA-001",     # Module 1 string ID
        target_device="GROUND-GCS-001",    # Module 1 string ID
        risk_score=87,                     # 0–100
        ai_confidence=94,                  # 0–100
        action_taken="QUARANTINE_ISSUED",
        evidence_hash="0xsha256hashhere",  # SHA-256 of the evidence file
    )
    print(result.tx_hash)

    incident = svc.get_incident("0xdeadbeef...")
    verified  = svc.verify_evidence("0xdeadbeef...", "0xsha256hashhere")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from ..blockchain_service import BlockchainService, TransactionResult
from ..exceptions import (
    DuplicateIncidentError,
    EvidenceTamperingError,
    IncidentNotFoundError,
    ContractError,
)
from ..utils import (
    bytes32_to_hex,
    device_id_to_bytes32,
    hex_to_bytes32,
    incident_status_label,
    timestamp_to_iso,
)

logger = logging.getLogger(__name__)


@dataclass
class IncidentRecord:
    """Python representation of the on-chain IncidentRecord struct."""
    incident_id: str           # hex string
    source_device: str         # hex string (keccak256 of Module 1 device ID)
    target_device: str         # hex string (keccak256 of Module 1 device ID)
    evidence_hash: str         # hex string (SHA-256 of evidence file)
    timestamp: int             # Unix timestamp
    timestamp_iso: str
    attack_type: str
    action_taken: str
    risk_score: int            # 0–100
    ai_confidence: int         # 0–100
    status: int                # 0=OPEN 1=INVESTIGATING 2=RESOLVED 3=CLOSED
    status_label: str

    @classmethod
    def from_tuple(cls, t: tuple) -> "IncidentRecord":
        """
        Build from the tuple returned by EvidenceVault.getIncident().
        Solidity struct field order:
          (incidentId, sourceDevice, targetDevice, evidenceHash, timestamp,
           attackType, actionTaken, riskScore, aiConfidence, status, exists)
        """
        ts = int(t[4])
        status = int(t[9])
        return cls(
            incident_id=bytes32_to_hex(t[0]),
            source_device=bytes32_to_hex(t[1]),
            target_device=bytes32_to_hex(t[2]),
            evidence_hash=bytes32_to_hex(t[3]),
            timestamp=ts,
            timestamp_iso=timestamp_to_iso(ts),
            attack_type=t[5],
            action_taken=t[6],
            risk_score=int(t[7]),
            ai_confidence=int(t[8]),
            status=status,
            status_label=incident_status_label(status),
        )

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "source_device": self.source_device,
            "target_device": self.target_device,
            "evidence_hash": self.evidence_hash,
            "timestamp": self.timestamp,
            "timestamp_iso": self.timestamp_iso,
            "attack_type": self.attack_type,
            "action_taken": self.action_taken,
            "risk_score": self.risk_score,
            "ai_confidence": self.ai_confidence,
            "status": self.status,
            "status_label": self.status_label,
        }


class EvidenceService:
    """
    Service for Module 3 — Evidence Vault.
    Provides tamper-evident forensic incident recording and verification.
    """

    def __init__(self, blockchain_service: BlockchainService | None = None) -> None:
        self._svc = blockchain_service or BlockchainService()

    # ──────────────────────────────────────────────────────────────
    #  Write operations (onlyOwner)
    # ──────────────────────────────────────────────────────────────

    def record_incident(
        self,
        incident_id: str,
        attack_type: str,
        source_device: str,
        target_device: str,
        risk_score: int,
        ai_confidence: int,
        action_taken: str,
        evidence_hash: str,
    ) -> TransactionResult:
        """
        Record a new security incident and seal its evidence hash on-chain.

        The evidenceHash is immutable once committed — it can never be changed,
        which means any tampering with the original evidence file will be
        detectable via verify_evidence().

        Args:
            incident_id:    Unique 32-byte identifier (0x-prefixed hex string).
                            Typically sha256(incident_data) or a UUID converted to hex.
            attack_type:    Attack category string (e.g. "GPS_SPOOFING", "REPLAY_ATTACK").
            source_device:  Module 1 string device ID of the attacker/originating device.
            target_device:  Module 1 string device ID of the target device.
            risk_score:     AI-assessed risk level 0–100.
            ai_confidence:  Model confidence percentage 0–100.
            action_taken:   Response action string (e.g. "QUARANTINE_ISSUED").
            evidence_hash:  SHA-256 or SHA-3 hash of the evidence package (hex string).

        Returns:
            TransactionResult

        Raises:
            DuplicateIncidentError: If incident_id already exists on-chain.
            ValueError:             If risk_score or ai_confidence is out of range.
        """
        if not 0 <= risk_score <= 100:
            raise ValueError(f"risk_score must be 0–100, got {risk_score}.")
        if not 0 <= ai_confidence <= 100:
            raise ValueError(f"ai_confidence must be 0–100, got {ai_confidence}.")

        if self.incident_exists(incident_id):
            raise DuplicateIncidentError(
                f"Incident '{incident_id}' is already recorded on-chain.",
                details={"incident_id": incident_id},
            )

        # Convert all IDs to bytes32 for the IncidentInput tuple
        incident_id_b32   = hex_to_bytes32(incident_id)
        source_device_b32 = device_id_to_bytes32(source_device)
        target_device_b32 = device_id_to_bytes32(target_device)
        evidence_hash_b32 = hex_to_bytes32(evidence_hash)

        # Build the IncidentInput tuple in the exact Solidity struct field order:
        # (incidentId, attackType, sourceDevice, targetDevice,
        #  riskScore, aiConfidence, actionTaken, evidenceHash)
        incident_input = (
            incident_id_b32,
            attack_type,
            source_device_b32,
            target_device_b32,
            int(risk_score),
            int(ai_confidence),
            action_taken,
            evidence_hash_b32,
        )

        logger.info(
            "Recording incident: id=%s attack=%s risk=%d confidence=%d",
            incident_id,
            attack_type,
            risk_score,
            ai_confidence,
        )

        return self._svc.send_transaction("recordIncident", incident_input)

    def update_incident_status(
        self,
        incident_id: str,
        status: int,
    ) -> TransactionResult:
        """
        Update the workflow status of an existing incident.

        Args:
            incident_id: 0x-prefixed hex string.
            status:      0=OPEN, 1=INVESTIGATING, 2=RESOLVED, 3=CLOSED.
                         Import utils.INCIDENT_* constants for clarity.

        Raises:
            IncidentNotFoundError: If the incident does not exist.
            ValueError:            If status is out of range (0–3).
        """
        if not 0 <= status <= 3:
            raise ValueError(f"status must be 0–3, got {status}.")

        if not self.incident_exists(incident_id):
            raise IncidentNotFoundError(
                f"Incident '{incident_id}' not found on-chain.",
                details={"incident_id": incident_id},
            )

        incident_id_b32 = hex_to_bytes32(incident_id)
        logger.info("Updating incident status: id=%s status=%d", incident_id, status)
        return self._svc.send_transaction(
            "updateIncidentStatus",
            incident_id_b32,
            int(status),
        )

    # ──────────────────────────────────────────────────────────────
    #  Read operations (free, no gas)
    # ──────────────────────────────────────────────────────────────

    def get_incident(self, incident_id: str) -> IncidentRecord:
        """
        Retrieve the full IncidentRecord by its ID.

        Raises:
            IncidentNotFoundError: If the incident is not on-chain.
        """
        incident_id_b32 = hex_to_bytes32(incident_id)
        raw = self._svc.call_function("getIncident", incident_id_b32)

        try:
            exists_flag = bool(raw[10])
        except (IndexError, TypeError) as exc:
            raise ContractError(
                f"Unexpected return shape from getIncident('{incident_id}'): {raw}",
                details={"raw": str(raw)},
            ) from exc

        if not exists_flag:
            raise IncidentNotFoundError(
                f"Incident '{incident_id}' not found on-chain.",
                details={"incident_id": incident_id},
            )

        return IncidentRecord.from_tuple(raw)

    def incident_exists(self, incident_id: str) -> bool:
        """Return True if the incident ID is already recorded on-chain."""
        try:
            incident_id_b32 = hex_to_bytes32(incident_id)
            return bool(self._svc.call_function("incidentExists", incident_id_b32))
        except Exception as exc:
            logger.warning("incidentExists check failed for '%s': %s", incident_id, exc)
            return False

    def verify_evidence(self, incident_id: str, evidence_hash: str) -> bool:
        """
        Verify that the supplied evidence hash matches the sealed on-chain hash.
        Raises EvidenceTamperingError if the hashes differ — this indicates the
        original evidence file has been tampered with.

        Args:
            incident_id:   0x-prefixed hex string.
            evidence_hash: SHA-256 / SHA-3 hash of the evidence file to verify.

        Returns:
            True if the hash matches exactly.

        Raises:
            IncidentNotFoundError:  If the incident does not exist.
            EvidenceTamperingError: If the hash does not match the on-chain record.
        """
        record = self.get_incident(incident_id)
        candidate_hex = bytes32_to_hex(hex_to_bytes32(evidence_hash))

        if record.evidence_hash.lower() != candidate_hex.lower():
            raise EvidenceTamperingError(
                f"Evidence hash mismatch for incident '{incident_id}'. "
                "The supplied hash does not match the on-chain sealed hash — "
                "the evidence file may have been tampered with.",
                details={
                    "incident_id": incident_id,
                    "provided_hash": candidate_hex,
                    "on_chain_hash": record.evidence_hash,
                },
            )

        logger.info("Evidence verified OK: incident=%s", incident_id)
        return True

    def latest_incident(self) -> IncidentRecord | None:
        """
        Return the most recently recorded incident, or None if none exist yet.
        """
        if self.total_incidents() == 0:
            return None

        raw = self._svc.call_function("latestIncident")
        try:
            exists_flag = bool(raw[10])
        except (IndexError, TypeError):
            return None

        if not exists_flag:
            return None

        return IncidentRecord.from_tuple(raw)

    def total_incidents(self) -> int:
        """Return the total number of recorded incidents."""
        return int(self._svc.call_function("totalIncidents"))
