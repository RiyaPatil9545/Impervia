from dataclasses import dataclass

from app.ml.pii_detection.detector import PIISpan
from app.ml.relevance_detection.detector import RelevanceAnalysisResult
from app.ml.sensitive_content.detector import SensitiveSpan
from app.models.enums import ProcessingPath, RiskLevel


@dataclass
class RiskDecision:
    risk_level: RiskLevel
    processing_path: ProcessingPath
    reason: str


class RiskAssessor:
    """
    Deterministic, rule-based risk assessment engine evaluating
    PII, sensitive disclosures, and academic relevance to determine
    the appropriate risk level and processing path.
    """

    def assess(
        self,
        pii_spans: list[PIISpan],
        sensitive_spans: list[SensitiveSpan],
        relevance: RelevanceAnalysisResult,
    ) -> RiskDecision:
        has_pii = len(pii_spans) > 0
        has_sensitive = len(sensitive_spans) > 0
        has_high_severity = any(s.severity == "high" for s in sensitive_spans)
        has_severe_pii = any(p.category in {"financial", "national_id"} for p in pii_spans)

        # 1. High Risk & Redirect:
        # Acute crisis (e.g., suicide / self-harm) or severe PII / sensitive disclosure with NO academic query
        if has_high_severity:
            return RiskDecision(
                risk_level=RiskLevel.high,
                processing_path=ProcessingPath.redirect,
                reason="Severe sensitive distress or crisis detected.",
            )

        if (has_sensitive or has_severe_pii) and not relevance.has_academic_intent:
            return RiskDecision(
                risk_level=RiskLevel.high,
                processing_path=ProcessingPath.redirect,
                reason="Sensitive or severe personal disclosure without academic relevance.",
            )

        # 2. Mixed Content & Separate:
        # Legitimate academic query accompanied by sensitive emotional/personal disclosure
        if has_sensitive and relevance.has_academic_intent:
            return RiskDecision(
                risk_level=RiskLevel.mixed,
                processing_path=ProcessingPath.separate,
                reason="Mixed content containing both academic request and sensitive disclosure.",
            )

        # 3. Sanitize:
        # Academic query with PII (e.g. student email, phone, name)
        if has_pii and relevance.has_academic_intent:
            return RiskDecision(
                risk_level=RiskLevel.mixed if has_severe_pii else RiskLevel.low,
                processing_path=ProcessingPath.sanitize,
                reason="Academic request contains identifiable PII that requires in-place sanitization.",
            )

        # 4. Pure PII with no academic query:
        if has_pii and not relevance.has_academic_intent:
            return RiskDecision(
                risk_level=RiskLevel.high if has_severe_pii else RiskLevel.mixed,
                processing_path=ProcessingPath.redirect,
                reason="PII shared without an academic context.",
            )

        # 5. Low Risk & Pass Through:
        # Standard academic request or general neutral conversation with no PII or sensitive content
        return RiskDecision(
            risk_level=RiskLevel.low,
            processing_path=ProcessingPath.pass_through,
            reason="No privacy risk detected. Academic query passed through safely.",
        )


risk_assessor = RiskAssessor()
