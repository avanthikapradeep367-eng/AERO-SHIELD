"""
services/ai_service.py — AI / SentinelX integration interface layer.

This module is a MOCK / PLACEHOLDER owned by Member 1 (Backend).
It defines the contract that the real SentinelX engine (Member 3)
will fulfil once the CUDA / PyTorch threat-detection layer is ready.

DO NOT implement real inference here.
DO NOT call PyTorch, CUDA, or any model weights from this file.

When Member 3 is ready, replace the mocked return values with actual
HTTP or IPC calls to the SentinelX inference service.
"""

import logging
import uuid
import random
from datetime import datetime, timezone

from app.interfaces.ai_interface import IAIService
from app.core.logger import ai_logger as logger

# Attack-type to baseline risk mapping used by the mock
_BASELINE_RISK: dict[str, float] = {
    "DDOS":             88.0,
    "INJECTION":        75.0,
    "REPLAY":           60.0,
    "MAN_IN_THE_MIDDLE": 95.0,
    "BRUTE_FORCE":      70.0,
    "SPOOFING":         65.0,
    "JAMMING":          80.0,
    "UNKNOWN":          50.0,
}


class AIService(IAIService):
    """
    Interface layer for AI threat-analysis interactions.

    All methods are async to match the eventual real implementation,
    which will perform I/O against the SentinelX inference endpoint.
    """

    async def analyze_request(self, request_data: dict) -> dict:
        """
        Analyze an incoming request / event for threats.

        Accepts a generic dict so it can receive any payload from any
        route without coupling the AI layer to a specific schema.

        Returns a standardised analysis result that includes:
            - risk_score       float  0–100
            - threat_detected  bool
            - attack_labels    list[str]
            - ai_confidence    float  0–100
            - analysis_id      str    UUID for correlation

        Args:
            request_data: Arbitrary dict describing the event to analyse.
                          Expected keys (all optional):
                            device_id  str
                            attack_type str
                            source_ip   str
                            payload_sample str
        """
        analysis_id = str(uuid.uuid4())
        attack_type = request_data.get("attack_type", "UNKNOWN").upper()

        # Mocked risk: baseline ± small random jitter
        base = _BASELINE_RISK.get(attack_type, 50.0)
        jitter = random.uniform(-5.0, 5.0)
        risk_score = max(0.0, min(100.0, base + jitter))
        ai_confidence = round(random.uniform(78.0, 99.0), 2)

        threat_detected = risk_score > 70.0
        labels = [attack_type] if threat_detected else []

        logger.info(
            "[MOCK] ai.analyze_request | id=%s attack=%s risk=%.1f confidence=%.1f%%",
            analysis_id,
            attack_type,
            risk_score,
            ai_confidence,
        )

        return {
            "mocked": True,
            "analysis_id": analysis_id,
            "risk_score": round(risk_score, 2),
            "threat_detected": threat_detected,
            "attack_labels": labels,
            "ai_confidence": ai_confidence,
            "model": "sentinelx-mock-v0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_status(self) -> dict:
        """
        Return mocked AI engine status.
        Used by the health-check endpoint.
        """
        return {
            "mocked": True,
            "status": "operational",
            "model": "sentinelx-mock-v0",
            "cuda_available": False,
            "device": "cpu (mocked)",
        }
