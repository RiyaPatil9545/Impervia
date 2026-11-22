from unittest.mock import MagicMock, patch

from google.genai.errors import APIError

from app.models.enums import ProcessingPath, RiskLevel
from app.models.privacy_settings import UserPrivacySettings
from app.services.academic.gemini_service import (
    ACADEMIC_TUTOR_SYSTEM_PROMPT,
    GeminiAcademicService,
    gemini_academic_service,
)
from app.services.academic.generation_service import AcademicGenerationService
from app.services.privacy.chat_service import ChatService


def _create_mock_gemini_client(response_text: str = "Detailed academic explanation."):
    """Creates a mock google-genai Client returning specified text."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = response_text
    mock_client.models.generate_content.return_value = mock_response
    return mock_client


def test_gemini_academic_question_success():
    """Verify clean academic question is answered by Gemini with correct model, prompt and token cap."""
    mock_client = _create_mock_gemini_client(
        "Dijkstra's algorithm finds the shortest path between nodes in a weighted graph."
    )
    service = GeminiAcademicService(client=mock_client)

    text, model, latency = service.generate_academic_response("Explain Dijkstra's algorithm.")

    assert "Dijkstra's algorithm" in text
    assert model == "gemini-2.5-flash"
    assert latency >= 0

    mock_client.models.generate_content.assert_called_once()
    call_kwargs = mock_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-2.5-flash"
    assert call_kwargs["contents"] == "Explain Dijkstra's algorithm."
    assert call_kwargs["config"].max_output_tokens == 800
    assert call_kwargs["config"].system_instruction == ACADEMIC_TUTOR_SYSTEM_PROMPT


def test_chat_service_with_gemini_sanitizes_pii_before_call():
    """Verify Gemini receives ONLY sanitized text with PII masked, never raw PII."""
    mock_client = _create_mock_gemini_client("To solve the calculus integral, use integration by parts.")
    gemini_academic_service.set_client(mock_client)

    try:
        db = MagicMock()
        mock_settings = UserPrivacySettings(
            user_id=1,
            save_chat_history=False,
            allow_aggregate_analytics=False,
        )

        with patch("app.repositories.user_repository.user_repository.get_privacy_settings", return_value=mock_settings):
            chat_service = ChatService()
            raw_input = (
                "Can you help me solve this calculus integral? My email is student@mit.edu and phone is 987-654-3210."
            )
            response = chat_service.process_user_input(db, raw_input, user_id=1)

            assert response.processing_path == ProcessingPath.sanitize
            assert "To solve the calculus integral" in response.assistant_response

            # Inspect the exact prompt received by Gemini
            mock_client.models.generate_content.assert_called_once()
            gemini_received_query = mock_client.models.generate_content.call_args.kwargs["contents"]

            # Must contain redaction tokens
            assert "[REDACTED_EMAIL]" in gemini_received_query
            assert "[REDACTED_PHONE]" in gemini_received_query

            # Must NEVER contain raw PII
            assert "student@mit.edu" not in gemini_received_query
            assert "987-654-3210" not in gemini_received_query
    finally:
        gemini_academic_service.set_client(None)


def test_chat_service_with_gemini_mixed_content_separation():
    """Verify sensitive emotional venting is stripped; Gemini receives ONLY the academic query."""
    mock_client = _create_mock_gemini_client(
        "TCP is connection-oriented and reliable, whereas UDP is connectionless and faster."
    )
    gemini_academic_service.set_client(mock_client)

    try:
        db = MagicMock()
        mock_settings = UserPrivacySettings(
            user_id=1,
            save_chat_history=False,
            allow_aggregate_analytics=False,
        )

        with patch("app.repositories.user_repository.user_repository.get_privacy_settings", return_value=mock_settings):
            chat_service = ChatService()
            raw_input = "I am having a panic attack and feeling depressed. Explain the difference between TCP and UDP."
            response = chat_service.process_user_input(db, raw_input, user_id=1)

            assert response.processing_path == ProcessingPath.separate
            assert response.risk_level == RiskLevel.mixed

            # Response must include privacy notice prepended
            assert "Notice: Impervia detected personal or sensitive information" in response.assistant_response
            assert "TCP is connection-oriented" in response.assistant_response

            # Gemini must receive ONLY the separated academic query
            mock_client.models.generate_content.assert_called_once()
            gemini_received_query = mock_client.models.generate_content.call_args.kwargs["contents"]

            assert "TCP and UDP" in gemini_received_query
            assert "panic attack" not in gemini_received_query
            assert "depressed" not in gemini_received_query
    finally:
        gemini_academic_service.set_client(None)


def test_chat_service_crisis_redirection_never_calls_gemini():
    """Verify high-risk crisis input redirects to helpline and NEVER invokes Gemini."""
    mock_client = _create_mock_gemini_client("This should never be generated.")
    gemini_academic_service.set_client(mock_client)

    try:
        db = MagicMock()
        mock_settings = UserPrivacySettings(
            user_id=1,
            save_chat_history=False,
            allow_aggregate_analytics=False,
        )

        with patch("app.repositories.user_repository.user_repository.get_privacy_settings", return_value=mock_settings):
            chat_service = ChatService()
            raw_input = "I want to end my life, feeling suicidal and completely hopeless."
            response = chat_service.process_user_input(db, raw_input, user_id=1)

            assert response.processing_path == ProcessingPath.redirect
            assert response.risk_level == RiskLevel.high
            assert response.extracted_academic_query is None
            assert "988" in response.assistant_response

            # Strict assertion: Gemini was NEVER called
            assert mock_client.models.generate_content.call_count == 0
    finally:
        gemini_academic_service.set_client(None)


def test_gemini_quota_exhaustion_handled_gracefully():
    """Verify 429 / quota error returns friendly message without crashing."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = APIError(
        429, {"error": {"message": "Resource exhausted: quota exceeded (code 429)"}}
    )
    service = GeminiAcademicService(client=mock_client)

    text, model, latency = service.generate_academic_response("Explain binary search trees.")

    assert "peak capacity or quota limit" in text
    assert model == "gemini-2.5-flash"


