"""
AERO-SHIELD X — Blockchain Evidence Verification Engine

Bridges the hashing layer with the existing blockchain services to perform
tamper-detection verification.

Verification workflow
---------------------
1. Compute SHA-256 of the current evidence payload (text / JSON / file / bytes)
2. Retrieve the sealed hash from the on-chain IncidentRecord
3. Compare hashes
4. Return a structured VerificationResult

Verification statuses
---------------------
    VERIFIED  — hashes match; evidence is intact
    TAMPERED  — hashes differ; evidence has been modified
    MISSING   — incident ID not found on-chain
    CORRUPTED — blockchain call succeeded but the record is internally inconsistent
    ERROR     — unexpected exception during verification
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.blockchain.services.evidence_service import EvidenceService
from app.blockchain.services.authentication_service import AuthenticationService
from app.blockchain.exceptions import (
    IncidentNotFoundError,
    EvidenceTamperingError,
    AuthRecordNotFoundError,
    BlockchainBaseError,
)
from app.core.logger import get_logger
from .hashing import hash_text, hash_json, hash_file, hash_bytes, compare_hash

logger = get_logger("forensics.verifier")

# ── Status constants ────────────────────────────────────────────────────────────
VERIFIED  = "VERIFIED"
TAMPERED  = "TAMPERED"
MISSING   = "MISSING"
CORRUPTED = "CORRUPTED"
ERROR     = "ERROR"


@dataclass
class VerificationResult:
    """Structured result returned by every verification call."""
    evidence_id: str
    verification_status: str        # VERIFIED | TAMPERED | MISSING | CORRUPTED | ERROR
    blockchain_hash: str | None
    current_hash: str | None
    hashes_match: bool
    message: str
    timestamp: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    transaction_hash: str | None = None
    blockchain_block: int | None = None
    risk_level: str = "LOW"         # LOW | MEDIUM | HIGH | CRITICAL
    integrity_score: int = 100      # 0–100
    details: dict[str, Any] = field(default_factory=dict)
    elapsed_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "verification_status": self.verification_status,
            "blockchain_hash": self.blockchain_hash,
            "current_hash": self.current_hash,
            "hashes_match": self.hashes_match,
            "message": self.message,
            "timestamp": self.timestamp,
            "transaction_hash": self.transaction_hash,
            "blockchain_block": self.blockchain_block,
            "risk_level": self.risk_level,
            "integrity_score": self.integrity_score,
            "details": self.details,
            "elapsed_ms": self.elapsed_ms,
        }


def _risk_for_status(status: str) -> tuple[str, int]:
    """Return (risk_level, integrity_score) for a given verification status."""
    return {
        VERIFIED:  ("LOW",      100),
        TAMPERED:  ("CRITICAL",   0),
        MISSING:   ("HIGH",      50),
        CORRUPTED: ("HIGH",      25),
        ERROR:     ("MEDIUM",    75),
    }.get(status, ("MEDIUM", 50))


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ── Core verification functions ─────────────────────────────────────────────────

def verify_evidence(
    incident_id: str,
    current_hash: str,
    evidence_service: EvidenceService | None = None,
) -> VerificationResult:
    """
    Verify that ``current_hash`` matches the hash sealed on-chain for ``incident_id``.

    Args:
        incident_id:      0x-prefixed hex string identifying the incident.
        current_hash:     SHA-256 hash of the current evidence payload (0x-prefixed hex).
        evidence_service: Optional pre-built EvidenceService (created if not supplied).

    Returns:
        VerificationResult with status VERIFIED, TAMPERED, MISSING, or ERROR.
    """
    t0 = time.monotonic()
    svc = evidence_service or EvidenceService()

    logger.info("verify_evidence | incident_id=%s", incident_id)

    try:
        record = svc.get_incident(incident_id)
        blockchain_hash = record.evidence_hash

        match = compare_hash(current_hash, blockchain_hash)
        status = VERIFIED if match else TAMPERED
        risk, score = _risk_for_status(status)

        if status == TAMPERED:
            logger.warning(
                "TAMPERED EVIDENCE | incident=%s | on_chain=%s | supplied=%s",
                incident_id, blockchain_hash, current_hash,
            )

        return VerificationResult(
            evidence_id=incident_id,
            verification_status=status,
            blockchain_hash=blockchain_hash,
            current_hash=current_hash,
            hashes_match=match,
            message=(
                "Evidence integrity verified — hashes match."
                if match
                else "EVIDENCE TAMPERED — current hash does not match blockchain record."
            ),
            blockchain_block=None,
            risk_level=risk,
            integrity_score=score,
            details=record.to_dict(),
            elapsed_ms=round((time.monotonic() - t0) * 1000, 2),
        )

    except IncidentNotFoundError:
        risk, score = _risk_for_status(MISSING)
        return VerificationResult(
            evidence_id=incident_id,
            verification_status=MISSING,
            blockchain_hash=None,
            current_hash=current_hash,
            hashes_match=False,
            message=f"Incident '{incident_id}' not found on-chain. Cannot verify.",
            risk_level=risk,
            integrity_score=score,
            elapsed_ms=round((time.monotonic() - t0) * 1000, 2),
        )
    except BlockchainBaseError as exc:
        logger.error("verify_evidence blockchain error | %s: %s", type(exc).__name__, exc)
        risk, score = _risk_for_status(ERROR)
        return VerificationResult(
            evidence_id=incident_id,
            verification_status=ERROR,
            blockchain_hash=None,
            current_hash=current_hash,
            hashes_match=False,
            message=f"Blockchain error during verification: {exc.message}",
            risk_level=risk,
            integrity_score=score,
            details={"error": type(exc).__name__, "blockchain_message": exc.message},
            elapsed_ms=round((time.monotonic() - t0) * 1000, 2),
        )


def verify_incident_text(
    incident_id: str,
    text: str,
    evidence_service: EvidenceService | None = None,
) -> VerificationResult:
    """
    Hash ``text`` on-the-fly and verify against blockchain.
    Use when the original evidence was plain text (log lines, descriptions).
    """
    h = hash_text(text)
    return verify_evidence(incident_id, h["hash"], evidence_service)


def verify_incident_json(
    incident_id: str,
    data: dict,
    evidence_service: EvidenceService | None = None,
) -> VerificationResult:
    """
    Hash a JSON dict canonically and verify against blockchain.
    Use when the original evidence was a structured JSON document.
    """
    h = hash_json(data)
    return verify_evidence(incident_id, h["hash"], evidence_service)


def verify_file(
    incident_id: str,
    file_path: str,
    evidence_service: EvidenceService | None = None,
) -> VerificationResult:
    """
    Hash a file on disk and verify against blockchain.
    Supports any file type: logs, images, PDFs, binary evidence packages.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    h = hash_file(file_path)
    result = verify_evidence(incident_id, h["hash"], evidence_service)
    result.details["file_name"] = h.get("file_name")
    result.details["file_path"] = h.get("file_path")
    result.details["file_size_bytes"] = h.get("size_bytes")
    return result


