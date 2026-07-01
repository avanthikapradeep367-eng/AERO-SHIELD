"""
app/ai/sentinelx/classifier.py — AttackClassifier: converts an
InvestigationReport into standardized attack-category classifications.

    InvestigationReport (+ optional source AttackEventRecords)
        -> AttackClassifier.classify()
        -> ClassificationReport (one AttackClassification per finding)

Why this exists as a separate stage from InvestigationAgent: the current
model (IsolationForestModel) is an unsupervised anomaly detector — it only
predicts ATTACK/NORMAL, not WHICH attack pattern occurred. This module
applies domain-derived heuristic rules — mirroring the same signal
characteristics the synthetic dataset generator uses to construct each
category (app/ai/datasets/generator.py) — to assign one of the defined
AttackCategory values, with a confidence score and human-readable
reasoning for each decision.

When no source AttackEventRecord is available for a finding, or when no
rule matches confidently enough, the result is AttackCategory.UNKNOWN —
this classifier never guesses. The ground-truth `reported_event_type`
carried on an InvestigationFinding (only ever populated for synthetic/
evaluation data) is used ONLY as a diagnostic comparison field
(`matched_ground_truth_category`); it never influences the classification
itself, so this module stays meaningful for real, unlabeled live traffic.

Heuristic rule-based classification is itself expected to have some
ambiguity/overlap between categories — that is why every result carries a
confidence score and reasoning, and why AttackCategory.UNKNOWN exists as a
legitimate outcome rather than forcing a guess. A future supervised
multi-class model can replace the rule engine here without changing this
module's public shape.

Purely a classification/labeling step — no response or mitigation logic
(no key rotation, no blockchain logging, no blacklisting) is implemented
here, nor is any ML/CUDA dependency imported.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from app.ai.datasets.schema import AttackEventRecord, EventType
from app.ai.exceptions import AIBaseError

from .investigator import InvestigationFinding, InvestigationReport

_MIN_CATEGORY_MATCH_RATIO = 0.5


class AttackCategory(str, Enum):
    """Standardized attack classification categories."""

    NORMAL = "Normal"
    REPLAY_ATTACK = "Replay Attack"
    BRUTE_FORCE = "Brute Force"
    SPOOFING = "Spoofing"
    DOS = "DoS"
    INVALID_ROLLING_KEY = "Invalid Rolling Key"
    ABNORMAL_DEVICE_BEHAVIOR = "Abnormal Device Behavior"
    UNKNOWN = "Unknown"


class ClassificationError(AIBaseError):
    """Raised when AttackClassifier receives malformed or inconsistent input."""


# Maps the dataset schema's ground-truth EventType values to AttackCategory,
# used only for the diagnostic matched_ground_truth_category field below —
# never to decide a classification.
_EVENT_TYPE_TO_CATEGORY: dict[str, AttackCategory] = {
    EventType.NORMAL.value: AttackCategory.NORMAL,
    EventType.REPLAY.value: AttackCategory.REPLAY_ATTACK,
    EventType.BRUTE_FORCE.value: AttackCategory.BRUTE_FORCE,
    EventType.SPOOFING.value: AttackCategory.SPOOFING,
    EventType.DOS.value: AttackCategory.DOS,
    EventType.INVALID_ROLLING_KEY.value: AttackCategory.INVALID_ROLLING_KEY,
    EventType.ABNORMAL_DEVICE_BEHAVIOR.value: AttackCategory.ABNORMAL_DEVICE_BEHAVIOR,
}


_Signal = tuple[str, Callable[[AttackEventRecord], bool]]


@dataclass(frozen=True)
class _CategoryRule:
    """
    One AttackCategory's domain signature, split into:

    required: ALL must hold for the category to be eligible at all. These
        are the necessary-but-possibly-not-sufficient gating conditions
        (e.g. "rolling key failed validation") — failing even one means
        this category cannot explain the record, so its score is 0.0.
    supporting: Once `required` is fully satisfied, these add confidence
        without gating eligibility. A category with no supporting signals
        scores a clean 1.0 whenever `required` passes.

    This separation exists because a flat "fraction of N signals matched"
    score lets a category with mostly generic signals (e.g. "valid key" +
    "auth succeeded", which are also true of ordinary NORMAL traffic) win
    on partial credit even when its one truly distinguishing signal never
    matched. Gating on the distinguishing signal(s) avoids that.
    """

    category: AttackCategory
    required: list[_Signal]
    supporting: list[_Signal] = field(default_factory=list)


def _is_telemetry_outlier(r: AttackEventRecord) -> bool:
    return (
        r.payload_size_bytes <= 16
        or r.payload_size_bytes >= 4000
        or r.session_duration_ms <= 50
        or r.session_duration_ms >= 30000
    )


# Ordered most-distinctive-first for tie-break purposes (see _score_record):
# on an exact score tie, the earlier rule in this list wins. In practice
# ties should not occur given the required-signal gating above, but the
# ordering is kept as a defensive, documented tie-break rather than
# leaving it to dict/list iteration order implicitly.
_ATTACK_RULES: list[_CategoryRule] = [
    _CategoryRule(
        category=AttackCategory.DOS,
        required=[
            ("extreme request rate (>= 100 req/s)", lambda r: r.request_rate_hz >= 100.0),
            ("high packet loss (>= 30%)", lambda r: r.packet_loss_ratio >= 0.30),
        ],
    ),
    _CategoryRule(
        category=AttackCategory.BRUTE_FORCE,
        required=[
            ("rolling key failed validation", lambda r: not r.rolling_key_valid),
            ("authentication failed", lambda r: not r.auth_success),
            ("elevated request rate (>= 10 req/s)", lambda r: r.request_rate_hz >= 10.0),
        ],
    ),
    _CategoryRule(
        category=AttackCategory.REPLAY_ATTACK,
        required=[
            ("rolling key failed validation", lambda r: not r.rolling_key_valid),
            ("authentication failed", lambda r: not r.auth_success),
            ("request rate consistent with a resent packet, not a flood (< 5 req/s)", lambda r: r.request_rate_hz < 5.0),
            ("rolling key version looks stale/reused (<= 10)", lambda r: r.rolling_key_version <= 10),
        ],
    ),
    _CategoryRule(
        category=AttackCategory.INVALID_ROLLING_KEY,
        required=[
            ("rolling key failed validation", lambda r: not r.rolling_key_valid),
            ("authentication failed", lambda r: not r.auth_success),
            ("normal, non-flooding request rate (< 10 req/s)", lambda r: r.request_rate_hz < 10.0),
            ("rolling key version out of sync, not a stale replay (> 10)", lambda r: r.rolling_key_version > 10),
        ],
    ),
    _CategoryRule(
        category=AttackCategory.SPOOFING,
        required=[
            ("rolling key passed validation", lambda r: r.rolling_key_valid),
            ("authentication succeeded", lambda r: r.auth_success),
            (
                "anomalous RF link quality (signal <= -90 dBm)",
                lambda r: r.signal_strength_dbm is not None and r.signal_strength_dbm <= -90.0,
            ),
        ],
        # Not required, so a genuine ABNORMAL_DEVICE_BEHAVIOR sample that
        # happens to also have a very negative signal_strength still scores
        # below ABNORMAL_DEVICE_BEHAVIOR's clean 1.0 (see _score_record),
        # instead of tying with SPOOFING on an accidental coincidence.
        supporting=[
            ("telemetry within normal bounds (not an outlier)", lambda r: not _is_telemetry_outlier(r)),
        ],
    ),
    _CategoryRule(
        category=AttackCategory.ABNORMAL_DEVICE_BEHAVIOR,
        required=[
            ("authentication succeeded", lambda r: r.auth_success),
            ("rolling key passed validation", lambda r: r.rolling_key_valid),
            ("telemetry outlier (extreme payload size or session duration)", _is_telemetry_outlier),
        ],
    ),
]


def _score_rule(record: AttackEventRecord, rule: _CategoryRule) -> tuple[float, list[str]]:
    """
    Score one rule against `record`.

    0.0 if any required signal fails (category is not eligible at all).
    Otherwise 1.0 if there are no supporting signals, else a value in
    [0.75, 1.0] scaled by how many supporting signals also matched —
    always strictly less than a "clean" 1.0 match on a required-only rule.
    """
    matched_required = [desc for desc, predicate in rule.required if predicate(record)]
    if len(matched_required) < len(rule.required):
        return 0.0, []

    if not rule.supporting:
        return 1.0, [f"matched signal: {desc}" for desc in matched_required]

    matched_supporting = [desc for desc, predicate in rule.supporting if predicate(record)]
    score = 0.75 + 0.25 * (len(matched_supporting) / len(rule.supporting))
    reasoning = [f"matched signal: {desc}" for desc in matched_required + matched_supporting]
    return score, reasoning


def _score_record(
    record: AttackEventRecord, min_match_ratio: float
) -> tuple[AttackCategory, float, list[str]]:
    """Score `record` against every rule, returning the best category/score/reasoning."""
    best_category = AttackCategory.UNKNOWN
    best_score = 0.0
    best_reasoning: list[str] = []

    for rule in _ATTACK_RULES:
        score, reasoning = _score_rule(record, rule)
        if score > best_score:
            best_score, best_category, best_reasoning = score, rule.category, reasoning

    if best_score < min_match_ratio:
        reasoning = ["no domain heuristic signals matched any known attack category"]
        return AttackCategory.UNKNOWN, best_score, reasoning

    return best_category, best_score, best_reasoning


@dataclass
class AttackClassification:
    """One structured, per-event attack classification."""

    investigation_id: str  # correlates back to the InvestigationFinding this came from
    event_id: str
    category: AttackCategory
    confidence: float  # 0-1 confidence in THIS category assignment
    reasoning: list[str]  # human-readable explanation of the decision
    verdict: str  # passthrough from InvestigationFinding: "ATTACK" | "NORMAL"
    severity: str  # passthrough from InvestigationFinding
    source_confidence: float  # the underlying model's anomaly confidence (InvestigationFinding.confidence)
    matched_ground_truth_category: str | None  # diagnostic-only; never used to decide category
    generated_at: str  # ISO-8601 UTC


@dataclass
class ClassificationReport:
    """A full classification batch: one AttackClassification per finding, plus a rollup."""

    classifications: list[AttackClassification]
    total_events: int
    category_counts: dict[str, int]
    source_investigation: InvestigationReport


class AttackClassifier:
    """
    Converts InvestigationReport findings into standardized AttackCategory
    classifications with confidence and reasoning.

    Usage:
        classifier = AttackClassifier()
        report = classifier.classify(investigation_report)               # category=UNKNOWN for all ATTACK verdicts
        report = classifier.classify(investigation_report, records)      # heuristic sub-typing enabled
        classification = classifier.classify_single(finding, record)     # single-finding convenience
    """

    def __init__(self, min_match_ratio: float = _MIN_CATEGORY_MATCH_RATIO) -> None:
        self._min_match_ratio = min_match_ratio

    def classify(
        self,
        report: InvestigationReport,
        records: list[AttackEventRecord] | None = None,
    ) -> ClassificationReport:
        """
        Build a full ClassificationReport from an InvestigationReport.

        Args:
            report: The InvestigationReport produced by InvestigationAgent.investigate().
            records: Optional source AttackEventRecords, in the same order
                as report.findings. When provided, ATTACK-verdict findings
                are sub-classified via domain heuristics; when omitted,
                every ATTACK verdict classifies as AttackCategory.UNKNOWN
                (there is no signal data to reason from).
        """
        if not isinstance(report, InvestigationReport):
            raise ClassificationError(
                f"AttackClassifier.classify() expects an InvestigationReport, got {type(report).__name__}."
            )
        if records is not None and len(records) != report.total_events:
            raise ClassificationError(
                f"records length ({len(records)}) does not match "
                f"InvestigationReport.total_events ({report.total_events})."
            )

        classifications: list[AttackClassification] = []
        category_counts: dict[str, int] = {}

        for i, finding in enumerate(report.findings):
            record = records[i] if records is not None else None
            classification = self._classify_finding(finding, record)
            classifications.append(classification)
            key = classification.category.value
            category_counts[key] = category_counts.get(key, 0) + 1

        return ClassificationReport(
            classifications=classifications,
            total_events=report.total_events,
            category_counts=category_counts,
            source_investigation=report,
        )

    def classify_single(
        self,
        finding: InvestigationFinding,
        record: AttackEventRecord | None = None,
    ) -> AttackClassification:
        """Convenience for classifying a single InvestigationFinding directly."""
        if not isinstance(finding, InvestigationFinding):
            raise ClassificationError(
                f"AttackClassifier.classify_single() expects an InvestigationFinding, "
                f"got {type(finding).__name__}."
            )
        return self._classify_finding(finding, record)

    # ── internals ────────────────────────────────────────────────────

    def _classify_finding(
        self, finding: InvestigationFinding, record: AttackEventRecord | None
    ) -> AttackClassification:
        ground_truth_category = (
            _EVENT_TYPE_TO_CATEGORY.get(finding.reported_event_type)
            if finding.reported_event_type is not None
            else None
        )

        if finding.verdict == "NORMAL":
            category = AttackCategory.NORMAL
            confidence = round(1.0 - finding.confidence, 4)
            reasoning = [
                "model verdict was NORMAL",
                f"anomaly confidence was low ({finding.confidence:.2%})",
            ]
        elif record is None:
            category = AttackCategory.UNKNOWN
            confidence = 0.0
            reasoning = [
                "verdict is ATTACK but no source AttackEventRecord was provided",
                "cannot determine a specific attack category without underlying signal data",
            ]
        else:
            category, raw_confidence, reasoning = _score_record(record, self._min_match_ratio)
            confidence = round(raw_confidence, 4)

        return AttackClassification(
            investigation_id=finding.investigation_id,
            event_id=finding.event_id,
            category=category,
            confidence=confidence,
            reasoning=reasoning,
            verdict=finding.verdict,
            severity=finding.severity,
            source_confidence=finding.confidence,
            matched_ground_truth_category=(
                ground_truth_category.value if ground_truth_category is not None else None
            ),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
