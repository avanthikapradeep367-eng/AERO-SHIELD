"""
scripts/train_ai_models.py — Offline training entry point for SentinelX models.

Trains app.ai.models.isolation_forest.IsolationForestModel and
app.ai.models.autoencoder.AutoencoderModel against the *exact* preprocessing
pipeline state app/services/ai_service.py reconstructs at runtime:

    AttackLogDataset(size=500, seed=42) -> PreprocessingPipeline().fit()

This is the same bootstrap dataset/seed _build_sentinelx_engine() uses, so
the fitted scaler statistics and feature width the models are trained
against are identical to what the live service will use to preprocess
requests — no train/serve skew.

Neither model class does its own fitting (see the "no training" notes in
isolation_forest.py / autoencoder.py's module docstrings) — this script is
the offline step those docstrings say is responsible for producing the
artifacts load_weights() reads.

Usage:
    cd backend
    python scripts/train_ai_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_DIR))

import joblib  # noqa: E402
import torch  # noqa: E402
from sklearn.ensemble import IsolationForest  # noqa: E402

from app.ai.datasets import AttackLogDataset  # noqa: E402
from app.ai.models.autoencoder import _DEFAULT_HIDDEN_DIM, _DEFAULT_LATENT_DIM, _build_autoencoder_net  # noqa: E402
from app.ai.preprocessing import PreprocessingPipeline, TensorBatch  # noqa: E402

# Must match app/services/ai_service.py's _build_sentinelx_engine() exactly.
BOOTSTRAP_DATASET_SIZE = 500
BOOTSTRAP_DATASET_SEED = 42

# A larger, independent corpus for actually fitting the models (the
# bootstrap set above only exists to reproduce the serving-time pipeline).
TRAINING_DATASET_SIZE = 5000
TRAINING_DATASET_SEED = 1337

AUTOENCODER_EPOCHS = 150
AUTOENCODER_LR = 1e-3
# Reconstruction-error threshold: the 99th percentile of normal-traffic
# error, so ~1% of normal samples are expected to false-positive.
AUTOENCODER_THRESHOLD_PERCENTILE = 0.99

WEIGHTS_DIR = _BACKEND_DIR / "app" / "ai" / "models" / "weights"


def _classification_metrics(prediction: list[int], labels: list[int]) -> dict[str, float]:
    tp = sum(1 for p, l in zip(prediction, labels) if p == 1 and l == 1)
    fp = sum(1 for p, l in zip(prediction, labels) if p == 1 and l == 0)
    fn = sum(1 for p, l in zip(prediction, labels) if p == 0 and l == 1)
    tn = sum(1 for p, l in zip(prediction, labels) if p == 0 and l == 0)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / len(labels) if labels else 0.0
    return {
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def build_bootstrap_pipeline() -> PreprocessingPipeline:
    """Fit the pipeline the same way _build_sentinelx_engine() does at runtime."""
    dataset = AttackLogDataset(size=BOOTSTRAP_DATASET_SIZE, seed=BOOTSTRAP_DATASET_SEED)
    dataset.load()
    return PreprocessingPipeline().fit(dataset.records)


def build_training_batch(pipeline: PreprocessingPipeline) -> TensorBatch:
    """Transform an independent, larger corpus through the bootstrap-fitted pipeline."""
    dataset = AttackLogDataset(size=TRAINING_DATASET_SIZE, seed=TRAINING_DATASET_SEED)
    dataset.load()
    return pipeline.transform(dataset.records)


def train_isolation_forest(batch: TensorBatch) -> IsolationForest:
    contamination = sum(batch.labels) / len(batch.labels)
    contamination = min(max(contamination, 0.01), 0.5)  # sklearn requires (0, 0.5]
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=TRAINING_DATASET_SEED,
        n_jobs=-1,
    )
    model.fit(batch.rows)
    return model


def evaluate_isolation_forest(model: IsolationForest, batch: TensorBatch) -> dict[str, float]:
    raw_labels = model.predict(batch.rows)  # 1 = inlier, -1 = outlier
    prediction = [1 if int(label) == -1 else 0 for label in raw_labels]
    return _classification_metrics(prediction, batch.labels)


def train_autoencoder(batch: TensorBatch, input_dim: int) -> tuple[object, float]:
    import torch.nn as nn

    torch.manual_seed(TRAINING_DATASET_SEED)

    normal_rows = [row for row, label in zip(batch.rows, batch.labels) if label == 0]
    x_normal = torch.tensor(normal_rows, dtype=torch.float32)

    net = _build_autoencoder_net(input_dim=input_dim, hidden_dim=_DEFAULT_HIDDEN_DIM, latent_dim=_DEFAULT_LATENT_DIM)
    optimizer = torch.optim.Adam(net.parameters(), lr=AUTOENCODER_LR)
    loss_fn = nn.MSELoss()

    net.train()
    for _ in range(AUTOENCODER_EPOCHS):
        optimizer.zero_grad()
        reconstruction = net(x_normal)
        loss = loss_fn(reconstruction, x_normal)
        loss.backward()
        optimizer.step()

    net.eval()
    with torch.inference_mode():
        recon_normal = net(x_normal)
        errors_normal = torch.mean((recon_normal - x_normal) ** 2, dim=1)

    threshold = float(torch.quantile(errors_normal, AUTOENCODER_THRESHOLD_PERCENTILE))
    return net, threshold


def evaluate_autoencoder(net, threshold: float, batch: TensorBatch) -> dict[str, float]:
    x = torch.tensor(batch.rows, dtype=torch.float32)
    with torch.inference_mode():
        reconstruction = net(x)
        errors = torch.mean((reconstruction - x) ** 2, dim=1).tolist()
    prediction = [1 if err > threshold else 0 for err in errors]
    return _classification_metrics(prediction, batch.labels)


def main() -> None:
    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fitting bootstrap preprocessing pipeline (size={BOOTSTRAP_DATASET_SIZE}, seed={BOOTSTRAP_DATASET_SEED})...")
    pipeline = build_bootstrap_pipeline()
    input_dim = len(pipeline.feature_names())
    print(f"  feature width: {input_dim}")

    print(f"Generating training corpus (size={TRAINING_DATASET_SIZE}, seed={TRAINING_DATASET_SEED})...")
    batch = build_training_batch(pipeline)
    n_attack = sum(batch.labels)
    print(f"  {len(batch.rows)} samples -> {n_attack} attack / {len(batch.labels) - n_attack} normal")

    print("\nTraining Isolation Forest...")
    iso_model = train_isolation_forest(batch)
    iso_metrics = evaluate_isolation_forest(iso_model, batch)
    print(f"  training-set metrics: {iso_metrics}")
    iso_path = WEIGHTS_DIR / "isolation_forest.joblib"
    joblib.dump(iso_model, iso_path)
    print(f"  saved -> {iso_path}")

    print("\nTraining Autoencoder...")
    net, threshold = train_autoencoder(batch, input_dim)
    ae_metrics = evaluate_autoencoder(net, threshold, batch)
    print(f"  reconstruction_error_threshold: {threshold:.4f}")
    print(f"  training-set metrics: {ae_metrics}")
    ae_path = WEIGHTS_DIR / "autoencoder.pt"
    torch.save(
        {
            "state_dict": net.state_dict(),
            "input_dim": input_dim,
            "hidden_dim": _DEFAULT_HIDDEN_DIM,
            "latent_dim": _DEFAULT_LATENT_DIM,
            "reconstruction_error_threshold": threshold,
        },
        ae_path,
    )
    print(f"  saved -> {ae_path}")

    print("\nDone.")
    print("app/services/ai_service.py wires up the Isolation Forest model by name")
    print("(app.ai.models.isolation_forest.MODEL_NAME) — set AI_MODEL_WEIGHTS_PATH to:")
    print(f"  {iso_path}")


if __name__ == "__main__":
    main()
