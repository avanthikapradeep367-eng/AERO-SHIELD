"""
app/ai/sentinelx/engine.py — SentinelXEngine: top-level orchestrator for
the full SentinelX threat-analysis pipeline.

    AttackEventRecord(s) / BaseDataset
        -> InferenceEngine.predict()        -> InferenceResult
        -> InvestigationAgent.investigate() -> InvestigationReport
        -> AttackClassifier.classify()      -> ClassificationReport
        -> ResponseAgent.recommend()        -> ResponseReport
        -> SentinelXAnalysis (bundles all four)

This module only wires the four already-implemented stages together in
order and bundles their outputs into one structured result — it does not
reimplement any of their logic. Each stage remains independently usable
and independently testable (see app/ai/inference/engine.py,
app/ai/sentinelx/investigator.py, classifier.py, response_agent.py).

Explicitly OUT OF SCOPE for this module (by design, not oversight):
  - AIService integration. app/services/ai_service.py still returns
    mocked data and does not import anything from app.ai — wiring
    SentinelXEngine into it (translating SentinelXAnalysis into
    IAIService's analyze_request()/get_status() dict shape) is a
    separate, not-yet-implemented change owned outside this file.
  - Executing any response action. ResponseAgent already never rotates
    keys, blocks/blacklists devices, or calls app.blockchain.*/
    app.services.blockchain_service — SentinelXEngine simply carries that
    guarantee forward by only ever calling ResponseAgent.recommend(), never
    anything that would act on its output.
  - Loading model weights. That remains InferenceEngine.load_model()'s
    job — SentinelXEngine receives an InferenceEngine instance and does
    not construct or load one itself.

No ML/CUDA dependency is imported here — this module only orchestrates
dataclasses already produced by the four stages above.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.ai.datasets.base import BaseDataset
from app.ai.datasets.schema import AttackEventRecord
from app.ai.exceptions import AIBaseError
from app.ai.inference.engine import InferenceEngine, InferenceResult
from app.ai.preprocessing.pipeline import records_from_dataset
from app.ai.utils.device import device_summary

from .classifier import AttackClassifier, ClassificationReport
from .investigator import InvestigationAgent, InvestigationReport
from .response_agent import ResponseAgent, ResponseReport


class SentinelXError(AIBaseError):
    """Raised when SentinelXEngine receives malformed or inconsistent input."""


def _normalize_records(
    input_data: AttackEventRecord | list[AttackEventRecord] | BaseDataset,
) -> list[AttackEventRecord]:
    """
    Materialize a list[AttackEventRecord] from any input shape
    InferenceEngine.predict() accepts, so InvestigationAgent/AttackClassifier
    can be handed the same source records for device_id/timestamp
    enrichment and heuristic sub-typing that InferenceEngine used
    internally for prediction.
    """
    if isinstance(input_data, BaseDataset):
        return records_from_dataset(input_data)
    if isinstance(input_data, AttackEventRecord):
        return [input_data]
    if isinstance(input_data, list):
        return list(input_data)
    raise SentinelXError(
        "SentinelXEngine.analyze() does not support input of type "
        f"{type(input_data).__name__}. Expected AttackEventRecord, "
        "list[AttackEventRecord], or BaseDataset."
    )


@dataclass
class SentinelXAnalysis:
    """
    Single structured result bundling every stage of one analyze()/
    analyze_single() call. Both methods return this same shape — for
    analyze_single(), every nested report simply contains exactly one entry.
    """

    inference_result: InferenceResult
    investigation_report: InvestigationReport
    classification_report: ClassificationReport
    response_report: ResponseReport
    generated_at: str  # ISO-8601 UTC, when this bundled result was assembled


class SentinelXEngine:
    """
    Orchestrates InferenceEngine -> InvestigationAgent -> AttackClassifier
    -> ResponseAgent into a single call.

    Requires an already-constructed InferenceEngine (with its
    PreprocessingPipeline already fitted and, before analyze() is called,
    its model already loaded via InferenceEngine.load_model() — this class
    does neither of those for you). InvestigationAgent/AttackClassifier/
    ResponseAgent default to their standard configuration if not supplied.

    Usage:
        engine = SentinelXEngine(inference=inference_engine)
        analysis = engine.analyze(some_dataset_or_records_or_one_record)
        analysis = engine.analyze_single(one_record)
    """

    def __init__(
        self,
        inference: InferenceEngine,
        investigator: InvestigationAgent | None = None,
        classifier: AttackClassifier | None = None,
        responder: ResponseAgent | None = None,
    ) -> None:
        if not isinstance(inference, InferenceEngine):
            raise SentinelXError(
                f"SentinelXEngine requires an InferenceEngine, got {type(inference).__name__}."
            )
        self._inference = inference
        self._investigator = investigator or InvestigationAgent()
        self._classifier = classifier or AttackClassifier()
        self._responder = responder or ResponseAgent()

    @property
    def inference(self) -> InferenceEngine:
        return self._inference

    def analyze(
        self, input_data: AttackEventRecord | list[AttackEventRecord] | BaseDataset
    ) -> SentinelXAnalysis:
        """
        Run the full SentinelX pipeline for any supported input shape: one
        AttackEventRecord, a list of them, or any BaseDataset (e.g.
        AttackLogDataset).
        """
        inference_result = self._inference.predict(input_data)
        records = _normalize_records(input_data)
        return self._run(inference_result, records)

    def analyze_single(self, record: AttackEventRecord) -> SentinelXAnalysis:
        """
        Run the full SentinelX pipeline for exactly one event.

        NOTE: rolling-key features are device-history-aware (see
        app/ai/preprocessing/rolling_key_features.py) — a lone event has
        no history. See InferenceEngine.predict_event()'s docstring for
        the same caveat, which applies unchanged here.
        """
        inference_result = self._inference.predict_event(record)
        return self._run(inference_result, [record])

    # ── internals ────────────────────────────────────────────────────

    def _run(
        self,
        inference_result: InferenceResult,
        records: list[AttackEventRecord],
    ) -> SentinelXAnalysis:
        investigation_report = self._investigator.investigate(inference_result, records)
        classification_report = self._classifier.classify(investigation_report, records)
        response_report = self._responder.recommend(classification_report)

        return SentinelXAnalysis(
            inference_result=inference_result,
            investigation_report=investigation_report,
            classification_report=classification_report,
            response_report=response_report,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    # ── status ───────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return real device/model status. Safe to call even before the model is loaded."""
        summary = device_summary()
        model_loaded = self._inference.is_model_loaded()
        return {
            "mocked": False,
            "status": "operational" if model_loaded else "not_loaded",
            "model": self._inference.model_name,
            "cuda_available": summary["cuda_available"],
            "device": summary["device"],
        }
