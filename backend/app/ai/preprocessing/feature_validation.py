"""
app/ai/preprocessing/feature_validation.py — Validation utilities for
extracted/encoded/scaled preprocessing outputs.

Runs at two points in the pipeline:
  1. Right after feature_extraction — catches malformed FeatureVectors
     before any encoding/scaling work is wasted on them.
  2. Right before tensor hand-off — catches NaN/Inf/ragged rows that would
     otherwise silently corrupt a future PyTorch training/inference batch.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .feature_extraction import FeatureVector


@dataclass
class FeatureValidationReport:
    total: int
    invalid_count: int
    duplicate_event_ids: list[str]
    issues: list[str]

    @property
    def is_valid(self) -> bool:
        return self.invalid_count == 0 and not self.duplicate_event_ids


def validate_feature_vector(fv: FeatureVector) -> list[str]:
    """Semantic checks on a single extracted FeatureVector."""
    issues: list[str] = []

    if not fv.event_id:
        issues.append("record missing event_id")
    if not fv.device_id:
        issues.append(f"{fv.event_id}: missing device_id")

    for name, value in fv.numeric.items():
        if value is None or math.isnan(value) or math.isinf(value):
            issues.append(f"{fv.event_id}: numeric feature '{name}' is NaN/Inf/None ({value!r})")

    for name, value in fv.categorical.items():
        if not value:
            issues.append(f"{fv.event_id}: categorical feature '{name}' is empty")

    return issues


def validate_feature_batch(vectors: list[FeatureVector]) -> FeatureValidationReport:
    """Run validate_feature_vector across a batch and check for duplicate event_ids."""
    seen: dict[str, int] = {}
    issues: list[str] = []
    invalid_count = 0

    for fv in vectors:
        seen[fv.event_id] = seen.get(fv.event_id, 0) + 1
        record_issues = validate_feature_vector(fv)
        if record_issues:
            invalid_count += 1
            issues.extend(record_issues)

    duplicates = sorted(eid for eid, count in seen.items() if count > 1)

    return FeatureValidationReport(
        total=len(vectors),
        invalid_count=invalid_count,
        duplicate_event_ids=duplicates,
        issues=issues,
    )


def validate_tensor_ready(rows: list[list[float]], expected_width: int | None = None) -> list[str]:
    """Final sanity check on the flat numeric matrix handed to a future model."""
    issues: list[str] = []
    if not rows:
        return issues

    width = expected_width if expected_width is not None else len(rows[0])
    for i, row in enumerate(rows):
        if len(row) != width:
            issues.append(f"row {i}: width {len(row)} != expected {width}")
            continue
        for j, value in enumerate(row):
            if value is None or math.isnan(value) or math.isinf(value):
                issues.append(f"row {i}, col {j}: NaN/Inf/None value ({value!r})")

    return issues