def verify_bytes(
    incident_id: str,
    data: bytes,
    evidence_service: EvidenceService | None = None,
) -> VerificationResult:
    """Hash raw binary data and verify against blockchain."""
    h = hash_bytes(data)
    return verify_evidence(incident_id, h["hash"], evidence_service)


def verify_authentication_exists(
    auth_id: str,
    auth_service: AuthenticationService | None = None,
) -> VerificationResult:
    """
    Verify that an authentication record exists on-chain (presence check).
    Authentication records store no mutable hash — we confirm the record was
    sealed and has not been removed.
    """
    t0 = time.monotonic()
    svc = auth_service or AuthenticationService()
    logger.info("verify_authentication_exists | auth_id=%s", auth_id)

    try:
        record = svc.get_authentication(auth_id)
        risk, score = _risk_for_status(VERIFIED)
        return VerificationResult(
            evidence_id=auth_id,
            verification_status=VERIFIED,
            blockchain_hash=None,
            current_hash=None,
            hashes_match=True,
            message="Authentication record exists and is sealed on-chain.",
            risk_level=risk,
            integrity_score=score,
            details=record.to_dict() if hasattr(record, "to_dict") else {},
            elapsed_ms=round((time.monotonic() - t0) * 1000, 2),
        )
    except AuthRecordNotFoundError:
        risk, score = _risk_for_status(MISSING)
        return VerificationResult(
            evidence_id=auth_id,
            verification_status=MISSING,
            blockchain_hash=None,
            current_hash=None,
            hashes_match=False,
            message=f"Authentication record '{auth_id}' not found on-chain.",
            risk_level=risk,
            integrity_score=score,
            elapsed_ms=round((time.monotonic() - t0) * 1000, 2),
        )
    except BlockchainBaseError as exc:
        risk, score = _risk_for_status(ERROR)
        return VerificationResult(
            evidence_id=auth_id,
            verification_status=ERROR,
            blockchain_hash=None,
            current_hash=None,
            hashes_match=False,
            message=f"Blockchain error: {exc.message}",
            risk_level=risk,
            integrity_score=score,
            elapsed_ms=round((time.monotonic() - t0) * 1000, 2),
        )
