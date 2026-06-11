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
