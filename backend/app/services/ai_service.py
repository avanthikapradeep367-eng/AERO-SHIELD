"""
services/ai_service.py — AI / SentinelX integration interface layer.

This module previously returned mocked data while the real SentinelX
engine (app/ai/*) was being built. That engine — dataset generation,
preprocessing, model management, inference, investigation, classification,
and response recommendation — is now complete, and this file delegates to
it via app.ai.sentinelx.SentinelXEngine instead of returning mocked values.

The IAIService interface, both method signatures, and both response dict
shapes are unchanged from the mock — this is a drop-in replacement.
Callers (SimulationService, routes/simulation.py) require no changes.

Bridging the HTTP contract to the ML pipeline
-----------------------------------------------
AttackRequest (the HTTP payload) only carries device_id/attack_type/
source_ip/payload_sample — it doesn't carry the network/auth telemetry
(rolling key state, request rate, packet loss, RF signal, etc.) that
SentinelX's preprocessing pipeline needs. Since this endpoint's job is to
*simulate* an attack scenario (see routes/simulation.py's docstring:
"Submits a simulated attack event"), a single representative
AttackEventRecord is generated for the requested attack_type using
app.ai.datasets.SyntheticEventGenerator — the same generator the dataset
layer uses to build training data, not new mock logic — with device_id/
source_ip/payload size substituted from the real request when provided.
The resulting risk_score/threat_detected/attack_labels are then genuine
SentinelXEngine output, not fabricated values.

Honest unavailability, not a silent fallback to mocking
----------------------------------------------------------
No trained model weights ship in this repository. If AI_MODEL_WEIGHTS_PATH
is unset (default) or loading fails, the underlying model stays unloaded
and analyze_request() raises the existing AIUnavailableError (503) —
exactly the contract this module already documented for "engine
unreachable" — rather than pretending to have a result. `mocked` in every
response below is now `False`: it is no longer accurate to claim mocked
results now that the mock has been removed.
"""

import os
import random
import threading

from pydantic import ValidationError

from app.ai.datasets import AttackLogDataset, EventType, SyntheticEventGenerator
from app.ai.datasets.schema import AttackEventRecord
from app.ai.exceptions import AIBaseError
from app.ai.inference import InferenceEngine
from app.ai.models import ModelManager
from app.ai.models.isolation_forest import MODEL_NAME
from app.ai.preprocessing import PreprocessingPipeline
from app.ai.sentinelx import SentinelXAnalysis, SentinelXEngine
from app.core.logger import ai_logger as logger
from app.exceptions.ai import AIAnalysisError, AIInvalidInputError, AIUnavailableError
from app.interfaces.ai_interface import IAIService

# Maps the HTTP-facing attack_type vocabulary (schemas/attack.py's
# VALID_ATTACK_TYPES) onto the closest dataset-layer EventType, so a
# representative synthetic record can be generated for the requested
# scenario. Not a 1:1 taxonomy match — DDOS/JAMMING both map to DOS
# (volumetric denial-of-service at different layers), MAN_IN_THE_MIDDLE
# maps to SPOOFING (closest identity/traffic-interception analogue), and
# INJECTION/UNKNOWN map to the general ABNORMAL_DEVICE_BEHAVIOR bucket.
_ATTACK_TYPE_TO_EVENT_TYPE: dict[str, EventType] = {
    "DDOS": EventType.DOS,
    "INJECTION": EventType.ABNORMAL_DEVICE_BEHAVIOR,
    "REPLAY": EventType.REPLAY,
    "MAN_IN_THE_MIDDLE": EventType.SPOOFING,
    "BRUTE_FORCE": EventType.BRUTE_FORCE,
    "SPOOFING": EventType.SPOOFING,
    "JAMMING": EventType.DOS,
    "UNKNOWN": EventType.ABNORMAL_DEVICE_BEHAVIOR,
}

_GENERATOR_METHOD_NAME: dict[EventType, str] = {
    EventType.NORMAL: "normal_traffic",
    EventType.REPLAY: "replay_attack",
    EventType.BRUTE_FORCE: "brute_force_attack",
    EventType.SPOOFING: "spoofing_attack",
    EventType.DOS: "dos_attack",
    EventType.INVALID_ROLLING_KEY: "invalid_rolling_key",
    EventType.ABNORMAL_DEVICE_BEHAVIOR: "abnormal_device_behavior",
}

_BOOTSTRAP_DATASET_SIZE = 500
_BOOTSTRAP_DATASET_SEED = 42

# Process-wide SentinelXEngine, built lazily on first use and reused
# across every AIService() instance (FastAPI instantiates one per
# request via Depends) — see _get_sentinelx_engine().
_sentinelx_engine: SentinelXEngine | None = None
_sentinelx_engine_lock = threading.Lock()


