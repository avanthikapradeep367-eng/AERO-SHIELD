"""
database.py — SQLAlchemy database engine and session configuration.

This module sets up the PostgreSQL connection using environment variables,
creates the SQLAlchemy engine and session factory, and provides a
dependency-injectable session for FastAPI route handlers.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base  # ✅ Modern SQLAlchemy 2.x style (replaces sqlalchemy.ext.declarative)
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# ── Database URL ──────────────────────────────────────────────────────────────
# Expected format: postgresql://user:password@host:port/dbname
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Check your .env file.")

# ── Engine ────────────────────────────────────────────────────────────────────
# `pool_pre_ping=True` ensures stale connections are recycled automatically.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,                      # Detects broken connections before use
    pool_size=10,                            # Number of connections to maintain in pool
    max_overflow=20,                         # Extra connections allowed beyond pool_size
    echo=False,                              # Set to True to log all SQL statements (debug)
    connect_args={"connect_timeout": 10},   # ✅ Prevents hanging if DB is unreachable
)

# ── Session Factory ───────────────────────────────────────────────────────────
# autocommit=False → We commit manually (best practice for transactional safety)
# autoflush=False  → Prevents accidental flushes before we're ready
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# ── Declarative Base ──────────────────────────────────────────────────────────
# All ORM models will inherit from this Base class.
Base = declarative_base()


# ── Dependency ────────────────────────────────────────────────────────────────
def get_db():
    """
    FastAPI dependency that provides a database session per request.

    Usage in a route:
        @router.get("/example")
        def example(db: Session = Depends(get_db)):
            ...

    The session is automatically closed after the request completes,
    even if an exception is raised (ensured by the finally block).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
