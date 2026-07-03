"""
app/ai/preprocessing/tests/test_preprocessing.py — unit tests for the
preprocessing layer: feature extraction, validation, encoding, scaling,
rolling-key engineering, temporal sequencing, tensor prep, and the
end-to-end PreprocessingPipeline.

Uses stdlib unittest (no pytest dependency, consistent with the rest of
app/ai, which adds no new third-party dependencies). Run from backend/:

    python -m unittest discover -s app/ai/preprocessing/tests -p "test_*.py" -v
"""

from __future__ import annotations

import math
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.ai.datasets import AttackLogDataset, DeviceType, EventType, Protocol, generate_dataset
from app.ai.preprocessing import (
    CategoricalEncoder,
    FeatureScaler,
    FeatureVector,
    PipelineNotFittedError,
    PreprocessingError,
    PreprocessingPipeline,
    RollingKeyFeatureEngineer,
    build_row,
    build_sequences,
    extract_batch,
    extract_features,
    records_from_dataset,
    validate_feature_batch,
    validate_feature_vector,
    validate_tensor_ready,
)
from app.ai.preprocessing.feature_extraction import CATEGORICAL_COLUMNS, NUMERIC_COLUMNS


def _make_vector(
    event_id: str,
    device_id: str = "SHIELD-001",
    timestamp: datetime | None = None,
    rolling_key_version: float = 10.0,
    rolling_key_valid: bool = True,
) -> FeatureVector:
    """Hand-crafted FeatureVector for tests that need exact, known values."""
    ts = timestamp or datetime(2026, 1, 1, tzinfo=timezone.utc)
    return FeatureVector(
        event_id=event_id,
        device_id=device_id,
        timestamp=ts,
        numeric={
            "request_rate_hz": 1.0,
            "payload_size_bytes": 100.0,
            "session_duration_ms": 500.0,
            "packet_loss_ratio": 0.01,
            "signal_strength_dbm": -50.0,
            "signal_strength_missing": 0.0,
            "rolling_key_version": rolling_key_version,
            "rolling_key_valid_flag": 1.0 if rolling_key_valid else 0.0,
            "auth_success_flag": 1.0,
            "source_port": 5000.0,
            "destination_port": 14550.0,
            "source_ip_hash_bucket": 42.0,
        },
        categorical={"device_type": "UAV", "protocol": "MAVLINK"},
        label_event_type="NORMAL",
        label_is_attack=False,
    )


class TestFeatureExtraction(unittest.TestCase):
    def setUp(self) -> None:
        self.records = generate_dataset(total=50, seed=1)

    def test_extract_batch_preserves_order_and_count(self) -> None:
        vectors = extract_batch(self.records)
        self.assertEqual(len(vectors), len(self.records))
        self.assertEqual([v.event_id for v in vectors], [r.event_id for r in self.records])

    def test_numeric_keys_match_declared_columns(self) -> None:
        fv = extract_features(self.records[0])
        self.assertEqual(set(fv.numeric.keys()), set(NUMERIC_COLUMNS))

    def test_categorical_keys_match_declared_columns(self) -> None:
        fv = extract_features(self.records[0])
        self.assertEqual(set(fv.categorical.keys()), set(CATEGORICAL_COLUMNS))

    def test_severity_hint_excluded_no_label_leakage(self) -> None:
        for record in self.records:
            fv = extract_features(record)
            self.assertNotIn("severity_hint", fv.numeric)
            self.assertNotIn("event_type", fv.numeric)
            self.assertNotIn("event_type", fv.categorical)

    def test_is_attack_label_matches_event_type(self) -> None:
        for record in self.records:
            fv = extract_features(record)
            self.assertEqual(fv.label_is_attack, record.event_type != EventType.NORMAL)
            self.assertEqual(fv.label_event_type, record.event_type.value)

    def test_missing_signal_strength_flagged(self) -> None:
        record = self.records[0].model_copy(update={"signal_strength_dbm": None})
        fv = extract_features(record)
        self.assertEqual(fv.numeric["signal_strength_missing"], 1.0)
        self.assertEqual(fv.numeric["signal_strength_dbm"], 0.0)

    def test_deterministic_across_calls(self) -> None:
        fv1 = extract_features(self.records[0])
        fv2 = extract_features(self.records[0])
        self.assertEqual(fv1.numeric, fv2.numeric)
        self.assertEqual(fv1.categorical, fv2.categorical)


