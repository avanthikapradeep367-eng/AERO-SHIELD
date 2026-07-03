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
python -m uvicorn app.main:app --reload
```

> Use `python -m uvicorn` (not just `uvicorn`) — this ensures the command works
> regardless of whether uvicorn's script is in the virtual environment's PATH.

Server will start at: **http://127.0.0.1:8000**

> **PostgreSQL is optional for startup.** The server starts even without a database
> connection — only endpoints that read/write devices will return 503 until PostgreSQL
> is running. All blockchain endpoints work independently of the database.

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

## Blockchain Integration Layer

The `app/blockchain/` package provides a zero-knowledge Python interface to the
**EvidenceVault** smart contract deployed on the private Ganache Ethereum network.
Member 1 (Rolling Key Authentication) and Member 3 (SentinelX AI) use this
layer — no Solidity or blockchain knowledge is required.

### Prerequisites

| Requirement | Version |
|---|---|
| Ganache GUI | Latest |
| Node.js | 18+ |
| web3 (Python) | 7.x |

### Step 1 — Start Ganache

Open the **Ganache GUI** application and click **Quickstart Ethereum**.

Ganache will start on `http://127.0.0.1:7545` with Chain ID `1337`.

> Ganache must be running any time the blockchain services are used.

### Step 2 — Deploy the Smart Contract

In a separate terminal, from the project root:

```bash
cd blockchain
npm install
npm run deploy:ganache
```

Expected output:
```
DEPLOYMENT SUCCESSFUL
  Contract : 0x9A7E925E3c93D5c11052037246e2002385A6AeE8
  Version  : AERO-SHIELD-X:EvidenceVault:v2.0.0-phase2
```

### Step 3 — Install Web3.py

```bash
# From the backend/ directory (activate your venv first)
pip install -r requirements.txt
```

The `requirements.txt` already includes `web3>=6.0.0`.

### Step 4 — Configure backend/.env

The `.env` file already contains the correct values matched to the deployed
contract. No changes are needed if you are using the same Ganache instance.

```env
GANACHE_RPC_URL=http://127.0.0.1:7545
PRIVATE_KEY=0x4383686cee49b1020f1e8f4de187454dfb27c82c14d5d1f81377f6107addc58c
WALLET_ADDRESS=0x009DD4C18D28Fa147306adc2bf698579607ea20b
CHAIN_ID=1337
CONTRACT_ADDRESS=0x9A7E925E3c93D5c11052037246e2002385A6AeE8
```

> If you redeploy the contract (e.g. after resetting Ganache), update
> `CONTRACT_ADDRESS` with the new address from
> `blockchain/deployment/EvidenceVault.json`.

### Step 5 — Verify the Connection

Run this one-liner from the `backend/` directory to confirm everything is wired up:

```bash
python -c "
from dotenv import load_dotenv; load_dotenv('.env')
from app.blockchain import BlockchainService
svc = BlockchainService()
print(svc.verify_connection())
"
```

Expected output:
```json
{
  "connected": true,
  "rpc_url": "http://127.0.0.1:7545",
  "chain_id": 1337,
  "block_number": 7,
  "contract_address": "0x9A7E925E3c93D5c11052037246e2002385A6AeE8",
  "wallet_address": "0x009DD4C18D28Fa147306adc2bf698579607ea20b",
  "wallet_balance": "99.982... ETH"
}
```

### Quick-Start Code Examples

#### Module 1 — Register a Device

```python
from dotenv import load_dotenv; load_dotenv('.env')
from app.blockchain import DeviceService

svc = DeviceService()

# Register a new device
result = svc.register_device("UAV-ALPHA-001", "UAV", "0x04abcdef...")
print("TX hash:", result.tx_hash)
print("Gas used:", result.gas_used)

# Read it back
device = svc.get_device("UAV-ALPHA-001")
print(device.device_id, device.device_type, device.active)

# List all devices
print(svc.get_registered_devices())   # ["UAV-ALPHA-001"]
print(svc.total_devices())            # 1

# Deactivate a device
svc.update_device_status("UAV-ALPHA-001", active=False)
```

