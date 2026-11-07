import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.ml.relevance_detection.detector import RelevanceAnalysisResult
from app.ml.sensitive_content.detector import SensitiveSpan
from app.ml.slm.client import LocalSLMClient
from app.ml.slm.hybrid_analyzer import HybridAnalyzer
from app.ml.slm.schemas import SLMAnalysisResult, SLMContextAnalysis
from app.models.enums import ProcessingPath, RelevanceStatus, RiskLevel
from app.services.privacy.privacy_pipeline import PrivacyPipeline


def test_slm_client_offline_fallback():
    client = LocalSLMClient(endpoint="http://127.0.0.1:99999", enabled=True)
    res = client.analyze("Explain binary search trees.")
    assert res.is_available is False
    assert res.analysis is None
    assert "offline" in res.error_message or "failed" in res.error_message.lower()


def test_slm_client_successful_parsing():
    client = LocalSLMClient(endpoint="http://127.0.0.1:11434", enabled=True)
    mock_json = {
        "has_academic_intent": True,
        "academic_score": 0.95,
        "primary_academic_domain": "computer_science",
        "has_sensitive_content": False,
        "sensitive_category": None,
        "distress_severity": None,
        "is_crisis": False,
        "extracted_academic_query": "Explain binary search trees.",
        "extracted_sensitive_disclosure": None,
        "reasoning": "Standard computer science query.",
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": json.dumps(mock_json)}

    with patch("httpx.Client.post", return_value=mock_resp), patch.object(client, "is_healthy", return_value=True):
        res = client.analyze("Explain binary search trees.")
        assert res.is_available is True
        assert res.analysis is not None
        assert res.analysis.has_academic_intent is True
        assert res.analysis.primary_academic_domain == "computer_science"


def test_hybrid_analyzer_augments_subtle_distress_missed_by_rules():
    """
    Subtle distress without keyword matches is caught by the SLM and merged
    into sensitive_spans so mixed-content separation is triggered.
    """
    mock_slm_client = MagicMock()
    mock_slm_client.analyze.return_value = SLMAnalysisResult(
        is_available=True,
        analysis=SLMContextAnalysis(
            has_academic_intent=True,
            academic_score=0.9,
            primary_academic_domain="computer_science",
            has_sensitive_content=True,
            sensitive_category="mental_health",
            distress_severity="medium",
            is_crisis=False,
            extracted_academic_query="How does quicksort work?",
            extracted_sensitive_disclosure="I feel like my whole world is collapsing around me",
            reasoning="Student expressed deep despair alongside an algorithm question.",
        ),
    )

    analyzer = HybridAnalyzer(slm_client=mock_slm_client)
    raw = "How does quicksort work? I feel like my whole world is collapsing around me."

    rule_sens = []  # Rule detector missed this subtle wording
    rule_rel = RelevanceAnalysisResult(
        status=RelevanceStatus.relevant,
        academic_score=0.8,
        has_academic_intent=True,
        academic_text="How does quicksort work?",
        non_academic_text=None,
    )

    merged_sens, merged_rel, _ = analyzer.analyze_context(raw, [], rule_sens, rule_rel)

    assert len(merged_sens) == 1
    assert merged_sens[0].category == "mental_health"
    assert merged_sens[0].severity == "medium"
    assert merged_rel.status == RelevanceStatus.mixed


def test_hybrid_analyzer_strict_non_downgrade_of_crisis():
    """
    Safety Invariant: If Python rule-based detectors flag acute crisis (suicidal intent),
    the SLM can NEVER downgrade it to medium or safe.
    """
    mock_slm_client = MagicMock()
    # Malicious or flawed SLM output claiming no crisis
    mock_slm_client.analyze.return_value = SLMAnalysisResult(
        is_available=True,
        analysis=SLMContextAnalysis(
            has_academic_intent=False,
            academic_score=0.0,
            primary_academic_domain=None,
            has_sensitive_content=False,  # SLM hallucinating safety
            sensitive_category=None,
            distress_severity=None,
            is_crisis=False,
            extracted_academic_query=None,
            extracted_sensitive_disclosure=None,
            reasoning="Safe conversation.",
        ),
    )

    analyzer = HybridAnalyzer(slm_client=mock_slm_client)
    raw = "I want to end my life, feeling suicidal."

    rule_sens = [
        SensitiveSpan(
            category="mental_health",
            start=0,
            end=len(raw),
            text=raw,
            confidence=Decimal("0.95"),
            severity="high",
        )
    ]
    rule_rel = RelevanceAnalysisResult(
        status=RelevanceStatus.not_relevant,
        academic_score=0.0,
        has_academic_intent=False,
        academic_text=None,
        non_academic_text=raw,
    )

    merged_sens, merged_rel, _ = analyzer.analyze_context(raw, [], rule_sens, rule_rel)

    # Invariant holds: high crisis remains present and high severity!
    assert len(merged_sens) >= 1
    assert any(s.severity == "high" for s in merged_sens)


def test_end_to_end_hybrid_pipeline_with_slm():
    mock_slm_client = MagicMock()
    mock_slm_client.analyze.return_value = SLMAnalysisResult(
        is_available=True,
        model_used="qwen2.5:1.5b",
        analysis=SLMContextAnalysis(
            has_academic_intent=True,
            academic_score=0.95,
            primary_academic_domain="computer_science",
            has_sensitive_content=True,
            sensitive_category="mental_health",
            distress_severity="medium",
            is_crisis=False,
            extracted_academic_query="Explain Dijkstra's algorithm.",
            extracted_sensitive_disclosure="I feel like my whole world is falling apart",
            reasoning="Mixed academic query with subtle emotional distress.",
        ),
    )

    hybrid = HybridAnalyzer(slm_client=mock_slm_client)
    pipeline = PrivacyPipeline(hybrid_engine=hybrid)

    raw = "Explain Dijkstra's algorithm. I feel like my whole world is falling apart."
    res = pipeline.process(raw)

    assert res.sensitive_content_detected is True
    assert res.risk_level == RiskLevel.mixed
    assert res.processing_path == ProcessingPath.separate
    assert "Dijkstra" in res.extracted_academic_query
    assert "falling apart" not in res.extracted_academic_query
    assert "impervia-hybrid-v2.0" in res.detector_version


def test_pre_sanitized_pii_before_slm():
    """
    Priority 1 Fix 1: Raw student PII (email, phone, ID) must NEVER be sent
    to the Ollama SLM payload. Text must be pre-sanitized in Python memory first.
    """
    mock_slm_client = MagicMock()
    mock_slm_client.analyze.return_value = SLMAnalysisResult(
        is_available=True,
        analysis=SLMContextAnalysis(
            has_academic_intent=True,
            academic_score=0.9,
            primary_academic_domain="computer_science",
            has_sensitive_content=False,
            sensitive_category=None,
            distress_severity=None,
            is_crisis=False,
            extracted_academic_query="Explain quicksort",
            extracted_sensitive_disclosure=None,
            reasoning="Academic question with contact info.",
        ),
    )

    hybrid = HybridAnalyzer(slm_client=mock_slm_client)
    pipeline = PrivacyPipeline(hybrid_engine=hybrid)

    raw_input = "My email is student123@mit.edu and phone is +1-555-019-2834. Explain quicksort."
    pipeline.process(raw_input)

    # Check what was passed to slm_client.analyze
    assert mock_slm_client.analyze.called
    called_text = mock_slm_client.analyze.call_args[0][0]

    # Raw PII must NOT appear in the text sent to SLM
    assert "student123@mit.edu" not in called_text
    assert "+1-555-019-2834" not in called_text
    assert "555-019-2834" not in called_text
    # Redacted placeholders must appear
    assert "[REDACTED_EMAIL]" in called_text
    assert "[REDACTED_PHONE]" in called_text
    assert "Explain quicksort" in called_text


def test_disclosure_matching_fallback_preserves_academic_query():
    """
    Priority 1 Fix 4: When SLM extracted_sensitive_disclosure does not match verbatim,
    disclosure span alignment fallback isolates the personal clause and does NOT redact
    the entire message, preserving the academic query.
    """
    mock_slm_client = MagicMock()
    # SLM returns paraphrased/summarized disclosure text that is NOT a verbatim substring
    mock_slm_client.analyze.return_value = SLMAnalysisResult(
        is_available=True,
        analysis=SLMContextAnalysis(
            has_academic_intent=True,
            academic_score=0.9,
            primary_academic_domain="computer_science",
            has_sensitive_content=True,
            sensitive_category="mental_health",
            distress_severity="medium",
            is_crisis=False,
            extracted_academic_query="What is the time complexity of merge sort?",
            # Paraphrased summary by SLM (not verbatim in clean_text)
            extracted_sensitive_disclosure="having panic attacks and feeling hopeless",
            reasoning="Student asks merge sort complexity and mentions panic attack episodes.",
        ),
    )

    hybrid = HybridAnalyzer(slm_client=mock_slm_client)
    pipeline = PrivacyPipeline(hybrid_engine=hybrid)

    raw = "What is the time complexity of merge sort? I have panic attacks every evening."
    result = pipeline.process(raw)

    assert result.sensitive_content_detected is True
    assert result.processing_path == ProcessingPath.separate
    assert result.extracted_academic_query is not None
    # Academic query must be preserved!
    assert "merge sort" in result.extracted_academic_query
    # Sensitive disclosure must not be in the academic query
    assert "panic" not in result.extracted_academic_query


def test_secure_slm_error_logging_redacts_response_body(caplog):
    """
    Priority 1 Fix 2: SLM client logs must never leak response bodies or student text.
    Only safe metadata (HTTP status code, exception category) is logged.
    """
    import logging
    client = LocalSLMClient(endpoint="http://127.0.0.1:11434", enabled=True)

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error with sensitive user input: john@example.com"

    with patch("httpx.Client.post", return_value=mock_resp), patch.object(client, "is_healthy", return_value=True), caplog.at_level(logging.WARNING):
        res = client.analyze("student message containing john@example.com")
        assert res.is_available is False
        assert res.error_message == "HTTP 500"

        # caplog must not contain the sensitive response body or user input
        log_text = caplog.text
        assert "john@example.com" not in log_text
        assert "HTTP 500" in log_text


def test_slm_warm_up_safety():
    """
    Priority 2 Fix 5: Safe warm-up should never raise exceptions and return False
    gracefully if offline.
    """
    client = LocalSLMClient(endpoint="http://127.0.0.1:99999", enabled=True)
    # Offline endpoint: warm_up must return False without throwing
    res = client.warm_up()
    assert res is False


def test_slm_schema_coerces_null_academic_score_and_normalizes_category():
    """Fix 1 & 3: academic_score=None coerced to 0.0, 'suicide' normalized to 'mental_health'."""
    raw_payload = {
        "has_academic_intent": False,
        "academic_score": None,
        "primary_academic_domain": None,
        "has_sensitive_content": True,
        "sensitive_category": "suicide",
        "distress_severity": "high",
        "is_crisis": True,
        "extracted_academic_query": None,
        "extracted_sensitive_disclosure": "ending my life",
        "reasoning": "Acute crisis detected.",
    }
    analysis = SLMContextAnalysis.model_validate(raw_payload)
    assert analysis.academic_score == 0.0
    assert analysis.sensitive_category == "mental_health"
    assert analysis.is_crisis is True


def test_hybrid_analyzer_merges_distress_severity_when_has_sensitive_is_false():
    """Fix 2: meaningful distress disclosures are merged even if has_sensitive_content is false."""
    mock_slm_client = MagicMock()
    mock_slm_client.analyze.return_value = SLMAnalysisResult(
        is_available=True,
        analysis=SLMContextAnalysis(
            has_academic_intent=True,
            academic_score=0.8,
            primary_academic_domain="Database Management Systems",
            has_sensitive_content=False,  # Qwen thought exam stress was normal academic concern
            sensitive_category=None,
            distress_severity="medium",
            is_crisis=False,
            extracted_academic_query="Explain DBMS normalization.",
            extracted_sensitive_disclosure="I am feeling very stressed about my exams.",
            reasoning="Exam stress disclosure.",
        ),
    )

    analyzer = HybridAnalyzer(slm_client=mock_slm_client)
    raw = "Explain DBMS normalization. I am feeling very stressed about my exams."

    rule_sens = []
    rule_rel = RelevanceAnalysisResult(
        status=RelevanceStatus.relevant,
        academic_score=0.8,
        has_academic_intent=True,
        academic_text="Explain DBMS normalization.",
        non_academic_text=None,
    )

    merged_sens, merged_rel, _ = analyzer.analyze_context(raw, [], rule_sens, rule_rel)

    assert len(merged_sens) == 1
    assert merged_sens[0].category == "mental_health"
    assert merged_sens[0].severity == "medium"
    assert merged_rel.status == RelevanceStatus.mixed


def test_ensure_service_running_reuses_existing_instance():
    """Verify that when Ollama is already running, ensure_service_running reuses it without spawning duplicate processes."""
    client = LocalSLMClient(enabled=True)
    with patch.object(client, "is_healthy", return_value=True), patch("subprocess.Popen") as mock_popen:
        assert client.ensure_service_running() is True
        mock_popen.assert_not_called()


def test_ensure_service_running_respects_disabled_and_auto_start_flags():
    """Verify that ensure_service_running exits cleanly if SLM is disabled or auto_start is off."""
    client_disabled = LocalSLMClient(enabled=False)
    assert client_disabled.ensure_service_running() is False

    client_no_autostart = LocalSLMClient(enabled=True, auto_start=False)
    with patch.object(client_no_autostart, "is_healthy", return_value=False):
        assert client_no_autostart.ensure_service_running() is False



