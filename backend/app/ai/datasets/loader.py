"""
app/ai/datasets/loader.py — AttackLogDataset: BaseDataset implementation
backed by the synthetic aerospace attack-event generator.

Ties together schema.py (record shape), generator.py (synthetic data),
and validators.py (structural/semantic checks) behind the BaseDataset
contract, and registers itself in the dataset registry under the name
"attack_logs" so it can be retrieved via:

    from app.ai.datasets import get_dataset
    dataset_cls = get_dataset("attack_logs")
    dataset = dataset_cls()
    dataset.load()

Also supports persisting a generated dataset to a JSON-Lines file and
reloading it later, so a specific generated dataset (fixed seed) can be
reused across repeated training runs instead of being regenerated.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app.ai.exceptions import DatasetError

from .base import BaseDataset
from .generator import SyntheticEventGenerator
from .registry import register_dataset
from .schema import AttackEventRecord, DatasetMetadata, EventType
from .validators import validate_dataset


@register_dataset("attack_logs")
class AttackLogDataset(BaseDataset):
    """
    Synthetic aerospace authentication/network-event dataset.

    Generates records via SyntheticEventGenerator (default), or loads a
    previously saved dataset from a JSON-Lines file when `source_path`
    is given. Registered under "attack_logs" in app.ai.datasets' registry.
    """

    def __init__(
        self,
        size: int = 1000,
        seed: int = 42,
        class_weights: dict[EventType, float] | None = None,
        source_path: str | Path | None = None,
        validate: bool = True,
    ) -> None:
        self._size = size
        self._seed = seed
        self._class_weights = class_weights
        self._source_path = Path(source_path) if source_path else None
        self._validate = validate
        self._records: list[AttackEventRecord] = []
        self._loaded = False

    def load(self) -> None:
        """Populate records, either from a JSONL file or the synthetic generator."""
        if self._source_path is not None:
            self._records = self._read_jsonl(self._source_path)
        else:
            generator = SyntheticEventGenerator(seed=self._seed)
            self._records = generator.generate(self._size, class_weights=self._class_weights)

        if self._validate:
            report = validate_dataset(self._records)
            if not report.is_valid:
                raise DatasetError(
                    "attack_logs dataset failed validation.",
                    details={
                        "duplicate_event_ids": report.duplicate_event_ids[:10],
                        "semantic_issues": report.semantic_issues[:10],
                        "total_issues": len(report.semantic_issues),
                    },
                )

        self._loaded = True

    def __len__(self) -> int:
        return len(self._records)

    def __getitem__(self, index: int) -> AttackEventRecord:
        if not self._loaded:
            raise DatasetError("AttackLogDataset.load() must be called before access.")
        return self._records[index]

    @property
    def records(self) -> list[AttackEventRecord]:
        """Read-only snapshot of the currently loaded records."""
        return list(self._records)

    @property
    def metadata(self) -> DatasetMetadata:
        """Descriptive summary of the currently loaded dataset."""
        distribution = Counter(r.event_type.value for r in self._records)
        return DatasetMetadata(
            name="attack_logs",
            generated_at=datetime.now(timezone.utc),
            seed=self._seed,
            total_records=len(self._records),
            class_distribution=dict(sorted(distribution.items())),
            description="Synthetic aerospace authentication/network security events.",
        )

    def save_jsonl(self, path: str | Path) -> None:
        """Persist the current records to a JSON-Lines file (one record per line)."""
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            for record in self._records:
                f.write(record.model_dump_json() + "\n")

    @staticmethod
    def _read_jsonl(path: Path) -> list[AttackEventRecord]:
        if not path.exists():
            raise DatasetError(f"Dataset source file not found: {path}")
        records: list[AttackEventRecord] = []
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(AttackEventRecord.model_validate_json(line))
                except Exception as exc:
                    raise DatasetError(
                        f"Malformed record on line {line_no} of {path}: {exc}"
                    ) from exc
        return records