#### Module 2 — Record Authentication (Member 1)

```python
from dotenv import load_dotenv; load_dotenv('.env')
from app.blockchain import AuthenticationService

svc = AuthenticationService()

# Record a successful rolling-key authentication
result = svc.record_authentication(
    auth_id="0xabc123" + "0" * 58,     # unique 32-byte hex ID
    device_id="UAV-ALPHA-001",          # Module 1 string ID
    key_version=1,                       # rolling key generation number
    success=True,
    session_id="0xdef456" + "0" * 58,  # session identifier
)
print("TX hash:", result.tx_hash)

# Get authentication history for a device
history = svc.get_authentication_history("UAV-ALPHA-001")
print(history)    # ["0xabc123..."]

print("Total auth events:", svc.total_authentications())
```

#### Module 3 — Record Incident (Member 3 / SentinelX AI)

```python
from dotenv import load_dotenv; load_dotenv('.env')
from app.blockchain import EvidenceService

svc = EvidenceService()

evidence_hash = "0x" + "a1b2c3d4" * 8   # SHA-256 of evidence file

result = svc.record_incident(
    incident_id="0x" + "11" * 32,
    attack_type="GPS_SPOOFING",
    source_device="UAV-ALPHA-001",
    target_device="GCS-GROUND-001",
    risk_score=87,
    ai_confidence=94,
    action_taken="QUARANTINE_ISSUED",
    evidence_hash=evidence_hash,
)
print("TX hash:", result.tx_hash)

# Verify the evidence file has not been tampered with
svc.verify_evidence("0x" + "11" * 32, evidence_hash)   # True or raises EvidenceTamperingError

print("Total incidents:", svc.total_incidents())
```

#### Module 4 — Threat Intelligence (Member 3 / SentinelX AI)

```python
from dotenv import load_dotenv; load_dotenv('.env')
from app.blockchain import ThreatService

svc = ThreatService()

# SentinelX AI detects a threat — publish to blockchain
svc.blacklist_device("UAV-ALPHA-001", threat_level=8, risk_score=95)

# Check if a device is blacklisted (for rapid IOC lookup)
print(svc.is_blacklisted("UAV-ALPHA-001"))   # True

# Get the full threat profile
profile = svc.get_threat_profile("UAV-ALPHA-001")
print(profile.threat_level, profile.risk_score, profile.blacklisted)

# Update with refined intelligence
svc.update_threat_profile("UAV-ALPHA-001", threat_level=9, attack_count=3, risk_score=98)

# Remove from blacklist when cleared
svc.remove_blacklist("UAV-ALPHA-001")
```

### Folder Structure

```
app/blockchain/
├── __init__.py              # Public API — import from here
├── config.py                # Env var loading → BlockchainConfig
├── web3_client.py           # Singleton Web3 + signing account
├── contract_loader.py       # ABI + deployment JSON reader
├── blockchain_service.py    # Core: send_transaction, call_function, logging
├── exceptions.py            # All custom exceptions
├── utils.py                 # Type converters (bytes32, timestamps, gas)
├── services/
│   ├── device_service.py          # Module 1 — Device Registry
│   ├── authentication_service.py  # Module 2 — Auth Ledger (Member 1)
│   ├── evidence_service.py        # Module 3 — Evidence Vault (Member 3)
│   └── threat_service.py          # Module 4 — Threat Intelligence (Member 3)
├── abi/                     # Optional local ABI copy (auto-discovered if absent)
└── deployment/              # Optional local deployment copy (auto-discovered if absent)
```

### Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `BlockchainConnectionError: Web3.is_connected() returned False` | Ganache is not running | Open Ganache GUI and start a workspace |
| `ContractNotFoundError: EvidenceVault ABI not found` | Contract not deployed yet | Run `npm run deploy:ganache` in `blockchain/` |
| `Chain ID mismatch` | Ganache has a different chain ID | Set Ganache to Chain ID 1337 in its settings |
| `GasEstimationError` | Transaction would revert (e.g. duplicate ID, invalid score) | Check input values match the Solidity `require()` constraints |
| `DeviceNotFoundError` | Device ID does not exist on-chain | Register it first with `register_device()` |
| `EvidenceTamperingError` | Evidence file hash does not match on-chain record | The file has been modified after submission |

---

## 🏗️ Project Architecture Overview (Member 1 + Member 2 + Member 3)

AERO-SHIELD's backend is composed of three independently owned layers that meet at well-defined interface boundaries — each member's code can be developed, tested, and swapped without the others changing:

```
                        ┌─────────────────────────────┐
                        │   FastAPI routes/ (HTTP)     │
                        │  routes/simulation.py, etc.  │
                        └───────────────┬───────────────┘
                                        │  Depends()
                        ┌───────────────▼───────────────┐
                        │   SimulationService             │
                        │  (business orchestration)       │
                        └─────┬───────────────────┬───────┘
                              │                    │
              IAIService ─────┘                    └───── IBlockchainService
           (interfaces/ai_interface.py)         (interfaces/blockchain_interface.py)
                    │                                        │
   ┌────────────────▼────────────────┐      ┌────────────────▼────────────────┐
   │  Member 1 — AIService            │      │  Member 1 — BlockchainService    │
   │  services/ai_service.py          │      │  services/blockchain_service.py  │
   │  (interface/adapter layer;       │      │  (mock/interface layer, unless   │
   │   now delegates to Member 3)     │      │   Member 2's app/blockchain/     │
   │                                  │      │   is wired in)                  │
   └────────────────┬─────────────────┘      └────────────────┬────────────────┘
                    │                                          │
   ┌────────────────▼─────────────────┐      ┌─────────────────▼────────────────┐
   │  Member 3 — SentinelX AI Engine   │      │  Member 2 — Blockchain Layer      │
   │  app/ai/  (datasets →             │      │  app/blockchain/ (EvidenceVault   │
   │  preprocessing → models →         │      │  smart contract via Web3.py)      │
   │  inference → sentinelx)           │      │                                   │
   └───────────────────────────────────┘      └───────────────────────────────────┘
```

**How a request flows end-to-end** (`POST /api/v1/simulate-attack`):

