"""
AERO-SHIELD X — SHA-256 Hashing Engine (Digital Forensics)

Provides all cryptographic hashing utilities for the forensics layer.
Supports plain text, JSON objects, log files, incident reports, images,
PDFs, and arbitrary binary data.

Every function returns a standardised dict:
    {
        "hash":       "0x<64-char hex>",
        "algorithm":  "SHA-256",
        "size_bytes": <int>,
        "timestamp":  "<ISO-8601>",
        ...type-specific fields...
    }
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.logger import get_logger

logger = get_logger("forensics.hashing")


# ── Internal helpers ────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _sha256_hex(data: bytes) -> str:
    """Return lowercase 64-char hex SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def _to_0x(digest: str) -> str:
    """Prefix a bare hex digest with '0x'."""
    return digest if digest.startswith("0x") else f"0x{digest}"


# ── Public API ──────────────────────────────────────────────────────────────────

def hash_text(text: str, label: str | None = None) -> dict[str, Any]:
    """
    Hash a plain-text string (incident description, log line, etc.) using SHA-256.

    Args:
        text:  The UTF-8 string to hash.
        label: Optional human-readable label for the payload (stored in result).

    Returns:
        Standard hash result dict.
    """
    encoded = text.encode("utf-8")
    digest = _sha256_hex(encoded)
    logger.debug("hash_text | label=%s | size=%d | hash=0x%.8s…", label, len(encoded), digest)
    return {
        "hash": _to_0x(digest),
        "algorithm": "SHA-256",
        "input_type": "text",
        "label": label,
        "size_bytes": len(encoded),
        "timestamp": _now_iso(),
    }


def hash_json(data: dict[str, Any], label: str | None = None) -> dict[str, Any]:
    """
    Hash a JSON-serialisable object using canonical serialisation (sorted keys,
    no whitespace). Guarantees identical hashes regardless of key insertion order.

    Args:
        data:  The Python dict to hash.
        label: Optional label.

    Returns:
        Standard hash result dict, plus ``canonical_representation``.
    """
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    encoded = canonical.encode("utf-8")
    digest = _sha256_hex(encoded)
    logger.debug("hash_json | label=%s | keys=%d | hash=0x%.8s…", label, len(data), digest)
    return {
        "hash": _to_0x(digest),
        "algorithm": "SHA-256",
        "input_type": "json",
        "label": label,
        "size_bytes": len(encoded),
        "canonical_representation": canonical,
        "timestamp": _now_iso(),
    }


def hash_file(file_path: str) -> dict[str, Any]:
    """
    Hash the raw bytes of any file on disk — text, log, image, PDF, binary, etc.

    Args:
        file_path: Absolute or relative path to the file.

    Returns:
        Standard hash result dict, plus ``file_name``, ``file_path``, ``file_extension``.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError:        If the path points to a directory rather than a file.
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not p.is_file():
        raise ValueError(f"Path is a directory, not a file: {file_path}")

    raw = p.read_bytes()
    digest = _sha256_hex(raw)
    logger.info(
        "hash_file | file=%s | size=%d bytes | hash=0x%.8s…",
        p.name, len(raw), digest,
    )
    return {
        "hash": _to_0x(digest),
        "algorithm": "SHA-256",
        "input_type": "file",
        "file_path": str(p.resolve()),
        "file_name": p.name,
        "file_extension": p.suffix.lower(),
        "size_bytes": len(raw),
        "timestamp": _now_iso(),
    }


def hash_bytes(data: bytes, label: str | None = None) -> dict[str, Any]:
    """
    Hash arbitrary in-memory binary data.

    Args:
        data:  Raw bytes to hash.
        label: Optional label.

    Returns:
        Standard hash result dict.
    """
    digest = _sha256_hex(data)
    logger.debug("hash_bytes | label=%s | size=%d | hash=0x%.8s…", label, len(data), digest)
    return {
        "hash": _to_0x(digest),
        "algorithm": "SHA-256",
        "input_type": "bytes",
        "label": label,
        "size_bytes": len(data),
        "timestamp": _now_iso(),
    }


def hash_bytes_from_base64(b64_string: str, label: str | None = None) -> dict[str, Any]:
    """
    Decode a base64-encoded string, then hash the raw bytes.
    Useful for API endpoints that receive binary content as base64.

    Raises:
        ValueError: If ``b64_string`` is not valid base64.
    """
    try:
        raw = base64.b64decode(b64_string, validate=True)
    except Exception as exc:
        raise ValueError(f"Invalid base64 input: {exc}") from exc
    return hash_bytes(raw, label=label)


def compare_hash(hash1: str, hash2: str) -> bool:
    """
    Compare two SHA-256 hashes for equality.

    Handles ``0x``-prefixed and bare hex, case-insensitively.

    Returns:
        True if the hashes represent the same digest.
    """
    def _normalise(h: str) -> str:
        return h.strip().lower().removeprefix("0x")

    result = _normalise(hash1) == _normalise(hash2)
    logger.debug("compare_hash | match=%s", result)
    return result
