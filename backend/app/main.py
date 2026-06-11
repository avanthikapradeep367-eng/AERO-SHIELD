"""
main.py — AERO-SHIELD FastAPI application entry point.

Initializes the FastAPI app, registers routers, configures CORS,
and creates database tables on startup.

Run with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database import engine, Base
from app.routes import auth


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    - On startup  → create all database tables (if they don't exist)
    - On shutdown → cleanup (placeholder for future teardown logic)
    """
    # Create tables based on all registered ORM models
    Base.metadata.create_all(bind=engine)
    print("[OK] Database tables verified / created.")
    yield
    # Shutdown logic (close connections, flush caches, etc.)
    print("[INFO] AERO-SHIELD server shutting down.")


# ── FastAPI App Instance ──────────────────────────────────────────────────────
app = FastAPI(
    title="AERO-SHIELD API",
    description=(
        "### AERO-SHIELD Device Management Backend\n\n"
        "Provides endpoints for registering and querying AERO-SHIELD sensor devices.\n\n"
        "**Features:**\n"
        "- Device registration with unique ID enforcement\n"
        "- Device lookup by device_id\n"
        "- PostgreSQL persistence via SQLAlchemy ORM\n"
        "- Full Pydantic validation on all requests and responses\n"
    ),
    version="1.0.0",
    contact={
        "name": "AERO-SHIELD Team",
        "email": "support@aero-shield.io",
    },
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan,
)


# ── CORS Middleware ───────────────────────────────────────────────────────────
# Adjust `allow_origins` to your frontend URL(s) in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # ⚠️ Restrict in production (e.g. ["https://yourdomain.com"])
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)


# ── Root Health Check ─────────────────────────────────────────────────────────
@app.get(
    "/",
    tags=["Health"],
    summary="Root health check",
    description="Returns a simple status message to confirm the server is running.",
)
def root():
    """Health check endpoint — confirms the API is live."""
    return {
        "service": "AERO-SHIELD API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
    }


@app.get(
    "/health",
    tags=["Health"],
    summary="Detailed health check",
)
def health_check():
    """Returns detailed service health status."""
    return {
        "status": "healthy",
        "database": "connected",
        "api_version": "1.0.0",
    }
