import logging
import re
from decimal import Decimal

from app.ml.pii_detection.detector import PIISpan
from app.ml.preprocessing import preprocessor
from app.ml.relevance_detection.detector import RelevanceAnalysisResult
from app.ml.sensitive_content.detector import SensitiveSpan
from app.ml.slm.client import LocalSLMClient, local_slm_client
from app.ml.slm.schemas import SLMAnalysisResult
from app.models.enums import PrivacyAction, RelevanceStatus

logger = logging.getLogger("impervia")


class HybridAnalyzer:
    """
    Coordinates Python deterministic rule-based detectors and the local Small Language Model (SLM).
    
    Zero-Trust Policy:
    1. Python deterministic rules are the baseline of truth for safety.
    2. High-risk crisis detections (e.g., suicide, self-harm) from rule-based detectors
       can NEVER be downgraded or ignored by the SLM.
    3. The SLM augments sensitivity recall for subtle distress, typos, and nuanced personal venting.
    4. The SLM improves academic intent detection for conversational inquiries.
    5. If the SLM is unavailable, offline, or returns invalid data, the system falls back
       to pure Python rule-based processing seamlessly.
    """

    def __init__(self, slm_client: LocalSLMClient | None = None) -> None:
        self.slm_client = slm_client or local_slm_client

    def analyze_context(
        self,
        clean_text: str,
        rule_pii_spans: list[PIISpan],
        rule_sensitive_spans: list[SensitiveSpan],
        rule_relevance: RelevanceAnalysisResult,
        slm_input_text: str | None = None,
    ) -> tuple[list[SensitiveSpan], RelevanceAnalysisResult, SLMAnalysisResult]:
        """
        Merges rule-based findings with SLM contextual intelligence.
        Returns:
            - merged_sensitive_spans: list[SensitiveSpan]
            - merged_relevance: RelevanceAnalysisResult
            - slm_result: SLMAnalysisResult (for auditability and version reporting)
        """
        # Call local SLM with pre-sanitized text to prevent raw PII leakage to Ollama
        target_slm_text = slm_input_text if slm_input_text is not None else clean_text
        slm_result = self.slm_client.analyze(target_slm_text)

        # Fallback to pure rules if SLM is inactive, offline, or errored
        if not slm_result.is_available or slm_result.analysis is None:
            return rule_sensitive_spans, rule_relevance, slm_result

        slm_analysis = slm_result.analysis

        # ----------------------------------------------------------------------
        # 1. Merge Sensitive Content Spans
        # ----------------------------------------------------------------------
        merged_sensitive_spans: list[SensitiveSpan] = list(rule_sensitive_spans)
        has_rule_crisis = any(s.severity == "high" for s in rule_sensitive_spans)

        # Non-downgrade guarantee: if rule detector flagged high crisis, SLM cannot downgrade it
        has_slm_distress = (
            slm_analysis.has_sensitive_content
            or slm_analysis.is_crisis
            or (slm_analysis.distress_severity in {"high", "medium"})
            or bool(slm_analysis.extracted_sensitive_disclosure)
        )
        if has_slm_distress:
            category = slm_analysis.sensitive_category or "mental_health"
            if category.lower() in {"suicide", "suicidal", "self_harm", "self-harm", "crisis"}:
                category = "mental_health"
            severity = "high" if (slm_analysis.is_crisis or slm_analysis.distress_severity == "high" or has_rule_crisis) else "medium"

            # Check if SLM identified a sensitive disclosure that rule detectors missed
            if not merged_sensitive_spans:
                disclosure_text = (slm_analysis.extracted_sensitive_disclosure or "").strip()
                start_idx: int | None = None
                end_idx: int | None = None

                # 1. Attempt exact substring match
                if disclosure_text and disclosure_text.lower() in clean_text.lower():
                    m = re.search(re.escape(disclosure_text), clean_text, re.IGNORECASE)
                    if m:
                        start_idx, end_idx = m.start(), m.end()

                # 2. Safe sentence/clause-aligned fallback if exact match failed
                if start_idx is None:
                    segments = preprocessor.segment_sentences(clean_text)
                    academic_candidate = (
                        rule_relevance.academic_text
                        or slm_analysis.extracted_academic_query
                        or ""
                    ).strip().lower()

                    best_seg: str | None = None
                    best_overlap = -1

                    for seg in segments:
                        seg_lower = seg.lower()
                        # If segment contains or is contained in the academic query, exclude it
                        if academic_candidate and (
                            seg_lower in academic_candidate or academic_candidate in seg_lower
                        ):
                            continue

                        # Measure word overlap with disclosure text
                        if disclosure_text:
                            words = set(re.findall(r"\w+", disclosure_text.lower()))
                            seg_words = set(re.findall(r"\w+", seg_lower))
                            overlap = len(words & seg_words)
                            if overlap > best_overlap:
                                best_overlap = overlap
                                best_seg = seg
                        elif best_seg is None:
                            best_seg = seg

                    if best_seg:
                        m = re.search(re.escape(best_seg), clean_text)
                        if m:
                            start_idx, end_idx = m.start(), m.end()

                # 3. Only if no academic intent exists at all, fall back to whole-message span.
                # If academic intent exists, do NOT redact the whole message.
                if start_idx is None:
                    if not (rule_relevance.has_academic_intent or slm_analysis.has_academic_intent):
                        start_idx = 0
                        end_idx = len(clean_text)

                if start_idx is not None and end_idx is not None and start_idx < end_idx:
                    merged_sensitive_spans.append(
                        SensitiveSpan(
                            category=category,
                            start=start_idx,
                            end=end_idx,
                            text=clean_text[start_idx:end_idx],
                            confidence=Decimal("0.85"),
                            severity=severity,
                            action=PrivacyAction.removed,
                        )
                    )
            elif not has_rule_crisis and (slm_analysis.is_crisis or slm_analysis.distress_severity == "high"):
                # SLM recognized acute crisis that keyword rules classified only as medium
                for s in merged_sensitive_spans:
                    if s.category == "mental_health":
                        s.severity = "high"
                        s.confidence = Decimal("0.95")

        # ----------------------------------------------------------------------
        # 2. Merge Academic Relevance & Intent
        # ----------------------------------------------------------------------
        has_academic_intent = rule_relevance.has_academic_intent or (
            slm_analysis.has_academic_intent and slm_analysis.academic_score >= 0.4
        )
        academic_score = max(rule_relevance.academic_score, slm_analysis.academic_score)

        # Determine academic query span
        academic_text = rule_relevance.academic_text
        if not academic_text and slm_analysis.has_academic_intent:
            slm_query = (slm_analysis.extracted_academic_query or "").strip()
            # Validate extracted query exists in original text (prevent hallucination)
            if slm_query and (slm_query in clean_text or slm_query.lower() in clean_text.lower()):
                academic_text = slm_query

        # Determine non-academic / sensitive text
        non_academic_text = rule_relevance.non_academic_text
        if not non_academic_text and (slm_analysis.has_sensitive_content or slm_analysis.distress_severity in {"high", "medium"}):
            non_academic_text = slm_analysis.extracted_sensitive_disclosure or clean_text

        has_sensitive = len(merged_sensitive_spans) > 0

        # Compute composite status
        if has_academic_intent and has_sensitive:
            status = RelevanceStatus.mixed
        elif has_academic_intent:
            status = RelevanceStatus.relevant
        elif has_sensitive:
            status = RelevanceStatus.not_relevant
        elif academic_score < 0.2 and len(clean_text.split()) < 3:
            status = RelevanceStatus.unclear
        else:
            status = RelevanceStatus.not_relevant

        merged_relevance = RelevanceAnalysisResult(
            status=status,
            academic_score=round(academic_score, 3),
            has_academic_intent=has_academic_intent,
            academic_text=academic_text,
            non_academic_text=non_academic_text,
        )

        return merged_sensitive_spans, merged_relevance, slm_result


hybrid_analyzer = HybridAnalyzer()
