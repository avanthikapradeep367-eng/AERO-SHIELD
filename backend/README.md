# AERO-SHIELD Backend API

FastAPI + PostgreSQL backend for the AERO-SHIELD device management system.

---

## 📁 Project Structure

```
backend/
├── app/
│   ├── __init__.py         # Package marker
│   ├── main.py             # FastAPI app entry point
│   ├── database.py         # SQLAlchemy engine & session
│   ├── models.py           # ORM models (Device table)
│   ├── schemas.py          # Pydantic request/response schemas
│   ├── routes/
│   │   ├── __init__.py
│   │   └── auth.py         # Device API endpoints
│   └── utils/              # Utility helpers (future use)
├── .env                    # Environment variables (never commit!)
├── requirements.txt        # Python dependencies
└── README.md
```

---

## ⚙️ Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11+ |
| PostgreSQL | 14+ |

---

## 🚀 Setup & Installation

### 1. Clone / navigate to the backend folder

```bash
cd AERO-SHIELD/backend
```

### 2. Create a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Edit `.env` and update the `DATABASE_URL` with your PostgreSQL credentials:

```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/aeroshield_db
```

### 5. Create the PostgreSQL database

```sql
CREATE DATABASE aeroshield_db;
```

> The application will **automatically create the `devices` table** on first startup — no manual migration needed.

### 6. Run the server

```bash
uvicorn app.main:app --reload
```

Server will start at: **http://127.0.0.1:8000**

---

## 📖 API Documentation

| URL | Description |
|---|---|
| http://127.0.0.1:8000/docs | Interactive Swagger UI |
| http://127.0.0.1:8000/redoc | ReDoc documentation |
| http://127.0.0.1:8000/openapi.json | Raw OpenAPI schema |

---

## 🔌 API Endpoints

### `GET /` — Health Check
```json
{
  "service": "AERO-SHIELD API",
  "version": "1.0.0",
  "status": "operational",
  "docs": "/docs"
}
```

---

### `POST /api/v1/register-device` — Register a Device

**Request Body:**
```json
{
  "device_id": "SHIELD-001",
  "device_name": "Sensor Unit Alpha",
  "status": "active"
}
```

**Response `201 Created`:**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "device_id": "SHIELD-001",
  "device_name": "Sensor Unit Alpha",
  "status": "active",
  "created_at": "2026-06-11T06:30:00Z"
}
```

**Response `409 Conflict` (duplicate device_id):**
```json
{
  "detail": "Device with ID 'SHIELD-001' is already registered."
}
```

---

### `GET /api/v1/device/{device_id}` — Get Device by ID

**Example:** `GET /api/v1/device/SHIELD-001`

**Response `200 OK`:**
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "device_id": "SHIELD-001",
  "device_name": "Sensor Unit Alpha",
  "status": "active",
  "created_at": "2026-06-11T06:30:00Z"
}
```

**Response `404 Not Found`:**
```json
{
  "detail": "Device with ID 'SHIELD-999' was not found."
}
```

---

## 🧪 Sample curl Commands

```bash
# Register a device
curl -X POST http://127.0.0.1:8000/api/v1/register-device \
  -H "Content-Type: application/json" \
  -d '{"device_id": "SHIELD-001", "device_name": "Sensor Unit Alpha", "status": "active"}'

# Look up a device
curl http://127.0.0.1:8000/api/v1/device/SHIELD-001
```

---

## 🗄️ Database Schema

```sql
CREATE TABLE devices (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    device_id   VARCHAR(100) UNIQUE NOT NULL,
    device_name VARCHAR(200) NOT NULL,
    status      VARCHAR(50)  NOT NULL DEFAULT 'active',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

---

## ✅ Status Values

| Value | Description |
|---|---|
| `active` | Device is online and operational |
| `inactive` | Device is offline or decommissioned |
| `maintenance` | Device is undergoing maintenance |

---

## 🧠 Member 3 — SentinelX AI Module (`app/ai/`)

### Overview

SentinelX is the CUDA-ready threat-detection engine that backs `app.services.ai_service.AIService`. It analyzes aerospace device authentication/network telemetry (rolling-key state, request rate, RF signal quality, etc.) and produces a structured verdict, attack classification, and response recommendation for each event. It replaces the original mocked `AIService` implementation while preserving the existing `IAIService` contract exactly — no routes, schemas, or interfaces outside `app/ai/` were changed to enable this integration.

### Architecture

SentinelX is a strictly layered pipeline. Each layer only depends on the layer directly beneath it — there are no circular imports and no layer reaches past its neighbor:

```
datasets  →  preprocessing  →  models  →  inference  →  sentinelx
(synthetic     (feature        (Isolation    (orchestrates    (InvestigationAgent →
 telemetry +    engineering,     Forest /      preprocess →     AttackClassifier →
 schema)        scaling,         Autoencoder)  predict)         ResponseAgent)
                tensor prep)