class TestFeatureValidation(unittest.TestCase):
    def test_valid_vector_has_no_issues(self) -> None:
        fv = _make_vector("e1")
        self.assertEqual(validate_feature_vector(fv), [])

    def test_nan_numeric_flagged(self) -> None:
        fv = _make_vector("e2")
        fv = replace(fv, numeric={**fv.numeric, "request_rate_hz": float("nan")})
        issues = validate_feature_vector(fv)
        self.assertTrue(any("request_rate_hz" in i for i in issues))

    def test_inf_numeric_flagged(self) -> None:
        fv = _make_vector("e3")
        fv = replace(fv, numeric={**fv.numeric, "payload_size_bytes": float("inf")})
        issues = validate_feature_vector(fv)
        self.assertTrue(any("payload_size_bytes" in i for i in issues))

    def test_empty_categorical_flagged(self) -> None:
        fv = _make_vector("e4")
        fv = replace(fv, categorical={**fv.categorical, "device_type": ""})
        issues = validate_feature_vector(fv)
        self.assertTrue(any("device_type" in i for i in issues))

    def test_batch_detects_duplicate_event_ids(self) -> None:
        vectors = [_make_vector("dup"), _make_vector("dup")]
        report = validate_feature_batch(vectors)
        self.assertFalse(report.is_valid)
        self.assertEqual(report.duplicate_event_ids, ["dup"])

    def test_tensor_ready_detects_ragged_rows(self) -> None:
        issues = validate_tensor_ready([[1.0, 2.0], [1.0]])
        self.assertTrue(any("width" in i for i in issues))

    def test_tensor_ready_detects_nan(self) -> None:
        issues = validate_tensor_ready([[1.0, float("nan")]])
        self.assertTrue(any("NaN" in i for i in issues))

    def test_tensor_ready_clean_matrix_has_no_issues(self) -> None:
        issues = validate_tensor_ready([[1.0, 2.0], [3.0, 4.0]])
        self.assertEqual(issues, [])


class TestCategoricalEncoding(unittest.TestCase):
    def test_from_enum_size_matches_member_count(self) -> None:
        enc = CategoricalEncoder.from_enum(DeviceType)
        self.assertEqual(enc.size, len(list(DeviceType)))

    def test_one_hot_sums_to_one(self) -> None:
        enc = CategoricalEncoder.from_enum(Protocol)
        row = enc.encode_one_hot(Protocol.MQTT.value)
        self.assertEqual(sum(row), 1.0)
        self.assertEqual(len(row), enc.size)

    def test_unknown_category_raises(self) -> None:
        enc = CategoricalEncoder.from_enum(DeviceType)
        with self.assertRaises(ValueError):
            enc.encode_index("NOT_A_DEVICE")

    def test_encode_decode_roundtrip(self) -> None:
        enc = CategoricalEncoder.from_enum(DeviceType)
        for value in enc.values:
            idx = enc.encode_index(value)
            self.assertEqual(enc.decode_index(idx), value)

    def test_to_dict_from_dict_roundtrip(self) -> None:
        enc = CategoricalEncoder.from_enum(Protocol)
        restored = CategoricalEncoder.from_dict(enc.to_dict())
        self.assertEqual(enc.values, restored.values)
        for value in enc.values:
            self.assertEqual(enc.encode_one_hot(value), restored.encode_one_hot(value))

    def test_column_names_prefixed(self) -> None:
        enc = CategoricalEncoder.from_enum(DeviceType)
        names = enc.column_names("device_type")
        self.assertTrue(all(n.startswith("device_type__") for n in names))
        self.assertEqual(len(names), enc.size)


