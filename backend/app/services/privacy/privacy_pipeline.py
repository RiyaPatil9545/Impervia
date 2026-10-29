import time
from dataclasses import dataclass
from decimal import Decimal

from app.core.config import settings
from app.ml.pii_detection.detector import PIISpan, pii_detector
from app.ml.relevance_detection.detector import (
    RelevanceAnalysisResult,
    academic_relevance_detector,
)
from app.ml.risk_assessment.assessor import RiskDecision, risk_assessor
from app.ml.sensitive_content.detector import SensitiveSpan, sensitive_detector
from app.models.enums import (
    FindingType,
    PrivacyAction,
    ProcessingPath,
    RelevanceStatus,
    RiskLevel,
)
from app.schemas.privacy import PrivacyFindingSchema
from app.services.privacy.preprocessing import preprocessor
from app.services.privacy.sanitization import sanitizer_service


@dataclass
class PrivacyPipelineResult:
    pii_detected: bool
    sensitive_content_detected: bool
    context_relevance: RelevanceStatus
    risk_level: RiskLevel
    processing_path: ProcessingPath
    sanitized_text: str
    extracted_academic_query: str | None
    redirection_message: str | None
    findings: list[PrivacyFindingSchema]
    detector_version: str
    processing_time_ms: int
    raw_decision_reason: str


class PrivacyPipeline:
    """
    End-to-end Privacy Handler pipeline orchestrating:
    Input -> Preprocessing -> PII Detection -> Sensitive Content Detection ->
    Academic Relevance -> Risk Assessment -> Privacy Decision -> Sanitized Output.
    """

    def __init__(self) -> None:
        self.preprocessor = preprocessor
        self.pii_detector = pii_detector
        self.sensitive_detector = sensitive_detector
        self.relevance_detector = academic_relevance_detector
        self.risk_assessor = risk_assessor
        self.sanitizer = sanitizer_service
        self.version = settings.DETECTOR_VERSION

    def process(self, raw_input: str) -> PrivacyPipelineResult:
        start_time = time.perf_counter()

        # Step 1: Preprocessing
        clean_text = self.preprocessor.preprocess(raw_input)
        if not clean_text:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return PrivacyPipelineResult(
                pii_detected=False,
                sensitive_content_detected=False,
                context_relevance=RelevanceStatus.not_applicable,
                risk_level=RiskLevel.low,
                processing_path=ProcessingPath.pass_through,
                sanitized_text="",
                extracted_academic_query=None,
                redirection_message=None,
                findings=[],
                detector_version=self.version,
                processing_time_ms=elapsed_ms,
                raw_decision_reason="Empty input text.",
            )

        # Step 2: PII Detection
        pii_spans: list[PIISpan] = self.pii_detector.detect(clean_text)
        pii_detected = len(pii_spans) > 0

        # Step 3: Sensitive Content Detection
        sensitive_spans: list[SensitiveSpan] = self.sensitive_detector.detect(clean_text)
        sensitive_detected = len(sensitive_spans) > 0

        # Step 4: Academic Relevance Detection & Query Extraction
        relevance: RelevanceAnalysisResult = self.relevance_detector.analyze(
            clean_text,
            has_sensitive=sensitive_detected,
            sensitive_texts=[s.text for s in sensitive_spans],
        )

        # Step 5: Risk Assessment & Processing Path Decision
        decision: RiskDecision = self.risk_assessor.assess(
            pii_spans=pii_spans,
            sensitive_spans=sensitive_spans,
            relevance=relevance,
        )

        # Step 6: Sanitization / Separation / Redirection
        sanitized_text = clean_text
        extracted_academic_query: str | None = None
        redirection_message: str | None = None

        if decision.processing_path == ProcessingPath.pass_through:
            sanitized_text = clean_text
            extracted_academic_query = clean_text

        elif decision.processing_path == ProcessingPath.sanitize:
            sanitized_text = self.sanitizer.mask_pii(clean_text, pii_spans)
            extracted_academic_query = sanitized_text

        elif decision.processing_path == ProcessingPath.separate:
            # Mask any PII in the separated academic portion
            academic_part = relevance.academic_text or clean_text
            extracted_academic_query, notice = self.sanitizer.separate(
                clean_text,
                academic_part,
                pii_spans,
            )
            sanitized_text = extracted_academic_query
            redirection_message = notice

        elif decision.processing_path == ProcessingPath.redirect:
            redirection_message = self.sanitizer.generate_redirection_response(
                decision,
                sensitive_spans,
                pii_spans,
            )
            # Never keep sensitive raw text in sanitized_text for redirected requests
            sanitized_text = "[CONTENT_REMOVED_BY_PRIVACY_HANDLER]"
            extracted_academic_query = None

        # Step 7: Build Structured Privacy Findings (Never storing raw sensitive text)
        findings = self._build_findings(
            pii_spans=pii_spans,
            sensitive_spans=sensitive_spans,
            decision=decision,
            relevance=relevance,
        )

        elapsed_ms = max(1, int((time.perf_counter() - start_time) * 1000))

        return PrivacyPipelineResult(
            pii_detected=pii_detected,
            sensitive_content_detected=sensitive_detected,
            context_relevance=relevance.status,
            risk_level=decision.risk_level,
            processing_path=decision.processing_path,
            sanitized_text=sanitized_text,
            extracted_academic_query=extracted_academic_query,
            redirection_message=redirection_message,
            findings=findings,
            detector_version=self.version,
            processing_time_ms=elapsed_ms,
            raw_decision_reason=decision.reason,
        )

    def _build_findings(
        self,
        pii_spans: list[PIISpan],
        sensitive_spans: list[SensitiveSpan],
        decision: RiskDecision,
        relevance: RelevanceAnalysisResult,
    ) -> list[PrivacyFindingSchema]:
        """
        Aggregates and formats detected spans into schema-compliant findings without raw text.
        """
        # Map PII occurrences
        pii_counts: dict[str, tuple[int, Decimal, PrivacyAction]] = {}
        for span in pii_spans:
            action = PrivacyAction.masked if decision.processing_path in {ProcessingPath.sanitize, ProcessingPath.separate} else PrivacyAction.removed
            if span.category in pii_counts:
                count, max_conf, _ = pii_counts[span.category]
                pii_counts[span.category] = (count + 1, max(max_conf, span.confidence), action)
            else:
                pii_counts[span.category] = (1, span.confidence, action)

        # Map Sensitive content occurrences
        sens_counts: dict[str, tuple[int, Decimal, PrivacyAction]] = {}
        for span in sensitive_spans:
            action = PrivacyAction.removed if decision.processing_path in {ProcessingPath.separate, ProcessingPath.redirect} else PrivacyAction.ignored
            if span.category in sens_counts:
                count, max_conf, _ = sens_counts[span.category]
                sens_counts[span.category] = (count + 1, max(max_conf, span.confidence), action)
            else:
                sens_counts[span.category] = (1, span.confidence, action)

        findings: list[PrivacyFindingSchema] = []

        for category, (count, conf, action) in pii_counts.items():
            findings.append(
                PrivacyFindingSchema(
                    finding_type=FindingType.pii,
                    category=category,
                    relevance=relevance.status,
                    action_taken=action,
                    occurrence_count=count,
                    confidence=conf,
                )
            )

        for category, (count, conf, action) in sens_counts.items():
            findings.append(
                PrivacyFindingSchema(
                    finding_type=FindingType.sensitive_content,
                    category=category,
                    relevance=relevance.status,
                    action_taken=action,
                    occurrence_count=count,
                    confidence=conf,
                )
            )

        return findings


privacy_pipeline = PrivacyPipeline()
