from unittest.mock import MagicMock, patch

from google.genai import errors

from app.models.enums import ProcessingPath, RiskLevel
from app.models.privacy_settings import UserPrivacySettings
from app.services.academic.gemini_service import GeminiAcademicService
from app.services.academic.generation_service import AcademicGenerationService
from app.services.privacy.chat_service import ChatService


def test_gemini_service_successful_academic_response():
    """Verify GeminiAcademicService returns clean academic response using GenerateContentConfig."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Binary search is an efficient algorithm with O(log n) time complexity."
    mock_client.models.generate_content.return_value = mock_response

    service = GeminiAcademicService(
        api_key="AIzaSyFakeKeyForTesting123",
        model_name="gemini-2.5-flash",
        max_output_tokens=800,
        temperature=0.3,
        client=mock_client,
    )

    query = "Explain binary search algorithm."
    result = service.generate_academic_response(query)

    assert "Binary search is an efficient algorithm" in result
    mock_client.models.generate_content.assert_called_once()
    call_kwargs = mock_client.models.generate_content.call_args[1]
    assert call_kwargs["model"] == "gemini-2.5-flash"
    assert call_kwargs["contents"] == query
    assert call_kwargs["config"].max_output_tokens == 800
    assert call_kwargs["config"].temperature == 0.3
    assert "Academic Tutor" in call_kwargs["config"].system_instruction


def test_gemini_service_handles_sanitized_pii_query():
    """Verify Gemini receives ONLY sanitized text containing redaction placeholders."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Dijkstra's algorithm finds the shortest path in a weighted graph."
    mock_client.models.generate_content.return_value = mock_response

    service = GeminiAcademicService(
        api_key="AIzaSyFakeKeyForTesting123",
        client=mock_client,
    )

    sanitized_query = "Student [REDACTED_NAME] asks: Explain Dijkstra's algorithm."
    result = service.generate_academic_response(sanitized_query)

    assert "Dijkstra's algorithm" in result
    call_kwargs = mock_client.models.generate_content.call_args[1]
    assert call_kwargs["contents"] == sanitized_query
    # Ensure unmasked PII is absent
    assert "john" not in call_kwargs["contents"].lower()


def test_gemini_service_handles_api_error_gracefully():
    """Verify Gemini API errors are caught and return user-friendly messages without crashing."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = errors.APIError(500, {"error": {"message": "Internal server error"}})

    service = GeminiAcademicService(
        api_key="AIzaSyFakeKeyForTesting123",
        client=mock_client,
    )

    result = service.generate_academic_response("Explain QuickSort.")
    assert "The Academic AI service encountered an issue" in result


def test_gemini_service_handles_quota_error():
    """Verify 429 quota exhaustion is converted into a polite retry message."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = errors.APIError(429, {"error": {"message": "RESOURCE_EXHAUSTED"}})

    service = GeminiAcademicService(
        api_key="AIzaSyFakeKeyForTesting123",
        client=mock_client,
    )

    result = service.generate_academic_response("Explain MergeSort.")
    assert "high demand or rate limits" in result


def test_gemini_service_handles_timeout():
    """Verify network timeouts return a clear timeout message."""
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = TimeoutError("Request timed out")

    service = GeminiAcademicService(
        api_key="AIzaSyFakeKeyForTesting123",
        client=mock_client,
    )

    result = service.generate_academic_response("Explain Graph Traversal.")
    assert "timed out while generating your explanation" in result


def test_gemini_service_missing_api_key():
    """Verify missing or placeholder API key returns configuration message without crashing."""
    service = GeminiAcademicService(api_key="", client=None)
    result = service.generate_academic_response("Explain Calculus.")
    assert "API key not configured" in result


def test_gemini_service_empty_input():
    """Verify empty academic queries return immediately without calling the Gemini API."""
    mock_client = MagicMock()
    service = GeminiAcademicService(api_key="AIzaSyFakeKeyForTesting123", client=mock_client)

    result = service.generate_academic_response("   ")
    assert result == "No academic question was provided for processing."
    mock_client.models.generate_content.assert_not_called()


