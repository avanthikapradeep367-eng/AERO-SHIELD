"""
interfaces/ai_interface.py — Abstract contract for the AI / SentinelX service.

Defines the method signatures that any AI engine implementation must
satisfy. Member 3's real CUDA/PyTorch inference service and Member 1's
mock both implement this interface, making the integration swap seamless.

Rules:
  - No logic here — only abstract method stubs.
  - Signatures must match the concrete implementations exactly.
  - Return type is `dict` until Member 3 provides typed result models.
"""

from abc import ABC, abstractmethod


class IAIService(ABC):
    """
    Abstract interface for all AI threat-analysis interactions.

    Concrete implementations:
      - app.services.ai_service.AIService  (mock — Member 1)
      - SentinelX inference service        (real — Member 3)
    """

    @abstractmethod
    async def analyze_request(self, request_data: dict) -> dict:
        """
        Analyze an event payload for threats and return a risk assessment.

        The method accepts a generic dict so it is not coupled to any
        specific route schema. The caller is responsible for passing
        relevant fields.

        Common keys in request_data (all optional):
            device_id       str   — originating device
            attack_type     str   — suspected attack category
            source_ip       str   — attacker's IP address
            payload_sample  str   — excerpt of suspicious payload

        Returns:
            Analysis result dict including at minimum:
                analysis_id    str    — UUID for event correlation
                risk_score     float  — threat severity 0–100
                threat_detected bool  — True when risk_score exceeds threshold
                attack_labels  list   — predicted attack categories
                ai_confidence  float  — model confidence 0–100
                model          str    — model identifier used for inference
                timestamp      str    — ISO-8601 UTC timestamp
        """

    @abstractmethod
    async def get_status(self) -> dict:
        """
        Return the current AI engine health and capability status.

        Returns:
            Status dict including at minimum:
                status         str   — "operational" | "unavailable"
                model          str   — active model identifier
                cuda_available bool  — whether GPU acceleration is active
                device         str   — compute device description
        """
