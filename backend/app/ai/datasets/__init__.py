"""app/ai/datasets — dataset loaders for SentinelX model training/inference."""

from .base import BaseDataset
from .generator import DEFAULT_CLASS_WEIGHTS, SyntheticEventGenerator, generate_dataset
from .loader import AttackLogDataset
from .registry import get_dataset, list_datasets, register_dataset
from .schema import AttackEventRecord, DatasetMetadata, DeviceType, EventType, Protocol
from .validators import DatasetValidationReport, validate_dataset, validate_record

__all__ = [
    "BaseDataset",
    "register_dataset",
    "get_dataset",
    "list_datasets",
    "AttackEventRecord",
    "DatasetMetadata",
    "EventType",
    "DeviceType",
    "Protocol",
    "SyntheticEventGenerator",
    "generate_dataset",
    "DEFAULT_CLASS_WEIGHTS",
    "DatasetValidationReport",
    "validate_dataset",
    "validate_record",
    "AttackLogDataset",
]