1. The route delegates to `SimulationService.process_attack()` — no business logic in the route itself.
2. `SimulationService` calls `IAIService.analyze_request()` — implemented today by Member 1's `AIService`, which now internally delegates to Member 3's `SentinelXEngine` (see *AI Module (SentinelX)* below) instead of returning mocked data.
3. If the resulting `risk_score` exceeds the high-risk threshold, `SimulationService` calls `IBlockchainService.log_attack()` (Member 2's contract-backed implementation, or Member 1's mock until it's wired in) and rotates the device's rolling key.
4. A single `AttackResponse` is returned to the caller, combining the AI verdict and the automated response outcome.

Because every boundary is an abstract interface (`IAIService`, `IBlockchainService`) or a duck-typed contract (`BaseModel.predict()`), each member's layer was built, tested, and swapped in independently — Member 3's entire SentinelX engine was implemented and verified without ever touching a route, schema, or interface file.

---

## 🧠 AI Module (SentinelX)

Member 3's contribution replaces the original mocked `AIService` with a real, CUDA-ready threat-detection pipeline, while preserving the `IAIService` contract byte-for-byte (same method signatures, same response shapes).

### Synthetic Dataset Generation

`app/ai/datasets/generator.py`'s `SyntheticEventGenerator` produces deterministic, seeded `AttackEventRecord` samples across 7 categories — Normal traffic, Replay Attack, Brute Force, Spoofing, DoS, Invalid Rolling Key, and Abnormal Device Behavior — each with realistic, category-specific value ranges (request rate, rolling-key validity, packet loss, RF signal strength, etc.). `AttackLogDataset` (registered as `"attack_logs"` in the dataset registry) wraps the generator behind the standard `BaseDataset` interface (`load()` / `__len__()` / `__getitem__()`), with built-in structural and semantic validation (`app/ai/datasets/validators.py`) — duplicate-ID checks, future-timestamp checks, and label-consistency checks.

### Preprocessing Pipeline

`app/ai/preprocessing/pipeline.py`'s `PreprocessingPipeline` turns raw `AttackEventRecord`s into model-ready tensors in one fit-once/transform-many object: extract → validate → enrich (rolling-key history features) → encode (categorical one-hot) → scale (numeric standardization) → flatten into a `TensorBatch`. Scaler/encoder statistics are computed once via `.fit()` and reused unchanged on every subsequent `.transform()` call — exactly mirroring how a production model must never re-fit on live traffic.

### Feature Engineering

- **Base features** (`feature_extraction.py`): request rate, payload size, session duration, packet loss, RF signal strength (+ a missing-value flag), rolling-key version/validity, auth success, ports, and a stable hashed bucket of the source IP. `severity_hint` is deliberately excluded — it's assigned by the generator *from* the label, so including it would leak the answer.
- **Rolling-key features** (`rolling_key_features.py`): device-history-aware signals — version delta from the last seen key, whether a version was reused (replay signature), and a running count of consecutive invalid keys (brute-force signature) — computed deterministically regardless of input order.
- **Temporal sequencing** (`temporal_sequence.py`): per-device sliding windows for future sequence-model architectures.
- **Categorical encoding / numerical scaling**: fixed-vocabulary one-hot encoding (built from the schema's `Enum`s, not fit from data) and standard/min-max scaling, both independently serializable via `to_dict()`/`from_dict()`.

### Isolation Forest Model

`app/ai/models/isolation_forest.py`'s `IsolationForestModel` wraps `sklearn.ensemble.IsolationForest` — an unsupervised anomaly detector. `load_weights()` deserializes a **pre-trained** estimator via `joblib.load()` (no training happens in this codebase); `predict()` maps sklearn's inlier/outlier output to the project's `1 = attack, 0 = normal` convention and produces a `[0, 1]` confidence via a logistic squash of the decision score. scikit-learn/joblib are imported lazily — importing this module never requires them to be installed.

### Autoencoder Model

`app/ai/models/autoencoder.py`'s `AutoencoderModel` is a reconstruction-error-based anomaly detector backed by a small feed-forward PyTorch network (`Linear → ReLU` encoder/decoder). A sample the network reconstructs poorly (MSE above a calibrated threshold) is flagged as anomalous. It returns the **exact same prediction shape** as `IsolationForestModel` (`.prediction` / `.confidence` / `.metadata`), so the two models are fully interchangeable — swapping one for the other requires zero changes to `InferenceEngine` or `SentinelXEngine`. PyTorch is imported lazily, and the `nn.Module` architecture class is defined *inside* a function so merely importing this file never triggers `import torch`.

### CUDA Acceleration with Automatic CPU Fallback

`app/ai/utils/device.py` provides `get_device("cpu" | "cuda" | "auto")` and `is_cuda_available()`, shared by every model and by `SentinelXEngine.status()`. `AutoencoderModel` auto-detects the best device at construction time, moves the model and every input tensor to it as a single batched transfer, and runs inference inside `torch.inference_mode()`. CUDA logic is strictly confined to `utils/device.py` and `models/autoencoder.py` — every other layer (`inference/`, `sentinelx/`, `preprocessing/`, `datasets/`) has zero knowledge of CUDA/GPU concerns. If CUDA — or PyTorch itself — is unavailable, every device-resolution path falls back to `"cpu"` automatically, so the whole `app/ai/` package imports and runs cleanly on a CPU-only machine.

### Inference Engine

`app/ai/inference/engine.py`'s `InferenceEngine` orchestrates `AttackEventRecord(s)/BaseDataset → PreprocessingPipeline.transform() → TensorBatch → ModelManager.get(model_name) → BaseModel.predict() → InferenceResult`. It is model-agnostic **by contract, not by type-checking** — it never imports a concrete model class, only requiring (via runtime duck-typing) that `predict()` returns something exposing `.prediction`/`.confidence`/`.metadata`. Supports single-event (`predict_event`), batch (`predict_records`), and dataset-wide (`predict_dataset`) inference through one polymorphic `predict()` entry point.

### Investigation Agent

`app/ai/sentinelx/investigator.py`'s `InvestigationAgent` converts a raw `InferenceResult` into a structured, analyst-facing `InvestigationReport`: a per-event `ATTACK`/`NORMAL` verdict and a severity tier (`NONE`/`LOW`/`MEDIUM`/`HIGH`/`CRITICAL`) derived from the model's confidence. Pure triage — it takes no action itself.

### Attack Classifier

`app/ai/sentinelx/classifier.py`'s `AttackClassifier` converts an `InvestigationReport` into standardized attack categories (Normal, Replay Attack, Brute Force, Spoofing, DoS, Invalid Rolling Key, Abnormal Device Behavior, Unknown). Since the current models only predict ATTACK/NORMAL (not *which* attack), this stage applies domain-derived heuristic rules — mirroring the same signal characteristics the synthetic generator uses to construct each category — with required/supporting signal gating so generic signals can't win a category on partial credit alone. Falls back to `Unknown` rather than guessing when no rule matches confidently.

### Response Agent

`app/ai/sentinelx/response_agent.py`'s `ResponseAgent` converts classifications into recommended actions and priority — **it never executes anything**:

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

Priority is escalated (never lowered) by the underlying severity tier, and every recommendation carries human-readable reasoning plus an `immediate_action_required` flag.

### SentinelX Engine

`app/ai/sentinelx/engine.py`'s `SentinelXEngine` is the top-level orchestrator, wiring the four stages above into one call: `analyze()` (accepts a record, a list of records, or a dataset) and `analyze_single()` both return one `SentinelXAnalysis` bundling `inference_result`, `investigation_report`, `classification_report`, and `response_report`.

### AIService Integration

`app/services/ai_service.py`'s `AIService` (Member 1's original interface class) now builds a process-wide `SentinelXEngine` on first use and delegates to it, translating `SentinelXAnalysis` into the pre-existing `AIAnalysisResult`/`AIStatusResult` response shapes. The `IAIService` contract, both method signatures, and `routes/simulation.py`'s dependency injection are all **unchanged** — this is a drop-in replacement for the mock. If no trained model is deployed (`AI_MODEL_WEIGHTS_PATH` unset), `analyze_request()` honestly raises the pre-existing `AIUnavailableError` (`503`) rather than fabricating a result.

---

## 📂 Folder Structure — `app/ai/`

```
app/ai/
├── __init__.py             # Package facade (AIConfig, exceptions, SentinelXEngine)
├── config.py                # AIConfig / load_config() (env var loading)
├── exceptions.py             # AIBaseError hierarchy
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
│   └── autoencoder.py                # AutoencoderModel (PyTorch, CUDA-aware)
├── inference/
│   └── engine.py                # InferenceEngine (preprocess -> predict orchestration)
├── sentinelx/
│   ├── engine.py                 # SentinelXEngine (top-level orchestrator)
│   ├── investigator.py             # InvestigationAgent (verdict + severity triage)
│   ├── classifier.py                 # AttackClassifier (rule-based sub-categorization)
│   └── response_agent.py               # ResponseAgent (action + priority — recommendation only)
└── utils/
    └── device.py               # get_device / is_cuda_available / device_summary
```

---

## 🔄 AI Workflow — From Request to Response

```
1. HTTP request
   POST /api/v1/simulate-attack   { device_id, attack_type, source_ip, payload_sample }

2. routes/simulation.py → SimulationService.process_attack()
   (no business logic in the route itself)

3. SimulationService → AIService.analyze_request(request_data)
   (Member 1's IAIService implementation)

4. AIService synthesizes one representative AttackEventRecord for the
   requested attack_type (via app.ai.datasets.SyntheticEventGenerator —
   the HTTP payload alone doesn't carry the telemetry the model needs),
   then calls SentinelXEngine.analyze_single(record)

5. SentinelXEngine runs the full pipeline:
      PreprocessingPipeline.transform()  →  TensorBatch
      ModelManager.get(model)            →  loaded BaseModel
      BaseModel.predict(TensorBatch)     →  InferenceResult
      InvestigationAgent.investigate()   →  InvestigationReport
      AttackClassifier.classify()        →  ClassificationReport
      ResponseAgent.recommend()          →  ResponseReport
   → returns one SentinelXAnalysis bundling all four reports

6. AIService translates SentinelXAnalysis into the existing
   AIAnalysisResult shape: { risk_score, threat_detected, attack_labels,
   ai_confidence, analysis_id, model, timestamp }

7. SimulationService applies the existing high-risk logic
   (risk_score > 90 → log to blockchain + rotate rolling key)

8. HTTP response
   AttackResponse { risk_score, threat_detected, key_rotated,
   blockchain_logged, action_taken, ... }
```

If no model is loaded (`AI_MODEL_WEIGHTS_PATH` unset), step 4 short-circuits and the response is a `503 Service Unavailable` — the pipeline never fabricates a result.

---

## 🧩 AI Module — Installation Instructions

### Python Version

**Python 3.12 is recommended.** Python 3.14 may fail to install some dependencies — packages like `pydantic-core` and `psycopg2-binary` may not yet have prebuilt wheels for the newest Python version and will attempt to compile from source (requiring a Rust toolchain and a C/C++ linker), which commonly fails on machines without those build tools installed.

```powershell
python --version
```

If it reports 3.13 or 3.14 and you hit build errors below, install Python 3.12 from [python.org/downloads](https://www.python.org/downloads/) and create your virtual environment with it explicitly (`py -3.12 -m venv venv`).

### Virtual Environment Creation

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### Dependency Installation

```bash
cd backend
pip install -r requirements.txt
```

### Additional AI Dependencies

`torch`, `torchvision`, `torchaudio`, `scikit-learn`, and `joblib` are **not yet listed in `requirements.txt`** — the AI module imports them lazily, so the rest of the backend runs fine without them, but they're required to actually load/run a trained model (`IsolationForestModel` needs scikit-learn + joblib; `AutoencoderModel` needs PyTorch):

```bash
# Windows and Linux — identical command (CPU-only build)
pip install torch torchvision torchaudio
pip install scikit-learn joblib
```

For a CUDA-enabled PyTorch build (optional, requires an NVIDIA GPU + CUDA toolkit), see [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/) for the correct `--index-url` for your CUDA version — otherwise the CPU-only install above works everywhere, and every model in this module falls back to CPU automatically.

Verify:

```bash
python -c "import torch; print(torch.__version__, 'CUDA:', torch.cuda.is_available())"
python -c "import sklearn; print(sklearn.__version__)"
```

---

## ▶️ Backend Execution

```bash
cd backend
uvicorn app.main:app --reload
```

Server starts at **http://127.0.0.1:8000** (Swagger UI at `/docs`). The AI module initializes lazily on the first request that needs it — a missing `AI_MODEL_WEIGHTS_PATH` does not prevent the rest of the API from starting.
