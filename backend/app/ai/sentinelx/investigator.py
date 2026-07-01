"""
app/ai/sentinelx/investigator.py — InvestigationAgent: converts a raw
InferenceResult into a structured, analyst-facing investigation record.

    InferenceResult (+ optional source AttackEventRecords)
        -> InvestigationAgent.investigate()
        -> InvestigationReport (one InvestigationFinding per event)

This is a pure triage/classification step: it labels each event with a
verdict (ATTACK/NORMAL) and a severity tier derived from the model's
confidence, and carries through model/execution metadata for traceability.

It deliberately does NOT decide or perform any response action — no
rolling-key rotation, no blockchain logging, no blacklisting, no
automated remediation. Severity is a triage/prioritization signal for a
future response component to consume, not an instruction to act on. That
response logic belongs to a separate, not-yet-implemented piece of
SentinelXEngine (see app/ai/sentinelx/engine.py's module docstring).

No ML dependency is imported here — this module only reshapes the
dataclasses already produced by app.ai.inference.InferenceEngine.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.ai.datasets.schema import AttackEventRecord
from app.ai.exceptions import AIBaseError
from app.ai.inference.engine import ExecutionInfo, InferenceResult

_SEVERITY_ORDER: list[str] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

DEFAULT_SEVERITY_THRESHOLDS: dict[str, float] = {
    "CRITICAL": 0.90,
    "HIGH": 0.75,
    "MEDIUM": 0.50,
    "LOW": 0.0,
}


class InvestigationError(AIBaseError):
    """Raised when InvestigationAgent receives malformed or inconsistent input."""


def _classify_severity(confidence: float, is_attack: bool, thresholds: dict[str, float]) -> str:
    """Map a confidence score to a severity tier. NORMAL verdicts are always 'NONE'."""
    if not is_attack:
        return "NONE"
    for tier in _SEVERITY_ORDER:
        if confidence >= thresholds[tier]:
            return tier
    return "LOW"


def _build_summary(verdict: str, severity: str, device_id: str | None, model_name: str) -> str:
    subject = f"device '{device_id}'" if device_id else "an unidentified device"
    if verdict == "NORMAL":
        return f"No anomaly detected for {subject} ({model_name})."
    return f"{severity}-severity anomaly detected for {subject} ({model_name}); flagged for review."


@dataclass
class InvestigationFinding:
    """One structured, per-event investigative finding."""

    investigation_id: str
    event_id: str
    device_id: str | None
    event_timestamp: str | None  # ISO-8601 UTC, from the source AttackEventRecord if provided
    verdict: str  # "ATTACK" | "NORMAL"
    severity: str  # "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    confidence: float
    reported_event_type: str | None  # ground-truth/self-reported category, descriptive only
    matches_ground_truth: bool | None
    model_name: str
    model_metadata: dict[str, Any]
    generated_at: str  # ISO-8601 UTC, when this finding was produced
    summary: str


@dataclass
class InvestigationReport:
    """A full investigation batch: one InvestigationFinding per input event, plus a rollup."""

    findings: list[InvestigationFinding]
    total_events: int
    attack_count: int
    normal_count: int
    severity_counts: dict[str, int]
    source_execution: ExecutionInfo


class InvestigationAgent:
    """
    Converts an InferenceResult into a structured InvestigationReport.

    Pure transformation/triage — classifies verdicts and severity tiers so
    findings can be prioritized for review, but takes no action itself.

    Usage:
        agent = InvestigationAgent()
        report = agent.investigate(inference_result)                 # verdict/severity only
        report = agent.investigate(inference_result, records)        # + device_id/timestamp context
        finding = agent.investigate_single(inference_result, record)  # single-event convenience
    """

    def __init__(self, severity_thresholds: dict[str, float] | None = None) -> None:
        self._thresholds = severity_thresholds or DEFAULT_SEVERITY_THRESHOLDS

    def investigate(
        self,
        result: InferenceResult,
        records: list[AttackEventRecord] | None = None,
    ) -> InvestigationReport:
        """
        Build a full InvestigationReport from an InferenceResult.

        Args:
            result: The InferenceResult produced by InferenceEngine.predict*().
            records: Optional source AttackEventRecords, in the same order
                as result.event_ids. When provided, each finding is enriched
                with device_id/event_timestamp; when omitted, those fields
                are None and findings are built from `result` alone.
        """
        if not isinstance(result, InferenceResult):
            raise InvestigationError(
                f"InvestigationAgent.investigate() expects an InferenceResult, got {type(result).__name__}."
            )
        if records is not None and len(records) != result.n_samples:
            raise InvestigationError(
                f"records length ({len(records)}) does not match "
                f"InferenceResult.n_samples ({result.n_samples})."
            )

        ground_truth = result.preprocessing_metadata.get("ground_truth_labels") or []
        has_ground_truth = len(ground_truth) == result.n_samples

        findings: list[InvestigationFinding] = []
        severity_counts: dict[str, int] = {}
        attack_count = 0

        for i in range(result.n_samples):
            is_attack = result.prediction[i] == 1
            confidence = result.confidence[i]
            verdict = "ATTACK" if is_attack else "NORMAL"
            severity = _classify_severity(confidence, is_attack, self._thresholds)

            record = records[i] if records is not None else None
            reported_event_type = ground_truth[i] if has_ground_truth else None
            matches_ground_truth = (
                is_attack == (reported_event_type != "NORMAL") if reported_event_type is not None else None
            )

            findings.append(
                InvestigationFinding(
                    investigation_id=str(uuid.uuid4()),
                    event_id=result.event_ids[i],
                    device_id=record.device_id if record is not None else None,
                    event_timestamp=record.timestamp.isoformat() if record is not None else None,
                    verdict=verdict,
                    severity=severity,
                    confidence=confidence,
                    reported_event_type=reported_event_type,
                    matches_ground_truth=matches_ground_truth,
                    model_name=result.execution.model_name,
                    model_metadata=dict(result.model_metadata),
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    summary=_build_summary(
                        verdict,
                        severity,
                        record.device_id if record is not None else None,
                        result.execution.model_name,
                    ),
                )
            )
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            if is_attack:
                attack_count += 1

        return InvestigationReport(
            findings=findings,
            total_events=result.n_samples,
            attack_count=attack_count,
            normal_count=result.n_samples - attack_count,
            severity_counts=severity_counts,
            source_execution=result.execution,
        )

    def investigate_single(
        self,
        result: InferenceResult,
        record: AttackEventRecord | None = None,
    ) -> InvestigationFinding:
        """Convenience for a single-event InferenceResult (result.n_samples == 1)."""
        if result.n_samples != 1:
            raise InvestigationError(
                f"investigate_single() requires an InferenceResult with exactly 1 sample, "
                f"got {result.n_samples}."
            )
        report = self.investigate(result, [record] if record is not None else None)
        return report.findings[0]