def _build_sentinelx_engine() -> SentinelXEngine:
    """
    Build the process-wide SentinelXEngine: a fitted PreprocessingPipeline
    (fit on a deterministic bootstrap synthetic dataset, so scaler/encoder
    state exists) plus an InferenceEngine for the isolation_forest model.

    If AI_MODEL_WEIGHTS_PATH is configured and loadable, the model is
    loaded immediately. Otherwise the model stays unloaded and
    analyze_request() will correctly report the service as unavailable
    rather than fabricate a result — no training happens here or anywhere
    in this file.
    """
    bootstrap_dataset = AttackLogDataset(size=_BOOTSTRAP_DATASET_SIZE, seed=_BOOTSTRAP_DATASET_SEED)
    bootstrap_dataset.load()
    pipeline = PreprocessingPipeline().fit(bootstrap_dataset.records)

    manager = ModelManager()
    inference = InferenceEngine(model_name=MODEL_NAME, pipeline=pipeline, model_manager=manager)

    weights_path = os.getenv("AI_MODEL_WEIGHTS_PATH")
    if weights_path:
        try:
            inference.load_model(weights_path=weights_path, device=os.getenv("AI_DEVICE", "cpu"))
            logger.info("SentinelX model loaded from %s.", weights_path)
        except Exception as exc:
            logger.warning(
                "SentinelX model weights at %s failed to load (%s); "
                "AI service will report unavailable until this is fixed.",
                weights_path,
                exc,
            )
    else:
        logger.info(
            "AI_MODEL_WEIGHTS_PATH not set; SentinelX model not loaded. "
            "AI service will report unavailable until a trained model is deployed."
        )

    return SentinelXEngine(inference=inference)


def _get_sentinelx_engine() -> SentinelXEngine:
    """Return the process-wide SentinelXEngine, building it on first call."""
    global _sentinelx_engine
    if _sentinelx_engine is None:
        with _sentinelx_engine_lock:
            if _sentinelx_engine is None:
                _sentinelx_engine = _build_sentinelx_engine()
    return _sentinelx_engine


def _build_attack_event_record(request_data: dict) -> AttackEventRecord:
    """
    Build one AttackEventRecord representative of the requested attack_type.

    Reuses app.ai.datasets.SyntheticEventGenerator (the dataset layer's own
    generator, not new logic) to synthesize the network/auth telemetry the
    ML pipeline needs but request_data does not carry, then substitutes
    device_id/source_ip/payload size from the real request where provided.
    """
    attack_type = str(request_data.get("attack_type") or "UNKNOWN").strip().upper()
    event_type = _ATTACK_TYPE_TO_EVENT_TYPE.get(attack_type, EventType.ABNORMAL_DEVICE_BEHAVIOR)
    method_name = _GENERATOR_METHOD_NAME[event_type]

    generator = SyntheticEventGenerator(seed=random.randint(0, 2_147_483_647))
    [record] = getattr(generator, method_name)(1)

    overrides: dict = {}
    if request_data.get("device_id"):
        overrides["device_id"] = str(request_data["device_id"]).strip().upper()
    if request_data.get("source_ip"):
        overrides["source_ip"] = str(request_data["source_ip"])
    if request_data.get("payload_sample"):
        overrides["payload_size_bytes"] = len(str(request_data["payload_sample"]).encode("utf-8"))

    if not overrides:
        return record

    merged = {**record.model_dump(), **overrides}
    try:
        return AttackEventRecord.model_validate(merged)
    except ValidationError as exc:
        raise AIInvalidInputError(reason=str(exc)) from exc


def _translate_analysis_to_response(analysis: SentinelXAnalysis) -> dict:
    """Translate a SentinelXAnalysis (single-event) into the AIAnalysisResult dict shape."""
    finding = analysis.investigation_report.findings[0]
    classification = analysis.classification_report.classifications[0]

    threat_detected = finding.verdict == "ATTACK"
    attack_labels = [classification.category.value] if threat_detected else []

    return {
        "mocked": False,
        "analysis_id": finding.investigation_id,
        "risk_score": round(finding.confidence * 100, 2),
        "threat_detected": threat_detected,
        "attack_labels": attack_labels,
        "ai_confidence": round(classification.confidence * 100, 2),
        "model": f"sentinelx-{analysis.inference_result.execution.model_name}",
        "timestamp": analysis.generated_at,
    }


class AIService(IAIService):
    """
    Interface layer for AI threat-analysis interactions, backed by the
    real app.ai.sentinelx.SentinelXEngine.

    Takes no constructor arguments — existing dependency injection
    (routes/simulation.py's get_ai_service() -> AIService()) is unchanged.
    Construction fetches the process-wide SentinelXEngine (built once,
    lazily) rather than rebuilding the pipeline/model per request.
    """

    def __init__(self) -> None:
        self._engine = _get_sentinelx_engine()

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
        if not self._engine.inference.is_model_loaded():
            logger.warning("analyze_request called but no SentinelX model is loaded.")
            raise AIUnavailableError()

        record = _build_attack_event_record(request_data)

        try:
            analysis = self._engine.analyze_single(record)
        except AIBaseError as exc:
            logger.error("SentinelX analysis failed for device '%s': %s", record.device_id, exc)
            raise AIAnalysisError(reason=str(exc)) from exc

        response = _translate_analysis_to_response(analysis)

        logger.info(
            "ai.analyze_request | id=%s device=%s risk=%.1f confidence=%.1f%% threat=%s",
            response["analysis_id"],
            record.device_id,
            response["risk_score"],
            response["ai_confidence"],
            response["threat_detected"],
        )

        return response

    async def get_status(self) -> dict:
        """
        Return the current SentinelX engine health and capability status.
        Used by the health-check endpoint.
        """
        engine_status = self._engine.status()
        operational = engine_status["status"] == "operational"

        return {
            "mocked": False,
            "status": "operational" if operational else "unavailable",
            "model": engine_status["model"] if operational else "sentinelx (model not loaded)",
            "cuda_available": engine_status["cuda_available"],
            "device": engine_status["device"],
        }