def test_gemini_timeout_handled_gracefully():
    """Verify timeout error returns friendly message without crashing."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TimeoutError("Request timed out")
    service = GeminiAcademicService(client=mock_client)

    text, model, latency = service.generate_academic_response("Explain binary search trees.")

    assert "timed out" in text
    assert model == "gemini-2.5-flash"


def test_gemini_generic_api_failure_handled_gracefully():
    """Verify generic API error returns friendly error without exposing trace."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = APIError(
        500, {"error": {"message": "Internal server error (code 500)"}}
    )
    service = GeminiAcademicService(client=mock_client)

    text, model, latency = service.generate_academic_response("Explain binary search trees.")

    assert "encountered a service error" in text
    assert model == "gemini-2.5-flash"


def test_gemini_unconfigured_api_key_fallback():
    """Verify missing API key returns clear setup notification without exception."""
    with patch("app.core.config.settings.GEMINI_API_KEY", None):
        service = GeminiAcademicService(client=None)
        text, model, latency = service.generate_academic_response("Explain quicksort.")

        assert "GEMINI_API_KEY is not configured" in text
        assert "Explain quicksort." in text


def test_generation_service_empty_or_redacted_query_guard():
    """Verify generation service guards against empty and fully redacted queries."""
    mock_client = _create_mock_gemini_client("Should not run")
    gemini_svc = GeminiAcademicService(client=mock_client)
    gen_service = AcademicGenerationService(gemini_service=gemini_svc)

    res1 = gen_service.generate_response("")
    assert "No valid academic inquiry was detected" in res1
    assert mock_client.models.generate_content.call_count == 0

    res2 = gen_service.generate_response("   ")
    assert "No valid academic inquiry was detected" in res2
    assert mock_client.models.generate_content.call_count == 0

    res3 = gen_service.generate_response("[CONTENT_REMOVED_BY_PRIVACY_HANDLER]")
    assert "No valid academic inquiry was detected" in res3
    assert mock_client.models.generate_content.call_count == 0