```

`app.services.ai_service.AIService` sits outside `app/ai/` and is the only integration point: it builds a process-wide `SentinelXEngine`, translates `SentinelXAnalysis` into the existing `AIAnalysisResult`/`AIStatusResult` response shapes, and raises the existing `AIUnavailableError` / `AIAnalysisError` / `AIInvalidInputError` HTTP exceptions rather than fabricating results when no trained model is deployed.

### Folder Structure

```
app/ai/
├── __init__.py             # Package facade (AIConfig, exceptions, SentinelXEngine)
├── config.py                # AIConfig / load_config() (env var loading)
├── exceptions.py             # AIBaseError hierarchy (DatasetError, ModelLoadError, InferenceError, CUDAUnavailableError)
├── datasets/
│   ├── base.py                 # BaseDataset ABC
│   ├── schema.py                # AttackEventRecord, EventType, DeviceType, Protocol
│   ├── generator.py              # SyntheticEventGenerator (7 event categories)
│   ├── validators.py              # Dataset-level structural/semantic validation
│   ├── loader.py                   # AttackLogDataset ("attack_logs")
│   └── registry.py                  # register_dataset / get_dataset / list_datasets
├── preprocessing/
│   ├── feature_extraction.py        # AttackEventRecord -> FeatureVector
│   ├── feature_validation.py         # NaN/Inf/shape validation
│   ├── categorical_encoding.py        # Fixed-vocabulary one-hot encoding
│   ├── numerical_scaling.py            # Standard/min-max scaling
│   ├── rolling_key_features.py          # Device-history-aware key features
│   ├── temporal_sequence.py              # Per-device sliding windows
│   ├── tensor_prep.py                     # TensorBatch (model-input-ready rows)
│   ├── pipeline.py                         # PreprocessingPipeline (fit/transform)
│   └── tests/test_preprocessing.py         # 51 unit tests (stdlib unittest)
├── models/
│   ├── base.py                # BaseModel ABC (load_weights/to_device/predict)
│   ├── registry.py              # register_model / get_model / list_models
│   ├── model_manager.py           # ModelManager (load/unload/get lifecycle)
│   ├── isolation_forest.py          # IsolationForestModel (scikit-learn)
│   └── autoencoder.py                # AutoencoderModel (PyTorch)
├── inference/
│   └── engine.py                # InferenceEngine (preprocess -> predict orchestration)
├── sentinelx/
│   ├── engine.py                 # SentinelXEngine (top-level orchestrator)
│   ├── investigator.py             # InvestigationAgent (verdict + severity triage)
│   ├── classifier.py                 # AttackClassifier (rule-based sub-categorization)
│   └── response_agent.py               # ResponseAgent (action + priority recommendation)
└── utils/
    └── device.py               # get_device / is_cuda_available / device_summary
```

### Features

- Deterministic synthetic dataset generation across 7 categories: Normal, Replay Attack, Brute Force, Spoofing, DoS, Invalid Rolling Key, Abnormal Device Behavior.
- Full preprocessing pipeline: feature extraction, structural validation, categorical one-hot encoding, numeric scaling, device-history-aware rolling-key features, temporal windowing, and flat tensor-ready output.
- A model registry + lifecycle manager (`ModelManager`) decoupled from the class-level model registry (`registry.py`), so models can be loaded/unloaded/swapped independently of what types exist.
- Two fully interchangeable anomaly-detection models — swapping one for the other requires **zero** changes to `InferenceEngine` or `SentinelXEngine`.
- A 4-stage analysis pipeline (`InferenceEngine → InvestigationAgent → AttackClassifier → ResponseAgent`) producing verdict, severity, attack category, recommended action, and priority — with **no automated response execution** (recommendations only).
- Automatic CUDA detection with guaranteed CPU fallback; all PyTorch/scikit-learn imports are lazy, so `app/ai/` imports cleanly even on a machine with neither installed.
- Drop-in integration into the existing `AIService`/`IAIService` contract — verified against the existing `SimulationService` → `BlockchainService` → `RollingKeyService` chain with zero changes to any of those files.

### AI Pipeline

```
AttackEventRecord(s) / AttackLogDataset
    → PreprocessingPipeline.transform()   (already fitted; never refit at inference time)
    → TensorBatch                          (flat, scaled, one-hot-encoded rows)
    → ModelManager.get(model_name)         (already loaded; never loaded implicitly)
    → BaseModel.predict(TensorBatch)
    → InferenceResult                      (prediction, confidence, metadata, execution info)
