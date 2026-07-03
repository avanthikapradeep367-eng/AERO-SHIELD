"""
AERO-SHIELD X — Evidence Utilities & Forensic Report Generator

Generates structured forensic reports suitable for legal proceedings,
incident response handoffs, and audit trails.

Report structure
----------------
Every report contains:
    evidence_id        — the incident / evidence identifier
    blockchain_hash    — hash sealed on-chain
    current_hash       — hash of the current evidence state
    verification_status — VERIFIED | TAMPERED | MISSING | CORRUPTED | ERROR
    timestamp          — report generation time (ISO-8601)
    transaction_hash   — blockchain tx that anchored the evidence
    risk_level         — LOW | MEDIUM | HIGH | CRITICAL
    integrity_score    — 0–100 numeric integrity indicator
    verification_result — human-readable conclusion
    chain_of_custody   — full audit trail (if available)
    incident_record    — on-chain incident metadata (if available)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.blockchain.services.evidence_service import EvidenceService
from app.blockchain.exceptions import IncidentNotFoundError, BlockchainBaseError
from app.core.logger import get_logger
from .verifier import verify_evidence, MISSING
from . import chain_of_custody as custody

logger = get_logger("forensics.evidence_utils")


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _integrity_grade(score: int) -> str:
    """Convert a numeric score to a letter grade for executive summaries."""
    if score >= 95:
        return "A"
    if score >= 80:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def generate_forensic_report(
    incident_id: str,
    current_hash: str | None = None,
    include_chain_of_custody: bool = True,
    include_incident_record: bool = True,
    analyst: str = "SYSTEM",
    evidence_service: EvidenceService | None = None,
) -> dict[str, Any]:
    """
    Generate a complete, structured forensic report for an evidence item.

    Workflow:
        1. Retrieve the on-chain IncidentRecord.
        2. If ``current_hash`` is supplied, verify it against the blockchain hash.
        3. Optionally attach the chain-of-custody audit trail.
        4. Return the full report.

    Args:
        incident_id:              On-chain incident identifier.
        current_hash:             Current SHA-256 of the evidence (0x-prefixed hex).
                                  If None, reports the on-chain state without comparison.
        include_chain_of_custody: Attach the chain-of-custody history.
        include_incident_record:  Attach the full on-chain IncidentRecord.
        analyst:                  Name / ID of the analyst generating the report.
        evidence_service:         Optional pre-built EvidenceService.

    Returns:
        Structured forensic report dict.
    """
    report_id = str(uuid.uuid4())
    svc = evidence_service or EvidenceService()
    logger.info(
        "generate_forensic_report | incident_id=%s | analyst=%s | report_id=%s",
        incident_id, analyst, report_id,
    )

    # ── Fetch on-chain record ────────────────────────────────────────────────────
    incident_record: dict[str, Any] | None = None
    blockchain_hash: str | None = None
    on_chain_error: str | None = None

    try:
        record = svc.get_incident(incident_id)
        blockchain_hash = record.evidence_hash
        if include_incident_record:
            incident_record = record.to_dict()
    except IncidentNotFoundError:
        on_chain_error = f"Incident '{incident_id}' not found on-chain."
    except BlockchainBaseError as exc:
        on_chain_error = f"Blockchain error: {exc.message}"

    # ── Verify against current hash ──────────────────────────────────────────────
    verification_status = MISSING
    hashes_match = False
    risk_level = "HIGH"
    integrity_score = 50
    verification_message = on_chain_error or "No current hash provided — reporting on-chain state only."
    tx_hash: str | None = None

    if current_hash and blockchain_hash:
        result = verify_evidence(incident_id, current_hash, svc)
        verification_status = result.verification_status
        hashes_match = result.hashes_match
        risk_level = result.risk_level
        integrity_score = result.integrity_score
        verification_message = result.message
    elif blockchain_hash and not current_hash:
        verification_status = "ON_CHAIN_ONLY"
        hashes_match = False
        risk_level = "LOW"
        integrity_score = 90
        verification_message = "Evidence hash sealed on-chain. No current hash supplied for comparison."
    elif on_chain_error:
        verification_status = MISSING
        risk_level = "HIGH"
        integrity_score = 0
        verification_message = on_chain_error

    # ── Chain of custody ─────────────────────────────────────────────────────────
    custody_history: list[dict] = []
    custody_record: dict | None = None
    if include_chain_of_custody:
        try:
            custody_record = custody.get_record(incident_id).to_dict()
            custody_history = custody.get_history(incident_id)
        except KeyError:
            pass  # No custody record exists yet — that's fine

    # ── Build report ─────────────────────────────────────────────────────────────
    report: dict[str, Any] = {
        # Identity
        "report_id": report_id,
        "evidence_id": incident_id,
        "report_type": "FULL_FORENSIC_REPORT",
        "analyst": analyst,
        # Hashes
        "blockchain_hash": blockchain_hash,
        "current_hash": current_hash,
        # Verification
        "verification_status": verification_status,
        "hashes_match": hashes_match,
        "transaction_hash": tx_hash,
        # Risk
        "risk_level": risk_level,
        "integrity_score": integrity_score,
        "integrity_grade": _integrity_grade(integrity_score),
        # Verdict
        "verification_result": verification_message,
        # Timestamps
        "timestamp": _now_iso(),
        "generated_at": _now_iso(),
    }

    if incident_record:
        report["incident_record"] = incident_record

    if include_chain_of_custody:
        report["chain_of_custody"] = custody_record
        report["custody_history"] = custody_history
        report["custody_event_count"] = len(custody_history)

    logger.info(
        "generate_forensic_report | report_id=%s | status=%s | score=%d",
        report_id, verification_status, integrity_score,
    )
    return report


def quick_hash_report(
    input_type: str,
    hash_result: dict[str, Any],
    label: str | None = None,
) -> dict[str, Any]:
    """
    Wrap a raw hashing result (from hashing.py) into a forensic report envelope.

    Args:
        input_type:  "text" | "json" | "file" | "bytes"
        hash_result: Dict returned by hash_text / hash_json / hash_file / hash_bytes.
        label:       Optional human-readable label.

    Returns:
        Lightweight report dict.
    """
    return {
        "report_id": str(uuid.uuid4()),
        "report_type": "HASH_REPORT",
        "input_type": input_type,
        "label": label,
        "hash": hash_result.get("hash"),
        "algorithm": hash_result.get("algorithm", "SHA-256"),
        "size_bytes": hash_result.get("size_bytes"),
        "file_name": hash_result.get("file_name"),
        "canonical_representation": hash_result.get("canonical_representation"),
        "timestamp": hash_result.get("timestamp", _now_iso()),
        "generated_at": _now_iso(),
    }
