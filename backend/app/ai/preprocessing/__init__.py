"""
app/ai/preprocessing — Reusable preprocessing pipeline turning
AttackEventRecord data into PyTorch/CUDA-inference-ready tensors.

No machine learning, SentinelX logic, or CUDA code lives here — this
package only prepares data. See pipeline.py's module docstring for the
full stage-by-stage breakdown.
"""

from .categorical_encoding import CategoricalEncoder
from .exceptions import PipelineNotFittedError, PreprocessingError
from .feature_extraction import (
    CATEGORICAL_COLUMNS,
    NUMERIC_COLUMNS,
    FeatureVector,
    extract_batch,
    extract_features,
)
from .feature_validation import (
    FeatureValidationReport,
    validate_feature_batch,
    validate_feature_vector,
    validate_tensor_ready,
)
from .numerical_scaling import FeatureScaler
from .pipeline import PreprocessingPipeline, records_from_dataset
from .rolling_key_features import ROLLING_KEY_FEATURE_NAMES, RollingKeyFeatureEngineer
from .temporal_sequence import SequenceWindow, build_sequences
from .tensor_prep import TensorBatch, build_row

__all__ = [
    "FeatureVector",
    "extract_features",
    "extract_batch",
    "NUMERIC_COLUMNS",
    "CATEGORICAL_COLUMNS",
    "FeatureValidationReport",
    "validate_feature_vector",
    "validate_feature_batch",
    "validate_tensor_ready",
    "CategoricalEncoder",
    "FeatureScaler",
    "ROLLING_KEY_FEATURE_NAMES",
    "RollingKeyFeatureEngineer",
    "SequenceWindow",
    "build_sequences",
    "TensorBatch",
    "build_row",
    "PreprocessingPipeline",
    "records_from_dataset",
    "PreprocessingError",
    "PipelineNotFittedError",
]