```

`InferenceEngine` is model-agnostic by *contract*, not by type-checking: it never imports a concrete model class. Any `BaseModel.predict()` implementation just needs to return an object exposing `.prediction` (list[int]), `.confidence` (list[float]), and `.metadata` (dict) — both `IsolationForestModel` and `AutoencoderModel` satisfy this identically.

### SentinelX Workflow

```
InferenceResult
    → InvestigationAgent.investigate()   → InvestigationReport   (ATTACK/NORMAL verdict + severity tier)
    → AttackClassifier.classify()        → ClassificationReport  (specific attack category + reasoning)
    → ResponseAgent.recommend()          → ResponseReport        (recommended action + priority — NOT executed)
```

`SentinelXEngine.analyze()` / `.analyze_single()` run all three stages and return one `SentinelXAnalysis` bundling `inference_result`, `investigation_report`, `classification_report`, and `response_report`. Category → action mapping is fixed:

| Attack Category | Recommended Action |
|---|---|
| Normal | Monitor |
| Replay Attack | Rotate Key |
| Brute Force | Block Device |
| Spoofing | Blacklist Device |
| DoS | Rate Limit |
| Invalid Rolling Key | Force Re-authentication |
| Abnormal Device Behavior | Alert + Monitor |
| Unknown | Manual Investigation |

### Isolation Forest Model

`app/ai/models/isolation_forest.py` — an unsupervised anomaly detector backed by `sklearn.ensemble.IsolationForest`. `load_weights(path)` deserializes a **pre-trained** estimator via `joblib.load()` — no training happens in this codebase. scikit-learn/joblib are imported lazily inside `load_weights()`/`predict()` only.

```python
# offline training step (NOT part of this repo) produces the artifact:
from sklearn.ensemble import IsolationForest
import joblib

model = IsolationForest(contamination=0.1, n_estimators=100).fit(training_rows)
joblib.dump(model, "isolation_forest.joblib")
```

### Autoencoder Model

`app/ai/models/autoencoder.py` — a reconstruction-error-based anomaly detector backed by a small feed-forward PyTorch network (`Linear → ReLU` encoder/decoder). A sample the network reconstructs poorly (high MSE relative to a calibrated threshold) is flagged as anomalous. PyTorch is imported lazily, and the `nn.Module` architecture class itself is defined *inside* a function so merely importing this file never triggers `import torch`.

```python
# offline training step (NOT part of this repo) produces the checkpoint:
torch.save({
    "state_dict": model.state_dict(),
    "input_dim": <int>,                          # required
    "hidden_dim": <int>,                          # optional, default 16
    "latent_dim": <int>,                          # optional, default 8
    "reconstruction_error_threshold": <float>,     # optional, default 1.0
}, "autoencoder.pt")
```

### CUDA Support

`app/ai/utils/device.py` provides `get_device("cpu" | "cuda" | "auto")` and `is_cuda_available()`, used by both models and by `SentinelXEngine.status()`. `AutoencoderModel` auto-detects the best device at construction time and moves both the model and every input tensor to it as a single batched transfer (never per-row); inference runs inside `torch.inference_mode()` for reduced overhead on the hot prediction path.

### CPU Fallback

Every device-resolution path falls back to `"cpu"` automatically whenever CUDA — or PyTorch itself — is unavailable, so the entire `app/ai/` package imports and runs cleanly on a CPU-only machine with no PyTorch/scikit-learn installed at all (only `load_weights()`/`predict()` on a specific model require the corresponding library, and only when actually called).

### Dependencies

Already pinned in `requirements.txt`:

| Package | Purpose |
|---|---|
| `fastapi` | Web framework (existing) |
| `uvicorn` | ASGI server (existing) |
| `pydantic` | Schema validation (existing; also used by `app/ai/datasets/schema.py`) |

**Not yet in `requirements.txt`** — required to actually load/run trained models (the AI module imports these lazily, so the rest of the backend runs fine without them; they're only needed when `AI_MODEL_WEIGHTS_PATH` points to a real model):

| Package | Purpose |
|---|---|
| `torch` | PyTorch — required for `AutoencoderModel` |
| `torchvision` | PyTorch companion library (standard install alongside `torch`) |
| `torchaudio` | PyTorch companion library (standard install alongside `torch`) |
| `scikit-learn` | Required for `IsolationForestModel` |
| `joblib` | Required to deserialize `IsolationForestModel` checkpoints (installed automatically with `scikit-learn`, listed explicitly for clarity) |

### Installation Steps

```bash
# 1. Activate your virtual environment first (see Setup & Installation above)

