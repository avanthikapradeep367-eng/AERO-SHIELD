"""
services/rolling_key_service.py — Rolling key helper functions.

Provides cryptographic helpers for rolling key generation, rotation,
and validation. This layer is owned by Member 1 (Backend / Auth).

The service is stateless — it generates and validates keys but does
NOT persist them. Callers are responsible for storing/retrieving keys
from the database and passing them here for validation.
"""

import secrets
import hmac
import hashlib
import time
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Default key TTL in seconds (1 hour)
DEFAULT_KEY_TTL: int = 3600


class RollingKeyService:
    """
    Cryptographic helper service for rolling key authentication.

    All methods are synchronous and pure — no I/O, no state.
    """

    def generate_key(self, device_id: str) -> str:
        """
        Generate a new cryptographically secure rolling key for a device.

        Uses a 32-byte random token (256-bit entropy) anchored to the
        device_id via HMAC-SHA256 so the key is scoped to that device.

        Returns:
            A hex-encoded 64-character key string.
        """
        seed = secrets.token_bytes(32)
        device_tag = device_id.encode("utf-8")
        key = hmac.new(seed, device_tag, hashlib.sha256).hexdigest()
        logger.debug("Generated new rolling key for device '%s'.", device_id)
        return key

    def rotate_key(self, device_id: str, current_key: str) -> str:
        """
        Rotate a device's rolling key by deriving the next key from the
        current one plus a timestamp-based nonce.

        Rotation is deterministic given the same inputs, allowing the
        server to verify the client performed the expected rotation.

        Args:
            device_id:   Unique device identifier.
            current_key: The key that is being retired.

        Returns:
            A new hex-encoded 64-character key string.
        """
        nonce = str(int(time.time())).encode("utf-8")
        material = f"{device_id}:{current_key}".encode("utf-8")
        new_key = hmac.new(nonce, material, hashlib.sha256).hexdigest()
        logger.info("Rotated rolling key for device '%s'.", device_id)
        return new_key

    def validate_key(
        self, provided_key: str, stored_key: str
    ) -> bool:
        """
        Validate a client-supplied key against the server-stored key.

        Uses constant-time comparison (hmac.compare_digest) to prevent
        timing attacks.

        Args:
            provided_key: Key received from the client request.
            stored_key:   Key retrieved from the server-side store.

        Returns:
            True if the keys match, False otherwise.
        """
        valid = hmac.compare_digest(
            provided_key.encode("utf-8"),
            stored_key.encode("utf-8"),
        )
        if not valid:
            logger.warning("Rolling key validation failed — key mismatch.")
        return valid

    def is_expired(
        self, issued_at: float, ttl_seconds: int = DEFAULT_KEY_TTL
    ) -> bool:
        """
        Check whether a rolling key has exceeded its time-to-live.

        Args:
            issued_at:   Unix timestamp (float) of when the key was issued.
            ttl_seconds: How long the key is valid. Defaults to 3600 s.

        Returns:
            True if the key has expired, False if still valid.
        """
        age = time.time() - issued_at
        expired = age > ttl_seconds
        if expired:
            logger.info(
                "Rolling key expired (age=%.1f s, ttl=%d s).", age, ttl_seconds
            )
        return expired

    def key_metadata(self, device_id: str) -> dict:
        """
        Build a metadata dict to store alongside a newly generated key.

        Returns a dict with 'issued_at' (Unix float) and 'device_id'.
        """
        return {
            "device_id": device_id,
            "issued_at": time.time(),
            "issued_at_iso": datetime.now(timezone.utc).isoformat(),
        }
