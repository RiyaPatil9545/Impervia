from decimal import Decimal

from app.ml.pii_detection.detector import PIISpan
from app.ml.relevance_detection.detector import RelevanceAnalysisResult
from app.ml.risk_assessment.assessor import RiskAssessor
from app.ml.sensitive_content.detector import SensitiveSpan
from app.models.enums import ProcessingPath, RelevanceStatus, RiskLevel


def test_low_risk_pass_through():
    assessor = RiskAssessor()
    relevance = RelevanceAnalysisResult(
        status=RelevanceStatus.relevant,
        academic_score=0.8,
        has_academic_intent=True,
        academic_text="Explain TCP vs UDP",
        non_academic_text=None,
    )
    decision = assessor.assess(pii_spans=[], sensitive_spans=[], relevance=relevance)

    assert decision.risk_level == RiskLevel.low
    assert decision.processing_path == ProcessingPath.pass_through


def test_sanitize_path_on_academic_with_pii():
    assessor = RiskAssessor()
    pii = [
        PIISpan(
            category="email",
            start=0,
            end=18,
            text="student@domain.edu",
            confidence=Decimal("0.98"),
        )
    ]
    relevance = RelevanceAnalysisResult(
        status=RelevanceStatus.relevant,
        academic_score=0.7,
        has_academic_intent=True,
        academic_text="Can you solve this equation?",
        non_academic_text=None,
    )
    decision = assessor.assess(pii_spans=pii, sensitive_spans=[], relevance=relevance)

    assert decision.risk_level == RiskLevel.low
    assert decision.processing_path == ProcessingPath.sanitize


def test_separate_path_on_mixed_content():
    assessor = RiskAssessor()
    sens = [
        SensitiveSpan(
            category="mental_health",
            start=0,
            end=20,
            text="having a panic attack",
            confidence=Decimal("0.85"),
            severity="medium",
        )
    ]
    relevance = RelevanceAnalysisResult(
        status=RelevanceStatus.mixed,
        academic_score=0.6,
        has_academic_intent=True,
        academic_text="What is Bayes Theorem?",
        non_academic_text="having a panic attack",
    )
    decision = assessor.assess(pii_spans=[], sensitive_spans=sens, relevance=relevance)

    assert decision.risk_level == RiskLevel.mixed
    assert decision.processing_path == ProcessingPath.separate


def test_redirect_path_on_crisis():
    assessor = RiskAssessor()
    sens = [
        SensitiveSpan(
            category="mental_health",
            start=0,
            end=20,
            text="want to end my life",
            confidence=Decimal("0.95"),
            severity="high",
        )
    ]
    relevance = RelevanceAnalysisResult(
        status=RelevanceStatus.not_relevant,
        academic_score=0.1,
        has_academic_intent=False,
        academic_text=None,
        non_academic_text=None,
    )
    decision = assessor.assess(pii_spans=[], sensitive_spans=sens, relevance=relevance)

    assert decision.risk_level == RiskLevel.high
    assert decision.processing_path == ProcessingPath.redirect


def test_redirect_path_on_financial_card_dump():
    assessor = RiskAssessor()
    pii = [
        PIISpan(
            category="financial",
            start=0,
            end=19,
            text="4111-2222-3333-4444",
            confidence=Decimal("0.90"),
        )
    ]
    relevance = RelevanceAnalysisResult(
        status=RelevanceStatus.not_relevant,
        academic_score=0.0,
        has_academic_intent=False,
        academic_text=None,
        non_academic_text=None,
    )
    decision = assessor.assess(pii_spans=pii, sensitive_spans=[], relevance=relevance)

    assert decision.risk_level == RiskLevel.high
    assert decision.processing_path == ProcessingPath.redirect