# 2. Install the existing backend dependencies (if not already installed)
pip install -r requirements.txt

# 3. Install the AI module's dependencies
```

**CPU-only (Windows and Linux — identical command):**

```bash
pip install torch torchvision torchaudio
pip install scikit-learn joblib
```

**CUDA-enabled PyTorch (optional — only if you have an NVIDIA GPU + CUDA toolkit installed):**

```bash
# Windows (PowerShell / cmd)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Linux
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

> Replace `cu121` with the wheel index matching your installed CUDA toolkit version — check [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/) for the current index for your CUDA version. If in doubt, install the CPU-only build above; every model in this module falls back to CPU automatically.

Verify the install:

```bash
python -c "import torch; print(torch.__version__, 'CUDA:', torch.cuda.is_available())"
python -c "import sklearn; print(sklearn.__version__)"
```

### Environment Variables

Read by `app/services/ai_service.py` at process startup (first request):

| Variable | Default | Description |
|---|---|---|
| `AI_MODEL_WEIGHTS_PATH` | *(unset)* | Path to a trained model checkpoint (`.joblib` for Isolation Forest, `.pt` for Autoencoder). If unset, the model stays unloaded and `analyze_request()` returns `503 Service Unavailable`. |
| `AI_DEVICE` | `cpu` | `"cpu"`, `"cuda"`, or `"auto"` — passed to `InferenceEngine.load_model()`. |

> `app/ai/config.py` also declares `AI_MODEL_DIR`, `AI_BATCH_SIZE`, and `AI_CONFIDENCE_THRESHOLD` via `AIConfig`/`load_config()`, but these are **not currently consumed** by `ai_service.py` — reserved for future use (see *Current Limitations* below).

### Running the Backend

```bash
uvicorn app.main:app --reload
```

The AI module initializes lazily on the **first** call to `AIService()` (e.g. the first `POST /api/v1/simulate-attack` request) — it is not built at server startup, so a missing `AI_MODEL_WEIGHTS_PATH` does not prevent the rest of the API from starting.

### Running AIService

`AIService` requires no code changes to use — it's already wired into `routes/simulation.py` via the existing `get_ai_service()` dependency. To make it fully operational (real, non-503 results):

```bash
# Windows (PowerShell)
$env:AI_MODEL_WEIGHTS_PATH = "C:\path\to\isolation_forest.joblib"
$env:AI_DEVICE = "auto"
uvicorn app.main:app --reload

# Linux
export AI_MODEL_WEIGHTS_PATH=/path/to/isolation_forest.joblib
export AI_DEVICE=auto
uvicorn app.main:app --reload
```

Without `AI_MODEL_WEIGHTS_PATH` set, `POST /api/v1/simulate-attack` still responds — `AIService.analyze_request()` raises `AIUnavailableError`, which the existing exception handler in `app/main.py` turns into a `503` response, exactly as documented on that route.

### Testing the AI Pipeline

The preprocessing layer has a full automated unit test suite (stdlib `unittest`, no extra test dependency):

```bash
# Windows and Linux — identical command
cd backend
python -m unittest discover -s app/ai/preprocessing/tests -p "test_*.py" -v
```

