"""
app/ai/sentinelx/response_agent.py — ResponseAgent: converts
AttackClassification results into structured, NON-EXECUTED response
recommendations.

    ClassificationReport (from AttackClassifier)
        -> ResponseAgent.recommend()
        -> ResponseReport (one ResponseRecommendation per classification)

This module maps each AttackCategory to a standardized recommended action:

    Normal                    -> Monitor
    Replay Attack              -> Rotate Key
    Brute Force                -> Block Device
    Spoofing                   -> Blacklist Device
    DoS                        -> Rate Limit
    Invalid Rolling Key         -> Force Re-authentication
    Abnormal Device Behavior    -> Alert + Monitor
    Unknown                     -> Manual Investigation

and attaches a priority (escalated, never lowered, by the underlying
InvestigationFinding severity), a human-readable reasoning trail, and an
immediate_action_required flag.

THIS MODULE NEVER EXECUTES ANYTHING. It does not rotate keys, does not
call app.services.rolling_key_service, does not block/blacklist a device,
does not call app.blockchain.* or app.services.blockchain_service, and
does not touch app.interfaces.ai_interface / app.services.ai_service. It
only returns a recommendation object for a separate, not-yet-implemented
component (or a human operator) to act on.

No ML/CUDA dependency is imported here — this module only reshapes the
dataclasses already produced by app.ai.sentinelx.classifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.ai.exceptions import AIBaseError

from .classifier import AttackCategory, AttackClassification, ClassificationReport

_DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.6


class ResponseAction(str, Enum):
    """Standardized, recommended-only response actions."""

    MONITOR = "Monitor"
    ROTATE_KEY = "Rotate Key"
    BLOCK_DEVICE = "Block Device"
    BLACKLIST_DEVICE = "Blacklist Device"
    RATE_LIMIT = "Rate Limit"
    FORCE_REAUTHENTICATION = "Force Re-authentication"
    ALERT_AND_MONITOR = "Alert + Monitor"
    MANUAL_INVESTIGATION = "Manual Investigation"


class ResponsePriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ResponseError(AIBaseError):
    """Raised when ResponseAgent receives malformed or inconsistent input."""


# Fixed 1:1 mapping, exactly as specified.
_CATEGORY_TO_ACTION: dict[AttackCategory, ResponseAction] = {
    AttackCategory.NORMAL: ResponseAction.MONITOR,
    AttackCategory.REPLAY_ATTACK: ResponseAction.ROTATE_KEY,
    AttackCategory.BRUTE_FORCE: ResponseAction.BLOCK_DEVICE,
    AttackCategory.SPOOFING: ResponseAction.BLACKLIST_DEVICE,
    AttackCategory.DOS: ResponseAction.RATE_LIMIT,
    AttackCategory.INVALID_ROLLING_KEY: ResponseAction.FORCE_REAUTHENTICATION,
    AttackCategory.ABNORMAL_DEVICE_BEHAVIOR: ResponseAction.ALERT_AND_MONITOR,
    AttackCategory.UNKNOWN: ResponseAction.MANUAL_INVESTIGATION,
}

# Baseline urgency per category, before any severity-driven escalation.
_BASE_PRIORITY: dict[AttackCategory, ResponsePriority] = {
    AttackCategory.NORMAL: ResponsePriority.LOW,
    AttackCategory.REPLAY_ATTACK: ResponsePriority.HIGH,
    AttackCategory.BRUTE_FORCE: ResponsePriority.HIGH,
    AttackCategory.SPOOFING: ResponsePriority.CRITICAL,
    AttackCategory.DOS: ResponsePriority.CRITICAL,
    AttackCategory.INVALID_ROLLING_KEY: ResponsePriority.MEDIUM,
    AttackCategory.ABNORMAL_DEVICE_BEHAVIOR: ResponsePriority.MEDIUM,
    AttackCategory.UNKNOWN: ResponsePriority.HIGH,
}

_PRIORITY_ORDER: list[ResponsePriority] = [
    ResponsePriority.LOW,
    ResponsePriority.MEDIUM,
    ResponsePriority.HIGH,
    ResponsePriority.CRITICAL,
]

# InvestigationFinding.severity ("NONE"/"LOW"/"MEDIUM"/"HIGH"/"CRITICAL")
# acts as a *floor* on priority — it can only raise, never lower, the
# category's baseline urgency.
_SEVERITY_TO_PRIORITY_FLOOR: dict[str, ResponsePriority] = {
    "NONE": ResponsePriority.LOW,
    "LOW": ResponsePriority.LOW,
    "MEDIUM": ResponsePriority.MEDIUM,
    "HIGH": ResponsePriority.HIGH,
    "CRITICAL": ResponsePriority.CRITICAL,
}


def _escalate_priority(base: ResponsePriority, severity: str) -> tuple[ResponsePriority, bool]:
    """Return (final_priority, was_escalated) — severity can only raise `base`."""
    floor = _SEVERITY_TO_PRIORITY_FLOOR.get(severity, ResponsePriority.LOW)
    if _PRIORITY_ORDER.index(floor) > _PRIORITY_ORDER.index(base):
        return floor, True
    return base, False


@dataclass
class ResponseRecommendation:
    """One structured, per-event response recommendation. Nothing here is executed."""

    investigation_id: str  # correlates back through InvestigationFinding -> AttackClassification
    event_id: str
    category: AttackCategory
    recommended_actions: list[ResponseAction]
    priority: ResponsePriority
    immediate_action_required: bool
    reasoning: list[str]
    classification_confidence: float  # passthrough from AttackClassification.confidence
    generated_at: str  # ISO-8601 UTC


@dataclass
class ResponseReport:
    """A full response-recommendation batch: one ResponseRecommendation per classification, plus a rollup."""

    recommendations: list[ResponseRecommendation]
    total_events: int
    action_counts: dict[str, int]
    priority_counts: dict[str, int]
    immediate_action_count: int
    source_classification: ClassificationReport


class ResponseAgent:
    """
    Converts AttackClassification results into structured response
    recommendations. Never executes, calls, or triggers anything — the
    output is a recommendation for a separate component or a human
    operator to act on.

    Usage:
        agent = ResponseAgent()
        report = agent.recommend(classification_report)
        rec = agent.recommend_single(classification)
    """

    def __init__(self, low_confidence_threshold: float = _DEFAULT_LOW_CONFIDENCE_THRESHOLD) -> None:
        self._low_confidence_threshold = low_confidence_threshold

    def recommend(self, report: ClassificationReport) -> ResponseReport:
        """Build a full ResponseReport from a ClassificationReport."""
        if not isinstance(report, ClassificationReport):
            raise ResponseError(
                f"ResponseAgent.recommend() expects a ClassificationReport, got {type(report).__name__}."
            )

        recommendations = [self._recommend_for(c) for c in report.classifications]

        action_counts: dict[str, int] = {}
        priority_counts: dict[str, int] = {}
        immediate_action_count = 0

        for rec in recommendations:
            for action in rec.recommended_actions:
                action_counts[action.value] = action_counts.get(action.value, 0) + 1
            priority_counts[rec.priority.value] = priority_counts.get(rec.priority.value, 0) + 1
            if rec.immediate_action_required:
                immediate_action_count += 1

        return ResponseReport(
            recommendations=recommendations,
            total_events=report.total_events,
            action_counts=action_counts,
            priority_counts=priority_counts,
            immediate_action_count=immediate_action_count,
            source_classification=report,
        )

    def recommend_single(self, classification: AttackClassification) -> ResponseRecommendation:
        """Convenience for recommending a response to a single AttackClassification directly."""
        if not isinstance(classification, AttackClassification):
            raise ResponseError(
                f"ResponseAgent.recommend_single() expects an AttackClassification, "
                f"got {type(classification).__name__}."
            )
        return self._recommend_for(classification)

    # ── internals ────────────────────────────────────────────────────

    def _recommend_for(self, classification: AttackClassification) -> ResponseRecommendation:
        action = _CATEGORY_TO_ACTION[classification.category]
        base_priority = _BASE_PRIORITY[classification.category]
        final_priority, escalated = _escalate_priority(base_priority, classification.severity)

        reasoning = [
            f"AttackCategory '{classification.category.value}' maps to the standard "
            f"response action '{action.value}'.",
        ]
        if escalated:
            reasoning.append(
                f"Priority escalated from {base_priority.value} to {final_priority.value} "
                f"based on the underlying investigation severity '{classification.severity}'."
            )
        if classification.category == AttackCategory.UNKNOWN and classification.verdict == "ATTACK":
            reasoning.append(
                "Verdict is ATTACK but the specific attack category could not be "
                "determined; a human analyst should review before any action is taken."
            )
        if (
            classification.category != AttackCategory.NORMAL
            and classification.confidence < self._low_confidence_threshold
        ):
            reasoning.append(
                f"Classification confidence is low ({classification.confidence:.0%}); "
                "recommend manual confirmation before acting on this recommendation."
            )

        immediate_action_required = (
            classification.category != AttackCategory.NORMAL
            and final_priority in (ResponsePriority.HIGH, ResponsePriority.CRITICAL)
        )

        return ResponseRecommendation(
            investigation_id=classification.investigation_id,
            event_id=classification.event_id,
            category=classification.category,
            recommended_actions=[action],
            priority=final_priority,
            immediate_action_required=immediate_action_required,
            reasoning=reasoning,
            classification_confidence=classification.confidence,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