def test_generation_service_delegates_to_gemini():
    """Verify AcademicGenerationService coordinates with Gemini and returns its model name."""
    mock_gemini = MagicMock(spec=GeminiAcademicService)
    mock_gemini.model_name = "gemini-2.5-flash"
    mock_gemini.generate_academic_response.return_value = "Detailed DBMS normalization explanation."

    generation_svc = AcademicGenerationService(llm_service=mock_gemini)

    assert generation_svc.MODEL_NAME == "gemini-2.5-flash"
    res = generation_svc.generate_response("Explain 3NF.")
    assert res == "Detailed DBMS normalization explanation."
    mock_gemini.generate_academic_response.assert_called_once_with("Explain 3NF.")


def test_chat_service_academic_flow_with_gemini():
    """End-to-end integration: Academic question reaches Gemini and stores model name in DB."""
    db = MagicMock()
    chat_svc = ChatService()

    # Mock user privacy settings (save history=True to verify DB recording)
    mock_settings = UserPrivacySettings(
        user_id=1,
        save_chat_history=True,
        allow_aggregate_analytics=False,
    )

    from app.repositories.academic_repository import academic_repository
    from app.repositories.audit_repository import audit_repository
    from app.repositories.chat_repository import chat_repository
    from app.repositories.privacy_repository import privacy_repository
    from app.repositories.user_repository import user_repository

    user_repository.get_privacy_settings = MagicMock(return_value=mock_settings)

    mock_session = MagicMock()
    mock_session.id = 10
    chat_repository.create_session = MagicMock(return_value=mock_session)

    mock_user_msg = MagicMock()
    mock_user_msg.id = 101
    mock_asst_msg = MagicMock()
    mock_asst_msg.id = 102
    chat_repository.add_message = MagicMock(side_effect=[mock_user_msg, mock_asst_msg])

    mock_analysis = MagicMock()
    mock_analysis.id = 201
    privacy_repository.create_analysis = MagicMock(return_value=mock_analysis)
    privacy_repository.add_findings = MagicMock()
    academic_repository.create_academic_response_record = MagicMock()
    audit_repository.log_event = MagicMock()

    with patch("app.services.privacy.chat_service.academic_generation_service.generate_response", return_value="QuickSort divides the array around a pivot.") as mock_gen:
        resp = chat_svc.process_user_input(
            db=db,
            raw_message="Explain QuickSort algorithm.",
            user_id=1,
        )

        assert resp.processing_path == ProcessingPath.pass_through
        assert resp.risk_level == RiskLevel.low
        assert "QuickSort divides the array around a pivot" in resp.assistant_response
        mock_gen.assert_called_once_with("Explain QuickSort algorithm.")

        # Academic response DB record logged
        academic_repository.create_academic_response_record.assert_called_once()
        record_kwargs = academic_repository.create_academic_response_record.call_args[1]
        assert record_kwargs["user_id"] == 1
        assert record_kwargs["input_message_id"] == 101
        assert record_kwargs["response_message_id"] == 102
        assert "gemini" in record_kwargs["model_name"].lower()