For the dataset/model/inference/SentinelX layers, verify interactively:

```bash
python -c "
from app.ai.datasets import AttackLogDataset
from app.ai.preprocessing import PreprocessingPipeline
from app.ai.models import ModelManager
from app.ai.inference import InferenceEngine
from app.ai.sentinelx import SentinelXEngine

ds = AttackLogDataset(size=200, seed=42)
ds.load()
pipeline = PreprocessingPipeline().fit(ds.records)

manager = ModelManager()
inference = InferenceEngine(model_name='isolation_forest', pipeline=pipeline, model_manager=manager)
inference.load_model(weights_path='path/to/isolation_forest.joblib', device='auto')

engine = SentinelXEngine(inference=inference)
analysis = engine.analyze(ds.records[:10])
print(analysis.response_report.action_counts)
"
```

### Current Limitations

- **No trained model weights ship with this repository.** `AIService` reports `503 Service Unavailable` until `AI_MODEL_WEIGHTS_PATH` points to a real, offline-trained artifact.
- **`torch`/`scikit-learn`/`joblib` are not yet in `requirements.txt`** — see *Dependencies* above; install manually until this is finalized.
- **`AIService` currently hardcodes `model_name="isolation_forest"`** — `AutoencoderModel` is fully built, tested, and interchangeable, but selecting it in production requires editing `app/services/ai_service.py` (no `AI_MODEL_NAME` environment variable yet).
- **`AttackClassifier` is a rule-based heuristic**, not a trained multi-class model — it maps signal patterns to attack categories using fixed domain rules, not learned weights.
- **No persisted `PreprocessingPipeline` state** — scaler/encoder statistics are refit on a synthetic bootstrap dataset every process start, rather than loaded from a file saved alongside the trained model.
- **No dedicated "incident" interface yet for Member 2's `BlockchainService`** — `device_id`, attack category, risk score, and confidence exist across `SentinelXAnalysis`'s nested reports, but there's no single flat record shaped for `IBlockchainService.log_attack()`, and nothing computes an `evidence_hash`.
- Only the preprocessing layer has an automated test suite; datasets/models/inference/sentinelx are covered by manual verification scripts run during development, not checked-in tests.

### Future Work

- Ship a real trained Isolation Forest and/or Autoencoder checkpoint, and add `torch`/`scikit-learn`/`joblib` to `requirements.txt`.
- Add an `AI_MODEL_NAME` environment variable so `AIService` can select between `isolation_forest` and `autoencoder` (or a future model) without a code change.
- Replace `AttackClassifier`'s rule engine with a trained supervised multi-class model once labeled production data exists.
- Persist `PreprocessingPipeline.to_dict()` alongside model weights and load both together at startup, instead of refitting on synthetic data.
- Add an `IncidentRecord` dataclass (and a `SentinelXAnalysis.to_incident_records()` helper) in `app/ai/sentinelx/` that maps directly onto `IBlockchainService.log_attack()`'s parameters, including a real `evidence_hash`.
- Expand automated test coverage to `datasets/`, `models/`, `inference/`, and `sentinelx/` (currently only `preprocessing/` has a checked-in test suite).
- Add CI-friendly GPU/CPU test matrix and document a production CUDA deployment configuration (driver/toolkit version pinning).

---

## 🛠️ Backend Setup & Troubleshooting

### Python Version Requirement

**Python 3.12 is recommended.** Python 3.13/3.14 are **not** currently supported for this backend:

| Python Version | Status |
|---|---|
| 3.12.x | ✅ Recommended |
| 3.11.x | ✅ Supported (minimum) |
| 3.14.x | ❌ Known to fail — see below |

On Python 3.14, `pip install -r requirements.txt` fails to build **`pydantic-core`** and **`psycopg2-binary`**, because the pinned versions in `requirements.txt` have no prebuilt wheel for 3.14 yet and fall back to compiling from source. `pydantic-core` in particular requires a full Rust toolchain **and** the MSVC linker (Visual Studio C++ Build Tools) to compile on Windows — without both installed, the build fails with an error like:

```
error: linking with `link.exe` failed: exit code: 1
error: could not compile `pydantic-core` ... due to previous error
ERROR: Failed building wheel for pydantic-core
Failed to build psycopg2-binary pydantic-core
```