class TestNumericalScaling(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = [{"x": 1.0, "y": 10.0}, {"x": 2.0, "y": 20.0}, {"x": 3.0, "y": 30.0}]

    def test_standard_scaler_zero_mean(self) -> None:
        scaler = FeatureScaler(kind="standard").fit(self.rows, columns=["x", "y"])
        transformed = scaler.transform(self.rows)
        mean_x = sum(r["x"] for r in transformed) / len(transformed)
        self.assertAlmostEqual(mean_x, 0.0, places=9)

    def test_minmax_scaler_bounds(self) -> None:
        scaler = FeatureScaler(kind="minmax").fit(self.rows, columns=["x", "y"])
        transformed = scaler.transform(self.rows)
        for r in transformed:
            for v in r.values():
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 1.0)
        self.assertAlmostEqual(transformed[0]["x"], 0.0)
        self.assertAlmostEqual(transformed[-1]["x"], 1.0)

    def test_zero_variance_column_does_not_crash(self) -> None:
        rows = [{"x": 5.0}, {"x": 5.0}, {"x": 5.0}]
        scaler = FeatureScaler(kind="standard").fit(rows, columns=["x"])
        transformed = scaler.transform(rows)
        self.assertTrue(all(r["x"] == 0.0 for r in transformed))

    def test_transform_before_fit_raises(self) -> None:
        scaler = FeatureScaler(kind="standard")
        with self.assertRaises(RuntimeError):
            scaler.transform(self.rows)

    def test_to_dict_from_dict_roundtrip_identical_output(self) -> None:
        scaler = FeatureScaler(kind="standard").fit(self.rows, columns=["x", "y"])
        restored = FeatureScaler.from_dict(scaler.to_dict())
        self.assertEqual(scaler.transform(self.rows), restored.transform(self.rows))

    def test_invalid_kind_rejected(self) -> None:
        with self.assertRaises(ValueError):
            FeatureScaler(kind="bogus")


