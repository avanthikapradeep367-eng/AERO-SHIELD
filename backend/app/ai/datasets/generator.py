"""
app/ai/datasets/generator.py — Synthetic aerospace cybersecurity log generator.

Produces deterministic (seedable), labeled AttackEventRecord logs covering
normal authentication/network traffic plus six attack/anomaly categories
relevant to an aerospace rolling-key authentication system:

    NORMAL                     — healthy device traffic
    REPLAY                     — captured traffic re-sent with a stale key
    BRUTE_FORCE                — rapid repeated authentication failures
    SPOOFING                   — identity/IP mismatch using a stolen key
    DOS                        — volumetric flood against a device/gateway
    INVALID_ROLLING_KEY        — malformed/out-of-sync key, low request rate
    ABNORMAL_DEVICE_BEHAVIOR   — valid credentials, anomalous telemetry pattern

No machine learning happens here — this module only crafts plausible,
schema-valid synthetic records for later preprocessing/training.

IP ranges are drawn from RFC 5737 documentation-only blocks (192.0.2.0/24,
198.51.100.0/24, 203.0.113.0/24) and RFC 1918 private space, so no real
public IP addresses are ever generated.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

from .schema import AttackEventRecord, DeviceType, EventType, Protocol

_DEVICE_POOL: list[str] = [f"SHIELD-{i:03d}" for i in range(1, 21)]
_DEVICE_TYPES: list[DeviceType] = list(DeviceType)
_PROTOCOLS: list[Protocol] = list(Protocol)
_DEST_PORTS: dict[Protocol, list[int]] = {
    Protocol.MAVLINK: [14550],
    Protocol.MQTT: [1883, 8883],
    Protocol.HTTPS: [443],
    Protocol.CUSTOM_RF: [9000, 9001],
}

# RFC 1918 private range — trusted internal devices (never the .0.x octet, which
# is reserved for _GATEWAY_IP below, so source_ip can never collide with it)
_TRUSTED_SUBNET = "10.0.{}.{}"
# Fixed ground-station gateway address — the single destination all simulated
# devices talk to; keeping it constant also guarantees source_ip != destination_ip
_GATEWAY_IP = "10.0.0.1"
# RFC 5737 TEST-NET-3 — reserved for documentation; used for unknown/external sources
_EXTERNAL_SUBNET = "203.0.113.{}"
# RFC 5737 TEST-NET-2 — reserved for documentation; used for spoofed/mimicked sources
_SPOOF_SUBNET = "198.51.100.{}"

DEFAULT_CLASS_WEIGHTS: dict[EventType, float] = {
    EventType.NORMAL: 0.55,
    EventType.REPLAY: 0.07,
    EventType.BRUTE_FORCE: 0.08,
    EventType.SPOOFING: 0.08,
    EventType.DOS: 0.07,
    EventType.INVALID_ROLLING_KEY: 0.08,
    EventType.ABNORMAL_DEVICE_BEHAVIOR: 0.07,
}


class SyntheticEventGenerator:
    """
    Deterministic, seedable generator for synthetic aerospace authentication
    and network-event logs across all EventType categories.

    Usage:
        gen = SyntheticEventGenerator(seed=42)
        records = gen.generate(total=1000)
    """

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self._rng = random.Random(seed)

    # ── shared helpers ──────────────────────────────────────────────

    def _new_event_id(self) -> str:
        return str(uuid.UUID(int=self._rng.getrandbits(128), version=4))

    def _timestamp(self, base: datetime, jitter_seconds: float = 3600.0) -> datetime:
        """Return a timestamp up to `jitter_seconds` before `base` (never in the future)."""
        offset = self._rng.uniform(0, jitter_seconds)
        return base - timedelta(seconds=offset)

    def _pick_device(self) -> tuple[str, DeviceType]:
        return self._rng.choice(_DEVICE_POOL), self._rng.choice(_DEVICE_TYPES)

    def _trusted_ip(self) -> str:
        return _TRUSTED_SUBNET.format(self._rng.randint(1, 5), self._rng.randint(2, 254))

    def _external_ip(self) -> str:
        return _EXTERNAL_SUBNET.format(self._rng.randint(1, 254))

    def _spoofed_ip(self) -> str:
        return _SPOOF_SUBNET.format(self._rng.randint(1, 254))

    def _base_kwargs(self, base_time: datetime, event_type: EventType) -> dict:
        device_id, device_type = self._pick_device()
        protocol = self._rng.choice(_PROTOCOLS)
        return dict(
            event_id=self._new_event_id(),
            timestamp=self._timestamp(base_time),
            device_id=device_id,
            device_type=device_type,
            event_type=event_type,
            protocol=protocol,
            destination_ip=_GATEWAY_IP,
            destination_port=self._rng.choice(_DEST_PORTS[protocol]),
        )

    # ── per-category generators ─────────────────────────────────────

    def normal_traffic(self, n: int, base_time: datetime | None = None) -> list[AttackEventRecord]:
        """Healthy device traffic: valid key, successful auth, low/steady rate."""
        base_time = base_time or datetime.now(timezone.utc)
        out = []
        for _ in range(n):
            kw = self._base_kwargs(base_time, EventType.NORMAL)
            out.append(
                AttackEventRecord(
                    **kw,
                    source_ip=self._trusted_ip(),
                    source_port=self._rng.randint(1024, 65535),
                    rolling_key_version=self._rng.randint(5, 50),
                    rolling_key_valid=True,
                    auth_success=True,
                    request_rate_hz=round(self._rng.uniform(0.2, 4.0), 2),
                    payload_size_bytes=self._rng.randint(64, 512),
                    session_duration_ms=round(self._rng.uniform(200, 4000), 1),
                    packet_loss_ratio=round(self._rng.uniform(0.0, 0.02), 4),
                    signal_strength_dbm=round(self._rng.uniform(-75, -40), 1),
                    severity_hint=0.0,
                )
            )
        return out

    def replay_attack(self, n: int, base_time: datetime | None = None) -> list[AttackEventRecord]:
        """Captured traffic re-sent later: stale key version, rejected auth."""
        base_time = base_time or datetime.now(timezone.utc)
        out = []
        for _ in range(n):
            kw = self._base_kwargs(base_time, EventType.REPLAY)
            out.append(
                AttackEventRecord(
                    **kw,
                    source_ip=self._trusted_ip(),
                    source_port=self._rng.randint(1024, 65535),
                    rolling_key_version=self._rng.randint(1, 4),  # stale/expired version
                    rolling_key_valid=False,
                    auth_success=False,
                    request_rate_hz=round(self._rng.uniform(0.1, 2.0), 2),
                    payload_size_bytes=self._rng.randint(64, 512),
                    session_duration_ms=round(self._rng.uniform(200, 4000), 1),
                    packet_loss_ratio=round(self._rng.uniform(0.0, 0.05), 4),
                    signal_strength_dbm=round(self._rng.uniform(-80, -45), 1),
                    severity_hint=round(self._rng.uniform(55.0, 75.0), 1),
                )
            )
        return out

    def brute_force_attack(self, n: int, base_time: datetime | None = None) -> list[AttackEventRecord]:
        """Rapid repeated authentication failures from an external source."""
        base_time = base_time or datetime.now(timezone.utc)
        out = []
        for _ in range(n):
            kw = self._base_kwargs(base_time, EventType.BRUTE_FORCE)
            out.append(
                AttackEventRecord(
                    **kw,
                    source_ip=self._external_ip(),
                    source_port=self._rng.randint(1024, 65535),
                    rolling_key_version=self._rng.randint(0, 999),  # guessed
                    rolling_key_valid=False,
                    auth_success=self._rng.random() < 0.02,  # rare lucky guess
                    request_rate_hz=round(self._rng.uniform(10.0, 100.0), 2),
                    payload_size_bytes=self._rng.randint(32, 256),
                    session_duration_ms=round(self._rng.uniform(20, 300), 1),
                    packet_loss_ratio=round(self._rng.uniform(0.0, 0.1), 4),
                    signal_strength_dbm=round(self._rng.uniform(-90, -50), 1),
                    severity_hint=round(self._rng.uniform(65.0, 85.0), 1),
                )
            )
        return out

    def spoofing_attack(self, n: int, base_time: datetime | None = None) -> list[AttackEventRecord]:
        """Stolen/valid key presented from an unrecognized, mimicked source."""
        base_time = base_time or datetime.now(timezone.utc)
        out = []
        for _ in range(n):
            kw = self._base_kwargs(base_time, EventType.SPOOFING)
            out.append(
                AttackEventRecord(
                    **kw,
                    source_ip=self._spoofed_ip(),
                    source_port=self._rng.randint(1024, 65535),
                    rolling_key_version=self._rng.randint(5, 50),
                    rolling_key_valid=True,  # key itself validates — identity is the problem
                    auth_success=True,
                    request_rate_hz=round(self._rng.uniform(0.5, 5.0), 2),
                    payload_size_bytes=self._rng.randint(64, 512),
                    session_duration_ms=round(self._rng.uniform(200, 4000), 1),
                    packet_loss_ratio=round(self._rng.uniform(0.0, 0.03), 4),
                    signal_strength_dbm=round(self._rng.uniform(-125, -95), 1),  # anomalous link quality
                    severity_hint=round(self._rng.uniform(70.0, 90.0), 1),
                )
            )
        return out

    def dos_attack(self, n: int, base_time: datetime | None = None) -> list[AttackEventRecord]:
        """Volumetric flood: extreme request rate, large payloads, high packet loss."""
        base_time = base_time or datetime.now(timezone.utc)
        out = []
        for _ in range(n):
            kw = self._base_kwargs(base_time, EventType.DOS)
            out.append(
                AttackEventRecord(
                    **kw,
                    source_ip=self._external_ip(),
                    source_port=self._rng.randint(1024, 65535),
                    rolling_key_version=self._rng.randint(0, 50),
                    rolling_key_valid=self._rng.random() < 0.1,
                    auth_success=self._rng.random() < 0.05,
                    request_rate_hz=round(self._rng.uniform(100.0, 2000.0), 2),
                    payload_size_bytes=self._rng.randint(512, 9000),
                    session_duration_ms=round(self._rng.uniform(5, 100), 1),
                    packet_loss_ratio=round(self._rng.uniform(0.3, 0.95), 4),
                    signal_strength_dbm=round(self._rng.uniform(-110, -60), 1),
                    severity_hint=round(self._rng.uniform(80.0, 98.0), 1),
                )
            )
        return out

    def invalid_rolling_key(self, n: int, base_time: datetime | None = None) -> list[AttackEventRecord]:
        """Out-of-sync/malformed key at normal request rate — not a flood, not a replay."""
        base_time = base_time or datetime.now(timezone.utc)
        out = []
        for _ in range(n):
            kw = self._base_kwargs(base_time, EventType.INVALID_ROLLING_KEY)
            out.append(
                AttackEventRecord(
                    **kw,
                    source_ip=self._trusted_ip(),
                    source_port=self._rng.randint(1024, 65535),
                    rolling_key_version=self._rng.randint(51, 200),  # ahead of expected
                    rolling_key_valid=False,
                    auth_success=False,
                    request_rate_hz=round(self._rng.uniform(0.2, 3.0), 2),
                    payload_size_bytes=self._rng.randint(64, 512),
                    session_duration_ms=round(self._rng.uniform(200, 4000), 1),
                    packet_loss_ratio=round(self._rng.uniform(0.0, 0.05), 4),
                    signal_strength_dbm=round(self._rng.uniform(-80, -45), 1),
                    severity_hint=round(self._rng.uniform(40.0, 60.0), 1),
                )
            )
        return out

    def abnormal_device_behavior(
        self, n: int, base_time: datetime | None = None
    ) -> list[AttackEventRecord]:
        """Valid credentials but anomalous telemetry — malfunction or subtle compromise."""
        base_time = base_time or datetime.now(timezone.utc)
        out = []
        for _ in range(n):
            kw = self._base_kwargs(base_time, EventType.ABNORMAL_DEVICE_BEHAVIOR)
            # Bimodal outliers: unusually tiny or unusually large session/payload.
            short_session = self._rng.random() < 0.5
            out.append(
                AttackEventRecord(
                    **kw,
                    source_ip=self._trusted_ip(),
                    source_port=self._rng.randint(1024, 65535),
                    rolling_key_version=self._rng.randint(5, 50),
                    rolling_key_valid=True,
                    auth_success=True,
                    request_rate_hz=round(self._rng.uniform(0.01, 50.0), 2),
                    payload_size_bytes=(
                        self._rng.randint(1, 16) if short_session else self._rng.randint(4000, 8000)
                    ),
                    session_duration_ms=(
                        round(self._rng.uniform(1, 50), 1)
                        if short_session
                        else round(self._rng.uniform(30000, 90000), 1)
                    ),
                    packet_loss_ratio=round(self._rng.uniform(0.0, 0.4), 4),
                    signal_strength_dbm=round(self._rng.uniform(-130, -20), 1),
                    severity_hint=round(self._rng.uniform(30.0, 55.0), 1),
                )
            )
        return out

    # ── combined dataset generation ─────────────────────────────────

    def generate(
        self,
        total: int,
        class_weights: dict[EventType, float] | None = None,
        base_time: datetime | None = None,
        shuffle: bool = True,
    ) -> list[AttackEventRecord]:
        """
        Generate a mixed dataset spanning all event categories.

        Args:
            total: Approximate total number of records to generate.
            class_weights: Proportion (summing to ~1.0) allocated per
                EventType. Defaults to DEFAULT_CLASS_WEIGHTS, which mirrors
                a realistic class imbalance (majority normal traffic).
            base_time: Anchor time for generated timestamps. Defaults to now (UTC).
            shuffle: Whether to shuffle the combined record order.
        """
        weights = class_weights or DEFAULT_CLASS_WEIGHTS
        base_time = base_time or datetime.now(timezone.utc)

        dispatch = {
            EventType.NORMAL: self.normal_traffic,
            EventType.REPLAY: self.replay_attack,
            EventType.BRUTE_FORCE: self.brute_force_attack,
            EventType.SPOOFING: self.spoofing_attack,
            EventType.DOS: self.dos_attack,
            EventType.INVALID_ROLLING_KEY: self.invalid_rolling_key,
            EventType.ABNORMAL_DEVICE_BEHAVIOR: self.abnormal_device_behavior,
        }

        records: list[AttackEventRecord] = []
        for event_type, weight in weights.items():
            count = round(total * weight)
            if count <= 0:
                continue
            records.extend(dispatch[event_type](count, base_time=base_time))

        if shuffle:
            self._rng.shuffle(records)
        return records


def generate_dataset(
    total: int = 1000,
    seed: int = 42,
    class_weights: dict[EventType, float] | None = None,
) -> list[AttackEventRecord]:
    """Module-level convenience wrapper around SyntheticEventGenerator.generate()."""
    return SyntheticEventGenerator(seed=seed).generate(total, class_weights=class_weights)
