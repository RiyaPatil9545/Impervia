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


def test_end_to_end_pipeline_lowercase_name_sanitized():
    pipeline = PrivacyPipeline()
    raw = "Explain Dijkstra's algorithm. My name is riya."
    res = pipeline.process(raw)

    assert res.pii_detected is True
    assert res.processing_path == ProcessingPath.sanitize
    assert "[REDACTED_NAME]" in res.sanitized_text
    assert "riya" not in res.sanitized_text.lower()
    assert "Dijkstra" in res.extracted_academic_query


def test_end_to_end_pipeline_comma_separated_mixed_content():
    pipeline = PrivacyPipeline()
    raw = "Explain DBMS normalization, I am feeling very stressed about my exams."
    res = pipeline.process(raw)

    assert res.sensitive_content_detected is True
    assert res.risk_level == RiskLevel.mixed
    assert res.processing_path == ProcessingPath.separate
    assert res.extracted_academic_query == "Explain DBMS normalization."
    assert "stressed about my exams" not in res.extracted_academic_query


def test_end_to_end_pipeline_crisis_never_bypassed_with_academic_content():
    pipeline = PrivacyPipeline()
    raw = "Explain DBMS normalization. I am feeling sucidal."
    res = pipeline.process(raw)

    assert res.risk_level == RiskLevel.high
    assert res.processing_path == ProcessingPath.redirect
    # Academic query must NEVER be extracted for severe crisis
    assert res.extracted_academic_query is None
    assert "[CONTENT_REMOVED_BY_PRIVACY_HANDLER]" in res.sanitized_text
    # International crisis resources included
    assert "findahelpline.com" in res.redirection_message
    assert "1800-599-0019" in res.redirection_message
    assert "988" in res.redirection_message


def test_end_to_end_pipeline_neutral_greeting_returns_null_academic_query():
    pipeline = PrivacyPipeline()
    raw = "Hello there, good morning!"
    res = pipeline.process(raw)

    assert res.pii_detected is False
    assert res.sensitive_content_detected is False
    assert res.risk_level == RiskLevel.low
    assert res.processing_path == ProcessingPath.pass_through
    # Non-academic greeting must return null for extracted_academic_query
    assert res.extracted_academic_query is None
    assert res.sanitized_text == "Hello there, good morning!"


def test_end_to_end_pipeline_ending_my_life_and_hurt_myself_crisis_redirect():
    """
    Regression test for: 'I am thinking about ending my life and I might hurt myself right now.'
    Must detect crisis, must NOT detect PII (no false positive 'person_name' on 'right now'),
    must assign high risk and redirect path with crisis resources.
    """
    pipeline = PrivacyPipeline()
    raw = "I am thinking about ending my life and I might hurt myself right now."
    res = pipeline.process(raw)

    assert res.pii_detected is False
    assert res.sensitive_content_detected is True
    assert res.context_relevance == RelevanceStatus.not_relevant
    assert res.risk_level == RiskLevel.high
    assert res.processing_path == ProcessingPath.redirect
    assert res.sanitized_text == "[CONTENT_REMOVED_BY_PRIVACY_HANDLER]"
    assert res.extracted_academic_query is None
    assert res.redirection_message is not None
    assert "Tele-MANAS" in res.redirection_message or "1800-599-0019" in res.redirection_message
    assert "988" in res.redirection_message
    assert "findahelpline.com" in res.redirection_message
