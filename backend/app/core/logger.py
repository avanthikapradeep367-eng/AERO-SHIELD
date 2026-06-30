"""
core/logger.py — Centralized logging configuration for AERO-SHIELD.

All application code should obtain loggers via `get_logger(__name__)`
or use the pre-built domain loggers at the bottom of this file.
Never call `logging.basicConfig` or create handlers outside this module.

Log levels driven by the LOG_LEVEL environment variable (default INFO).

Format:
    2026-06-29T10:00:00 | INFO     | aeroshield.simulation | message here
"""

import logging
import logging.config
import os
import sys
from typing import Optional


# ── Constants ─────────────────────────────────────────────────────────────────

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
_ROOT_LOGGER_NAME = "aeroshield"

_LEVEL_MAP = {
    "DEBUG":    logging.DEBUG,
    "INFO":     logging.INFO,
    "WARNING":  logging.WARNING,
    "ERROR":    logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


# ── Setup ─────────────────────────────────────────────────────────────────────

def configure_logging(level: Optional[str] = None) -> None:
    """
    Bootstrap the AERO-SHIELD logging stack.

    Call this once at application startup (lifespan handler in main.py).
    Subsequent calls are no-ops — the root logger is only configured once.

    Args:
        level: Log level string (DEBUG/INFO/WARNING/ERROR/CRITICAL).
               Falls back to LOG_LEVEL env var, then INFO.
    """
    raw = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    log_level = _LEVEL_MAP.get(raw, logging.INFO)

    root = logging.getLogger(_ROOT_LOGGER_NAME)
    if root.handlers:
        return  # Already configured — idempotent

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root.setLevel(log_level)
    root.addHandler(handler)
    root.propagate = False

    root.debug("Logging configured at level %s.", raw)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named child logger under the aeroshield namespace.

    Usage:
        logger = get_logger(__name__)
        logger.info("Starting up.")

    If `name` already starts with 'aeroshield.', it is used as-is.
    Otherwise it is prefixed: 'aeroshield.<name>'.
    """
    if name.startswith(_ROOT_LOGGER_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")


# ── Domain Loggers ────────────────────────────────────────────────────────────
# Import these directly in any module that needs a pre-named logger.

auth_logger: logging.Logger = get_logger("auth")
simulation_logger: logging.Logger = get_logger("simulation")
health_logger: logging.Logger = get_logger("health")
blockchain_logger: logging.Logger = get_logger("blockchain")
ai_logger: logging.Logger = get_logger("ai")
error_logger: logging.Logger = get_logger("error")