**Fix:** install Python 3.12 (or 3.11) and create your virtual environment with that interpreter instead of the system default. Check your active version first:

```powershell
python --version
```

If it reports `3.13` or `3.14`, install Python 3.12 from [python.org/downloads](https://www.python.org/downloads/) (or via `winget install Python.Python.3.12`), then create the virtual environment explicitly with it:

```powershell
py -3.12 -m venv venv
```

### Virtual Environment (Windows)

```powershell
# Create the virtual environment (use py -3.12 if multiple Python versions are installed)
python -m venv venv

# Activate it
venv\Scripts\activate

# Confirm the interpreter in use is the one inside venv\
python --version
where python
```

> Linux/macOS equivalent: `python3.12 -m venv venv && source venv/bin/activate`

### Installing Dependencies

```powershell
cd AERO-SHIELD\backend
venv\Scripts\activate
pip install -r requirements.txt
```

### Additional AI Dependencies (if not already installed)

The SentinelX AI module (see *Member 3 — SentinelX AI Module* above) needs a few packages not yet pinned in `requirements.txt`. Install them if `import torch` / `import sklearn` fails:

```powershell
pip install torch torchvision torchaudio
pip install scikit-learn joblib
```

> Linux equivalent: identical commands — `pip install torch torchvision torchaudio` and `pip install scikit-learn joblib`.

### Running the FastAPI Backend

```powershell
uvicorn app.main:app --reload
```

Server starts at **http://127.0.0.1:8000** (Swagger UI at `/docs`).

### Common Startup Issue: `password authentication failed for user "postgres"`

If the server fails to start (or a database-backed route fails) with an error like:

```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) FATAL: password authentication failed for user "postgres"
```

**This is caused by incorrect PostgreSQL credentials or local database configuration — it is unrelated to the AI module.** The AI module (`app/ai/`) does not touch the database at all; this error comes entirely from `app/database.py`'s connection to PostgreSQL via the `DATABASE_URL` environment variable.

The project expects `DATABASE_URL` to be configured in the **root** `.env` file — `AERO-SHIELD/.env` (one level above `backend/`), **not** `backend/.env`:

```env
# AERO-SHIELD/.env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/aeroshield_db
```

`app/database.py` calls `load_dotenv()` (via `python-dotenv`), which searches upward from the current working directory for a `.env` file — so this only works correctly if you run `uvicorn` from inside `backend/` with the root `.env` present one directory above it.

### Troubleshooting Steps

**1. Verify the PostgreSQL service is running**

```powershell
# Windows — check the service status
Get-Service -Name postgresql*

# Start it if it's stopped
Start-Service -Name postgresql-x64-14   # adjust the service name to match your installed version
```

```bash
# Linux
sudo systemctl status postgresql
sudo systemctl start postgresql
```

**2. Verify `psql` connectivity with the same credentials as `DATABASE_URL`**

```powershell
psql -U postgres -h localhost -p 5432 -d aeroshield_db
```

- If this prompts for a password and rejects it → the password in `DATABASE_URL` does not match the actual PostgreSQL user password. Reset it if needed:
  ```sql
  ALTER USER postgres WITH PASSWORD 'yourpassword';
  ```
- If this fails with `database "aeroshield_db" does not exist` → create it:
  ```sql
  CREATE DATABASE aeroshield_db;
  ```
- If this fails to connect at all (`connection refused`) → PostgreSQL isn't running or isn't listening on that port — revisit step 1.

**3. Verify `DATABASE_URL` is actually being loaded**

```powershell
cd AERO-SHIELD\backend
venv\Scripts\activate
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print(os.getenv('DATABASE_URL'))"
```

- If this prints `None` → the root `.env` file is missing, misnamed, or not where `python-dotenv` expects it (confirm you're running this from inside `backend/`, with `.env` present at `AERO-SHIELD/.env`).
- If it prints a URL but the credentials are wrong → edit `AERO-SHIELD/.env` and correct the `DATABASE_URL` value, then restart `uvicorn`.

**4. Verify Python version compatibility**

```powershell
python --version
pip show pydantic-core psycopg2-binary 2>$null
```

- If `python --version` reports `3.13` or `3.14` and `pip show` fails to find either package (or `pip install -r requirements.txt` errored earlier) → recreate the virtual environment with Python 3.12 as described above.
