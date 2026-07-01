"""
app/ai/preprocessing/rolling_key_features.py — Device-history-aware rolling
key feature engineering.

The raw rolling_key_version/rolling_key_valid fields (already present in
FeatureVector.numeric via feature_extraction.py) only describe a single
event in isolation. Real rolling-key attacks (replay, brute force) show up
in the *sequence* of a device's key usage over time, so this module adds
three history-derived features per event, computed by replaying each
device's events in chronological order:

    key_version_delta             — version minus the previous version seen
                                     for this device (0 for a device's first
                                     event; non-positive can indicate a
                                     stale/reused key, e.g. REPLAY)
    key_version_reused             — 1.0 if this version was <= the highest
                                     version already seen for this device
    consecutive_invalid_key_count  — running count of back-to-back invalid
                                     keys for this device, reset to 0 on a
                                     valid key (BRUTE_FORCE signature)

Sorting uses (device_id, timestamp, event_id) as the key, so results are
fully deterministic regardless of the input list's order — event_id
uniqueness is already guaranteed by app.ai.datasets.validators before a
dataset is ever loaded.
"""

from __future__ import annotations

from dataclasses import replace

from .feature_extraction import FeatureVector

ROLLING_KEY_FEATURE_NAMES: list[str] = [
    "key_version_delta",
    "key_version_reused",
    "consecutive_invalid_key_count",
]


class RollingKeyFeatureEngineer:
    """Stateless wrapper around a deterministic, order-independent transform."""

    def transform(self, vectors: list[FeatureVector]) -> list[FeatureVector]:
        if not vectors:
            return []

        order = sorted(
            range(len(vectors)),
            key=lambda i: (vectors[i].device_id, vectors[i].timestamp, vectors[i].event_id),
        )

        last_version: dict[str, float] = {}
        max_version: dict[str, float] = {}
        invalid_streak: dict[str, int] = {}
        enriched: list[FeatureVector | None] = [None] * len(vectors)

        for idx in order:
            fv = vectors[idx]
            device = fv.device_id
            version = fv.numeric["rolling_key_version"]
            valid = fv.numeric["rolling_key_valid_flag"] >= 0.5

            prev_version = last_version.get(device)
            prev_max = max_version.get(device, float("-inf"))

            delta = 0.0 if prev_version is None else version - prev_version
            reused = 1.0 if version <= prev_max else 0.0
            streak = 0 if valid else invalid_streak.get(device, 0) + 1

            new_numeric = dict(fv.numeric)
            new_numeric["key_version_delta"] = delta
            new_numeric["key_version_reused"] = reused
            new_numeric["consecutive_invalid_key_count"] = float(streak)
            enriched[idx] = replace(fv, numeric=new_numeric)

            last_version[device] = version
            max_version[device] = max(prev_max, version)
            invalid_streak[device] = streak

        return enriched  # type: ignore[return-value]