def test_chat_service_mixed_content_separation_only_sends_academic_to_gemini():
    """Verify mixed content separates sensitive part: Gemini receives ONLY the academic question."""
    db = MagicMock()
    chat_svc = ChatService()

    from app.repositories.academic_repository import academic_repository
    from app.repositories.audit_repository import audit_repository
    from app.repositories.chat_repository import chat_repository
    from app.repositories.privacy_repository import privacy_repository
    from app.repositories.user_repository import user_repository

    user_repository.get_privacy_settings = MagicMock(return_value=None)
    chat_repository.add_message = MagicMock()
    mock_analysis = MagicMock()
    mock_analysis.id = 301
    privacy_repository.create_analysis = MagicMock(return_value=mock_analysis)
    privacy_repository.add_findings = MagicMock()
    academic_repository.create_academic_response_record = MagicMock()
    audit_repository.log_event = MagicMock()

    raw_input = "Explain DBMS normalization. I am feeling very stressed about my exams."

    with patch("app.services.privacy.chat_service.academic_generation_service.generate_response", return_value="DBMS normalization reduces data redundancy.") as mock_gen:
        resp = chat_svc.process_user_input(
            db=db,
            raw_message=raw_input,
            user_id=1,
        )

        assert resp.processing_path == ProcessingPath.separate
        assert resp.risk_level == RiskLevel.mixed
        # Gemini must ONLY receive the academic part!
        mock_gen.assert_called_once_with("Explain DBMS normalization.")
        # Notice must accompany the response
        assert "Notice: Impervia detected personal or sensitive information" in resp.assistant_response
        assert "DBMS normalization reduces data redundancy" in resp.assistant_response
        # Sensitive personal venting must NOT be present in assistant output
        assert "stressed about my exams" not in resp.assistant_response


def test_chat_service_crisis_redirection_never_calls_gemini():
    """Verify acute crisis inputs trigger redirect and NEVER invoke Gemini."""
    db = MagicMock()
    chat_svc = ChatService()

    from app.repositories.academic_repository import academic_repository
    from app.repositories.audit_repository import audit_repository
    from app.repositories.chat_repository import chat_repository
    from app.repositories.privacy_repository import privacy_repository
    from app.repositories.user_repository import user_repository

    user_repository.get_privacy_settings = MagicMock(return_value=None)
    chat_repository.add_message = MagicMock()
    mock_analysis = MagicMock()
    mock_analysis.id = 401
    privacy_repository.create_analysis = MagicMock(return_value=mock_analysis)
    privacy_repository.add_findings = MagicMock()
    academic_repository.create_academic_response_record = MagicMock()
    audit_repository.log_event = MagicMock()

    raw_crisis = "I am thinking about ending my life and I might hurt myself right now."

    with patch("app.services.privacy.chat_service.academic_generation_service.generate_response") as mock_gen:
        resp = chat_svc.process_user_input(
            db=db,
            raw_message=raw_crisis,
            user_id=1,
        )

        assert resp.processing_path == ProcessingPath.redirect
        assert resp.risk_level == RiskLevel.high
        # Gemini must NEVER be called!
        mock_gen.assert_not_called()
        academic_repository.create_academic_response_record.assert_not_called()
        # Crisis helpline resources returned
        assert "Tele-MANAS" in resp.assistant_response or "1800-599-0019" in resp.assistant_response
        assert "988" in resp.assistant_response


def test_chat_service_neutral_greeting_never_calls_gemini():
    """Verify non-academic messages (greetings) do not trigger Gemini calls."""
    db = MagicMock()
    chat_svc = ChatService()

    from app.repositories.academic_repository import academic_repository
    from app.repositories.audit_repository import audit_repository
    from app.repositories.chat_repository import chat_repository
    from app.repositories.privacy_repository import privacy_repository
    from app.repositories.user_repository import user_repository

    user_repository.get_privacy_settings = MagicMock(return_value=None)
    chat_repository.add_message = MagicMock()
    mock_analysis = MagicMock()
    mock_analysis.id = 501
    privacy_repository.create_analysis = MagicMock(return_value=mock_analysis)
    privacy_repository.add_findings = MagicMock()
    academic_repository.create_academic_response_record = MagicMock()
    audit_repository.log_event = MagicMock()

    raw_greeting = "Hello there, good morning!"

    with patch("app.services.privacy.chat_service.academic_generation_service.generate_response") as mock_gen:
        resp = chat_svc.process_user_input(
            db=db,
            raw_message=raw_greeting,
            user_id=1,
        )

        assert resp.processing_path == ProcessingPath.pass_through
        assert resp.extracted_academic_query is None
        # Gemini must NOT be called for non-academic greeting
        mock_gen.assert_not_called()
        assert "Impervia is ready to assist with your academic coursework" in resp.assistant_response