class TestRollingKeyFeatures(unittest.TestCase):
    def test_first_event_has_zero_delta_and_no_reuse(self) -> None:
        vectors = [_make_vector("e1", rolling_key_version=10.0)]
        enriched = RollingKeyFeatureEngineer().transform(vectors)
        fv = enriched[0]
        self.assertEqual(fv.numeric["key_version_delta"], 0.0)
        self.assertEqual(fv.numeric["key_version_reused"], 0.0)
        self.assertEqual(fv.numeric["consecutive_invalid_key_count"], 0.0)

    def test_known_sequence_produces_expected_values(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        vectors = [
            _make_vector("e1", timestamp=base, rolling_key_version=10.0, rolling_key_valid=True),
            _make_vector(
                "e2", timestamp=base + timedelta(seconds=1), rolling_key_version=11.0, rolling_key_valid=True
            ),
            # replay: reuses an old version, and is invalid
            _make_vector(
                "e3", timestamp=base + timedelta(seconds=2), rolling_key_version=10.0, rolling_key_valid=False
            ),
            # brute force continuation: another invalid guess right after
            _make_vector(
                "e4", timestamp=base + timedelta(seconds=3), rolling_key_version=3.0, rolling_key_valid=False
            ),
            # recovers with a valid, higher key
            _make_vector(
                "e5", timestamp=base + timedelta(seconds=4), rolling_key_version=12.0, rolling_key_valid=True
            ),
        ]
        enriched = {fv.event_id: fv for fv in RollingKeyFeatureEngineer().transform(vectors)}

        self.assertEqual(enriched["e1"].numeric["key_version_delta"], 0.0)
        self.assertEqual(enriched["e2"].numeric["key_version_delta"], 1.0)
        self.assertEqual(enriched["e2"].numeric["key_version_reused"], 0.0)

        self.assertEqual(enriched["e3"].numeric["key_version_delta"], -1.0)
        self.assertEqual(enriched["e3"].numeric["key_version_reused"], 1.0)
        self.assertEqual(enriched["e3"].numeric["consecutive_invalid_key_count"], 1.0)

        self.assertEqual(enriched["e4"].numeric["consecutive_invalid_key_count"], 2.0)
        self.assertEqual(enriched["e4"].numeric["key_version_reused"], 1.0)

        self.assertEqual(enriched["e5"].numeric["consecutive_invalid_key_count"], 0.0)
        self.assertEqual(enriched["e5"].numeric["key_version_reused"], 0.0)

    def test_deterministic_regardless_of_input_order(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        vectors = [
            _make_vector("e1", timestamp=base, rolling_key_version=10.0),
            _make_vector("e2", timestamp=base + timedelta(seconds=1), rolling_key_version=11.0),
            _make_vector("e3", timestamp=base + timedelta(seconds=2), rolling_key_version=9.0, rolling_key_valid=False),
        ]
        forward = {fv.event_id: fv.numeric for fv in RollingKeyFeatureEngineer().transform(vectors)}
        reversed_input = list(reversed(vectors))
        backward = {fv.event_id: fv.numeric for fv in RollingKeyFeatureEngineer().transform(reversed_input)}
        self.assertEqual(forward, backward)

    def test_separate_devices_do_not_interfere(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        vectors = [
            _make_vector("a1", device_id="SHIELD-001", timestamp=base, rolling_key_version=50.0),
            _make_vector("b1", device_id="SHIELD-002", timestamp=base, rolling_key_version=1.0),
        ]
        enriched = {fv.event_id: fv for fv in RollingKeyFeatureEngineer().transform(vectors)}
        self.assertEqual(enriched["a1"].numeric["key_version_delta"], 0.0)
        self.assertEqual(enriched["b1"].numeric["key_version_delta"], 0.0)

    def test_empty_input(self) -> None:
        self.assertEqual(RollingKeyFeatureEngineer().transform([]), [])


class TestTemporalSequence(unittest.TestCase):
    def _sequence_for_device(self, n: int, device_id: str = "SHIELD-001") -> list[FeatureVector]:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        return [
            _make_vector(f"e{i}", device_id=device_id, timestamp=base + timedelta(seconds=i))
            for i in range(n)
        ]

    def test_exact_multiple_produces_full_windows_only(self) -> None:
        vectors = self._sequence_for_device(10)
        windows = build_sequences(vectors, window_size=5, stride=5, pad_incomplete=True)
        self.assertEqual(len(windows), 2)
        for w in windows:
            self.assertEqual(len(w.vectors), 5)
            self.assertTrue(all(w.padding_mask))

    def test_short_sequence_padded(self) -> None:
        vectors = self._sequence_for_device(3)
        windows = build_sequences(vectors, window_size=5, stride=5, pad_incomplete=True)
        self.assertEqual(len(windows), 1)
        w = windows[0]
        self.assertEqual(len(w.vectors), 5)
        self.assertEqual(w.padding_mask, [False, False, True, True, True])
        self.assertEqual([v.event_id for v in w.vectors[2:]], ["e0", "e1", "e2"])

    def test_short_sequence_dropped_without_padding(self) -> None:
        vectors = self._sequence_for_device(3)
        windows = build_sequences(vectors, window_size=5, stride=5, pad_incomplete=False)
        self.assertEqual(windows, [])

    def test_windows_scoped_per_device(self) -> None:
        vectors = self._sequence_for_device(5, "SHIELD-001") + self._sequence_for_device(5, "SHIELD-002")
        windows = build_sequences(vectors, window_size=5, stride=5)
        devices = {w.device_id for w in windows}
        self.assertEqual(devices, {"SHIELD-001", "SHIELD-002"})

    def test_invalid_window_size_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_sequences([], window_size=0)

    def test_label_reflects_last_real_event(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        vectors = self._sequence_for_device(3)
        vectors[-1] = replace(vectors[-1], label_is_attack=True, label_event_type="DOS")
        windows = build_sequences(vectors, window_size=3, stride=3, pad_incomplete=True)
        self.assertTrue(windows[0].label_is_attack)
        self.assertEqual(windows[0].label_event_type, "DOS")


class TestTensorPrep(unittest.TestCase):
    def test_build_row_width_matches_columns(self) -> None:
        fv = _make_vector("e1")
        device_enc = CategoricalEncoder.from_enum(DeviceType)
        protocol_enc = CategoricalEncoder.from_enum(Protocol)
        encoders = {"device_type": device_enc, "protocol": protocol_enc}
        row = build_row(fv.numeric, fv.categorical, NUMERIC_COLUMNS, CATEGORICAL_COLUMNS, encoders)
        expected_width = len(NUMERIC_COLUMNS) + device_enc.size + protocol_enc.size
        self.assertEqual(len(row), expected_width)

    def test_to_torch_raises_clear_error_when_torch_missing(self) -> None:
        try:
            import torch  # noqa: F401

            self.skipTest("torch is installed in this environment")
        except ImportError:
            pass
        from app.ai.preprocessing import TensorBatch

        batch = TensorBatch(rows=[[1.0, 2.0]], feature_names=["a", "b"], labels=[0], label_names=["NORMAL"])
        with self.assertRaises(ImportError):
            batch.to_torch()


class TestPreprocessingPipelineIntegration(unittest.TestCase):
    """End-to-end: dataset registry -> AttackLogDataset -> pipeline -> TensorBatch."""

    def setUp(self) -> None:
        self.dataset = AttackLogDataset(size=300, seed=7)
        self.dataset.load()

    def test_records_from_dataset_matches_dataset_records(self) -> None:
        via_helper = records_from_dataset(self.dataset)
        self.assertEqual([r.event_id for r in via_helper], [r.event_id for r in self.dataset.records])

    def test_fit_transform_produces_rectangular_matrix(self) -> None:
        pipeline = PreprocessingPipeline()
        batch = pipeline.fit_transform(self.dataset.records)
        self.assertEqual(batch.shape[0], len(self.dataset))
        widths = {len(row) for row in batch.rows}
        self.assertEqual(widths, {batch.shape[1]})
        self.assertEqual(len(batch.feature_names), batch.shape[1])

    def test_labels_are_binary_and_aligned(self) -> None:
        pipeline = PreprocessingPipeline()
        batch = pipeline.fit_transform(self.dataset.records)
        self.assertEqual(len(batch.labels), len(self.dataset.records))
        self.assertTrue(set(batch.labels).issubset({0, 1}))
        for record, label in zip(self.dataset.records, batch.labels):
            self.assertEqual(label, 1 if record.event_type != EventType.NORMAL else 0)

    def test_no_nan_or_inf_in_output(self) -> None:
        pipeline = PreprocessingPipeline()
        batch = pipeline.fit_transform(self.dataset.records)
        for row in batch.rows:
            for value in row:
                self.assertFalse(math.isnan(value))
                self.assertFalse(math.isinf(value))

    def test_transform_is_deterministic_across_runs(self) -> None:
        pipeline_a = PreprocessingPipeline().fit(self.dataset.records)
        pipeline_b = PreprocessingPipeline().fit(self.dataset.records)
        batch_a = pipeline_a.transform(self.dataset.records)
        batch_b = pipeline_b.transform(self.dataset.records)
        self.assertEqual(batch_a.rows, batch_b.rows)
        self.assertEqual(batch_a.labels, batch_b.labels)

    def test_transform_before_fit_raises(self) -> None:
        pipeline = PreprocessingPipeline()
        with self.assertRaises(PipelineNotFittedError):
            pipeline.transform(self.dataset.records)

    def test_fit_on_empty_records_raises(self) -> None:
        pipeline = PreprocessingPipeline()
        with self.assertRaises(PreprocessingError):
            pipeline.fit([])

    def test_to_dict_from_dict_roundtrip_reproduces_transform(self) -> None:
        pipeline = PreprocessingPipeline().fit(self.dataset.records)
        original_batch = pipeline.transform(self.dataset.records)

        restored = PreprocessingPipeline.from_dict(pipeline.to_dict())
        restored_batch = restored.transform(self.dataset.records)

        self.assertEqual(original_batch.rows, restored_batch.rows)
        self.assertEqual(original_batch.feature_names, restored_batch.feature_names)
        self.assertEqual(original_batch.labels, restored_batch.labels)

    def test_persisted_pipeline_transforms_new_unseen_records_consistently(self) -> None:
        """Simulates the real inference scenario: fit on a training set, persist,
        then transform records the scaler/encoder never saw during fit()."""
        train_records = self.dataset.records[:200]
        held_out_records = self.dataset.records[200:]

        pipeline = PreprocessingPipeline().fit(train_records)
        persisted = pipeline.to_dict()

        reloaded = PreprocessingPipeline.from_dict(persisted)
        batch = reloaded.transform(held_out_records)

        self.assertEqual(batch.shape[0], len(held_out_records))
        for row in batch.rows:
            for value in row:
                self.assertFalse(math.isnan(value))
                self.assertFalse(math.isinf(value))

    def test_transform_single_returns_one_row_matching_batch_width(self) -> None:
        pipeline = PreprocessingPipeline().fit(self.dataset.records)
        full_batch = pipeline.transform(self.dataset.records)
        single_batch = pipeline.transform_single(self.dataset.records[0])
        self.assertEqual(single_batch.shape, (1, full_batch.shape[1]))
        self.assertEqual(single_batch.feature_names, full_batch.feature_names)

    def test_pipeline_compatible_with_dataset_registry_lookup(self) -> None:
        from app.ai.datasets import get_dataset

        dataset_cls = get_dataset("attack_logs")
        dataset = dataset_cls(size=50, seed=3)
        dataset.load()
        pipeline = PreprocessingPipeline()
        batch = pipeline.fit_transform(records_from_dataset(dataset))
        # generate_dataset() rounds per-class counts independently, so the
        # actual size can differ slightly from the requested `size`.
        self.assertEqual(batch.shape[0], len(dataset))
        self.assertGreater(batch.shape[0], 0)


if __name__ == "__main__":
    unittest.main()
