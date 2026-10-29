from app.models.enums import ProcessingPath, RelevanceStatus, RiskLevel
from app.services.privacy.privacy_pipeline import PrivacyPipeline


def test_end_to_end_pipeline_safe_academic():
    pipeline = PrivacyPipeline()
    raw = "What is Dijkstra's algorithm and how does its priority queue optimize shortest path search?"
    res = pipeline.process(raw)

    assert res.risk_level == RiskLevel.low
    assert res.processing_path == ProcessingPath.pass_through
    assert res.context_relevance == RelevanceStatus.relevant
    assert res.pii_detected is False
    assert res.sensitive_content_detected is False
    assert res.extracted_academic_query == raw
    assert len(res.findings) == 0


def test_end_to_end_pipeline_sanitize():
    pipeline = PrivacyPipeline()
    raw = "Can you help me solve this calculus integral? My email is john.doe@mit.edu."
    res = pipeline.process(raw)

    assert res.risk_level == RiskLevel.low
    assert res.processing_path == ProcessingPath.sanitize
    assert res.pii_detected is True
    assert "[REDACTED_EMAIL]" in res.sanitized_text
    assert "john.doe@mit.edu" not in res.sanitized_text
    assert len(res.findings) == 1
    assert res.findings[0].category == "email"


def test_end_to_end_pipeline_separate():
    pipeline = PrivacyPipeline()
    raw = "I am having a panic attack and feeling depressed. Can you explain the difference between TCP and UDP?"
    res = pipeline.process(raw)

    assert res.risk_level == RiskLevel.mixed
    assert res.processing_path == ProcessingPath.separate
    assert res.sensitive_content_detected is True
    assert "panic attack" not in res.extracted_academic_query
    assert "TCP" in res.extracted_academic_query
    assert res.redirection_message is not None


def test_end_to_end_pipeline_redirect():
    pipeline = PrivacyPipeline()
    raw = "I want to end my life, feeling suicidal and completely hopeless."
    res = pipeline.process(raw)

    assert res.risk_level == RiskLevel.high
    assert res.processing_path == ProcessingPath.redirect
    assert res.extracted_academic_query is None
    assert "[CONTENT_REMOVED_BY_PRIVACY_HANDLER]" in res.sanitized_text
    assert "988" in res.redirection_message


def test_end_to_end_pipeline_exam_stress_separate():
    pipeline = PrivacyPipeline()
    raw = "Explain DBMS normalization. I am feeling very stressed about my exams."
    res = pipeline.process(raw)

    assert res.sensitive_content_detected is True
    assert res.risk_level == RiskLevel.mixed
    assert res.processing_path == ProcessingPath.separate
    assert res.extracted_academic_query == "Explain DBMS normalization."
    assert res.sanitized_text == "Explain DBMS normalization."
    assert "stressed about my exams" not in res.extracted_academic_query
    assert res.redirection_message is not None
    assert "Notice: Impervia detected personal or sensitive information" in res.redirection_message
    assert any(f.category == "mental_health" for f in res.findings)


def test_end_to_end_pipeline_panic_attack_separate():
    pipeline = PrivacyPipeline()
    raw = "Explain DBMS normalization. I am having a panic attack about my exams."
    res = pipeline.process(raw)

    assert res.sensitive_content_detected is True
    assert res.risk_level == RiskLevel.mixed
    assert res.processing_path == ProcessingPath.separate
    assert res.extracted_academic_query == "Explain DBMS normalization."
    assert res.sanitized_text == "Explain DBMS normalization."
    assert "panic attack" not in res.extracted_academic_query


def test_end_to_end_pipeline_pure_dbms_pass_through():
    pipeline = PrivacyPipeline()
    raw = "Explain DBMS normalization."
    res = pipeline.process(raw)

    assert res.sensitive_content_detected is False
    assert res.risk_level == RiskLevel.low
    assert res.processing_path == ProcessingPath.pass_through
    assert res.extracted_academic_query == "Explain DBMS normalization."
    assert len(res.findings) == 0


def test_end_to_end_pipeline_technical_stress_pass_through():
    pipeline = PrivacyPipeline()
    raw = "Explain stress and strain in civil engineering. What is shear stress?"
    res = pipeline.process(raw)

    assert res.sensitive_content_detected is False
    assert res.risk_level == RiskLevel.low
    assert res.processing_path == ProcessingPath.pass_through
    assert res.extracted_academic_query == raw


def test_end_to_end_pipeline_pure_stress_redirect_distinct_from_crisis():
    pipeline = PrivacyPipeline()
    raw = "I am feeling very stressed about my exams and completely overwhelmed."
    res = pipeline.process(raw)

    assert res.sensitive_content_detected is True
    assert res.risk_level == RiskLevel.high
    assert res.processing_path == ProcessingPath.redirect
    assert res.extracted_academic_query is None
    # Verify ordinary stress is redirected respectfully WITHOUT 988 suicide crisis messaging
    assert "988" not in res.redirection_message
    assert "stressed or overwhelmed" in res.redirection_message
