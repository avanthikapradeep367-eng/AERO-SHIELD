"""
AERO-SHIELD X — Tamper Detection & Integrity Checker

Provides high-level integrity verification functions that:
  1. Compute the current SHA-256 of a record / file / log / report.
  2. Retrieve the corresponding blockchain hash.
  3. Compare and return a structured forensic report.

All functions return a ForensicReport dict matching Part 6 of the spec.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.blockchain.services.evidence_service import EvidenceService
from app.core.logger import get_logger
from .hashing import hash_json
from .verifier import (
    verify_evidence,
    verify_file as _verify_file,
)

logger = get_logger("forensics.integrity_checker")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _build_report(
    evidence_id: str,
    verification_result: Any,      # VerificationResult dataclass
    report_type: str = "INTEGRITY_CHECK",
) -> dict[str, Any]:
    """Build a standardised ForensicReport dict from a VerificationResult."""
    status = verification_result.verification_status
    score = verification_result.integrity_score

    return {
        "report_type": report_type,
        "evidence_id": evidence_id,
        "blockchain_hash": verification_result.blockchain_hash,
        "current_hash": verification_result.current_hash,
        "verification_status": status,
        "hashes_match": verification_result.hashes_match,
        "timestamp": _now_iso(),
        "transaction_hash": verification_result.transaction_hash,
        "risk_level": verification_result.risk_level,
        "integrity_score": score,
        "verification_result": status,
        "message": verification_result.message,
        "elapsed_ms": verification_result.elapsed_ms,
        "details": verification_result.details,
    }


# ── Public integrity-check functions ───────────────────────────────────────────

def verify_database_record(
    incident_id: str,
    record_data: dict[str, Any],
    evidence_service: EvidenceService | None = None,
) -> dict[str, Any]:
    """
    Verify a database record against its blockchain hash.

    Serialises ``record_data`` to canonical JSON, computes its SHA-256,
    then compares with the sealed hash on-chain for ``incident_id``.

    Args:
        incident_id:  Incident / evidence ID on-chain.
        record_data:  Current state of the database record (Python dict).
        evidence_service: Optional pre-built EvidenceService.

    Returns:
        ForensicReport dict.
    """
    t0 = time.monotonic()
    logger.info("verify_database_record | incident_id=%s", incident_id)

    h = hash_json(record_data, label=incident_id)
    result = verify_evidence(incident_id, h["hash"], evidence_service)
    result.details["record_hash_info"] = {
        "canonical_representation": h.get("canonical_representation", ""),
        "size_bytes": h["size_bytes"],
    }
    return _build_report(incident_id, result, report_type="DATABASE_RECORD_CHECK")


def verify_log_file(
    incident_id: str,
    file_path: str,
    evidence_service: EvidenceService | None = None,
) -> dict[str, Any]:
    """
    Hash a log file on disk and verify against blockchain.

    Args:
        incident_id:  Incident the log is associated with.
        file_path:    Path to the log file.
        evidence_service: Optional pre-built EvidenceService.

    Returns:
        ForensicReport dict.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    logger.info("verify_log_file | incident_id=%s | file=%s", incident_id, file_path)
    result = _verify_file(incident_id, file_path, evidence_service)
    return _build_report(incident_id, result, report_type="LOG_FILE_CHECK")


def verify_incident(
    incident_id: str,
    current_evidence_hash: str,
    evidence_service: EvidenceService | None = None,
) -> dict[str, Any]:
    """
    Verify that a supplied evidence hash matches the sealed blockchain hash.

    This is the primary tamper-detection call for incident forensics:
        - VERIFIED  → evidence is intact
        - TAMPERED  → evidence has been modified after sealing
        - MISSING   → incident not found on-chain

    Args:
        incident_id:           On-chain incident identifier.
        current_evidence_hash: Current SHA-256 of the evidence (0x-prefixed hex).
        evidence_service:      Optional pre-built EvidenceService.

    Returns:
        ForensicReport dict.
    """
    logger.info("verify_incident | incident_id=%s", incident_id)
    result = verify_evidence(incident_id, current_evidence_hash, evidence_service)
    return _build_report(incident_id, result, report_type="INCIDENT_INTEGRITY_CHECK")


def verify_report(
    incident_id: str,
    report_data: dict[str, Any],
    evidence_service: EvidenceService | None = None,
) -> dict[str, Any]:
    """
    Verify a JSON forensic report against its blockchain-sealed hash.

    Use this to confirm that a previously generated and sealed report has
    not been modified since it was anchored on-chain.

    Args:
        incident_id:  Incident the report belongs to.
        report_data:  Current content of the report (Python dict).
        evidence_service: Optional pre-built EvidenceService.

    Returns:
        ForensicReport dict.
    """
    logger.info("verify_report | incident_id=%s", incident_id)
    h = hash_json(report_data, label=f"report:{incident_id}")
    result = verify_evidence(incident_id, h["hash"], evidence_service)
    result.details["report_hash_info"] = {"size_bytes": h["size_bytes"]}
    return _build_report(incident_id, result, report_type="REPORT_INTEGRITY_CHECK")
