"""
app/ai/preprocessing/temporal_sequence.py — Per-device sliding-window
sequence preparation for future sequence models (RNN/Transformer-style
SentinelX architectures).

Groups FeatureVectors by device_id, orders each group chronologically
(deterministically — same tie-break strategy as rolling_key_features.py),
and slices fixed-size windows with a configurable stride. Optionally
left-pads a device's short trailing window so every window has the same
length, which is required before batching windows into a single tensor.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .feature_extraction import FeatureVector


@dataclass
class SequenceWindow:
    """A fixed-length, chronologically ordered slice of one device's events."""

    device_id: str
    vectors: list[FeatureVector]
    padding_mask: list[bool]  # True = real event, False = left-padding
    label_is_attack: bool
    label_event_type: str


def _pad_vector(template: FeatureVector) -> FeatureVector:
    """All-zero numeric / PAD categorical placeholder matching template's shape."""
    return replace(
        template,
        event_id="PAD",
        numeric={k: 0.0 for k in template.numeric},
        categorical={k: "PAD" for k in template.categorical},
        label_event_type="PAD",
        label_is_attack=False,
    )


def _grouped_chronological(vectors: list[FeatureVector]) -> dict[str, list[FeatureVector]]:
    ordered = sorted(vectors, key=lambda fv: (fv.device_id, fv.timestamp, fv.event_id))
    groups: dict[str, list[FeatureVector]] = {}
    for fv in ordered:
        groups.setdefault(fv.device_id, []).append(fv)
    return groups


def build_sequences(
    vectors: list[FeatureVector],
    window_size: int = 10,
    stride: int = 1,
    pad_incomplete: bool = True,
) -> list[SequenceWindow]:
    """
    Build fixed-size, per-device sliding windows in chronological order.

    Args:
        vectors: Feature vectors from any device, any order — grouped and
            sorted internally.
        window_size: Number of events per window.
        stride: Step between consecutive window start positions.
        pad_incomplete: If True, left-pad a device's final short window
            (if any) with zero/"PAD" vectors instead of dropping it.
    """
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    if stride <= 0:
        raise ValueError("stride must be positive")

    windows: list[SequenceWindow] = []
    for device_id, seq in _grouped_chronological(vectors).items():
        n = len(seq)
        start = 0
        while start < n:
            chunk = seq[start : start + window_size]
            if len(chunk) == window_size:
                mask = [True] * window_size
            elif pad_incomplete and chunk:
                pad_count = window_size - len(chunk)
                mask = [False] * pad_count + [True] * len(chunk)
                chunk = [_pad_vector(chunk[0])] * pad_count + chunk
            else:
                break

            last_real = chunk[-1]
            windows.append(
                SequenceWindow(
                    device_id=device_id,
                    vectors=chunk,
                    padding_mask=mask,
                    label_is_attack=last_real.label_is_attack,
                    label_event_type=last_real.label_event_type,
                )
            )

            if not all(mask):
                break  # padded tail window consumed the remainder for this device
            start += stride

    return windows
