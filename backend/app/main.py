"""
main.py — AERO-SHIELD FastAPI application entry point.

Initializes the FastAPI app, registers routers, configures CORS,
and creates database tables on startup.

Run with:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.core.logger import configure_logging, error_logger as logger
from app.database import engine, Base
from app.exceptions import (
    AuthenticationError,
    BlockchainError,
    AIServiceError,
)
from app.routes import auth, status, simulation


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    - On startup  → configure logging, create DB tables (graceful if DB is offline)
    - On shutdown → graceful teardown log
    """
    configure_logging()
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("AERO-SHIELD API started. Database tables verified.")
    except Exception as db_err:
        logger.warning(
            "Database unavailable at startup (%s). "
            "Endpoints requiring PostgreSQL will return 503. "
            "Start PostgreSQL and restart to enable DB features.",
            db_err,
        )
    yield
    logger.info("AERO-SHIELD API shutting down.")


# ── FastAPI App Instance ──────────────────────────────────────────────────────
app = FastAPI(
    title="AERO-SHIELD API",
    description=(
        "### AERO-SHIELD Device Management Backend\n\n"
        "Provides endpoints for registering and querying AERO-SHIELD sensor devices, "
        "running attack simulations, and inspecting backend health.\n\n"
        "**Features:**\n"
        "- Device registration with unique ID enforcement\n"
        "- Device lookup by device_id\n"
        "- PostgreSQL persistence via SQLAlchemy ORM\n"
        "- Full Pydantic validation on all requests and responses\n"
        "- Detailed health check with real DB probe\n"
        "- Attack simulation pipeline (AI → Blockchain → Rolling Key)\n"
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
app.include_router(status.router)
app.include_router(simulation.router)


# ── Exception Handlers ────────────────────────────────────────────────────────
# Custom exceptions inherit from HTTPException so FastAPI handles their status
# codes automatically. These handlers add structured logging before the response
# is sent, giving a single place to observe all domain errors.

@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
    logger.warning(
        "AuthenticationError | %s %s | %s",
        request.method,
        request.url.path,
        exc.detail,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(BlockchainError)
async def blockchain_error_handler(request: Request, exc: BlockchainError) -> JSONResponse:
    logger.error(
        "BlockchainError | %s %s | status=%d | %s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(AIServiceError)
async def ai_error_handler(request: Request, exc: AIServiceError) -> JSONResponse:
    logger.error(
        "AIServiceError | %s %s | status=%d | %s",
        request.method,
        request.url.path,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.critical(
        "Unhandled exception | %s %s | %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
        exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected internal error occurred."},
    )


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


