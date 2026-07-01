"""
app/ai/datasets/validators.py — Validation utilities for attack-event datasets.

Pydantic (via AttackEventRecord) already enforces per-field structural
validity — types, ranges, IP format, etc. This module adds the checks
that only make sense across a whole dataset or in relation to domain
semantics that a single field can't express on its own: duplicate IDs,
class balance, and label/attribute consistency.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone

from .schema import AttackEventRecord, EventType


@dataclass
class DatasetValidationReport:
    """Result of validating a full dataset."""

    total_records: int
    class_distribution: dict[str, int]
    duplicate_event_ids: list[str]
    semantic_issues: list[str]

    @property
    def is_valid(self) -> bool:
        return not self.duplicate_event_ids and not self.semantic_issues

    def summary(self) -> str:
        status = "VALID" if self.is_valid else "INVALID"
        return (
            f"[{status}] {self.total_records} records | "
            f"classes={self.class_distribution} | "
            f"duplicates={len(self.duplicate_event_ids)} | "
            f"issues={len(self.semantic_issues)}"
        )


def validate_record(record: AttackEventRecord) -> list[str]:
    """Semantic checks beyond what the Pydantic schema already enforces."""
    issues: list[str] = []

    if record.timestamp > datetime.now(timezone.utc):
        issues.append(f"{record.event_id}: timestamp is in the future")

    if record.source_ip == record.destination_ip:
        issues.append(f"{record.event_id}: source_ip equals destination_ip")

    if record.event_type == EventType.NORMAL and not record.auth_success:
        issues.append(f"{record.event_id}: NORMAL event has auth_success=False")

    if record.event_type == EventType.NORMAL and not record.rolling_key_valid:
        issues.append(f"{record.event_id}: NORMAL event has rolling_key_valid=False")

    return issues


def validate_dataset(
    records: list[AttackEventRecord],
    *,
    require_all_classes: bool = False,
) -> DatasetValidationReport:
    """
    Run structural + semantic validation across an entire dataset.

    Args:
        records: The dataset to validate.
        require_all_classes: If True, flag as invalid when any EventType
            has zero representation — useful as a pre-training sanity check.
    """
    seen: Counter[str] = Counter()
    issues: list[str] = []

    for record in records:
        seen[record.event_id] += 1
        issues.extend(validate_record(record))

    duplicates = sorted(eid for eid, count in seen.items() if count > 1)
    distribution = Counter(r.event_type.value for r in records)

    if require_all_classes:
        missing = [et.value for et in EventType if distribution.get(et.value, 0) == 0]
        issues.extend(f"missing class: {name}" for name in missing)

    return DatasetValidationReport(
        total_records=len(records),
        class_distribution=dict(sorted(distribution.items())),
        duplicate_event_ids=duplicates,
        semantic_issues=issues,
    )
