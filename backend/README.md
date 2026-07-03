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
