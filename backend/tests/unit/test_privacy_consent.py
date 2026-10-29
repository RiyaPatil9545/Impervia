from unittest.mock import MagicMock

from app.models.enums import MessageRole, ProcessingPath, RiskLevel, StorageStatus
from app.models.privacy_settings import UserPrivacySettings
from app.repositories.chat_repository import ChatRepository
from app.services.analytics.aggregation_service import AggregationService
from app.services.privacy.chat_service import ChatService


def test_chat_message_role_constraint_enforcement():
    repo = ChatRepository()
    db = MagicMock()

    # User message cannot have assistant_response status
    try:
        repo.add_message(
            db,
            session_id=1,
            role=MessageRole.user,
            content="Hello",
            storage_status=StorageStatus.assistant_response,
        )
        assert False, "Expected ValueError on role-status mismatch"
    except ValueError as e:
        assert "User messages may only be stored as sanitized_text" in str(e)


def test_chat_service_respects_no_history_consent():
    """
    When save_chat_history is False, chat_messages rows must NEVER be stored,
    and PrivacyAnalysis message_id must be None.
    """
    db = MagicMock()
    service = ChatService()

    # Mock user privacy settings with save_chat_history=False
    mock_settings = UserPrivacySettings(
        user_id=1,
        save_chat_history=False,
        allow_aggregate_analytics=False,
    )

    from app.repositories.user_repository import user_repository
    user_repository.get_privacy_settings = MagicMock(return_value=mock_settings)

    from app.repositories.chat_repository import chat_repository
    chat_repository.add_message = MagicMock()
    chat_repository.create_session = MagicMock()

    from app.repositories.privacy_repository import privacy_repository
    mock_analysis = MagicMock()
    mock_analysis.id = 101
    privacy_repository.create_analysis = MagicMock(return_value=mock_analysis)
    privacy_repository.add_findings = MagicMock()

    from app.repositories.audit_repository import audit_repository
    audit_repository.log_event = MagicMock()

    response = service.process_user_input(
        db=db,
        raw_message="Can you explain bubble sort?",
        user_id=1,
        session_id=None,
    )

    # Assertions
    assert response.user_message_stored is False
    assert response.user_message_id is None
    # ChatRepository.add_message should NEVER have been called!
    assert chat_repository.add_message.call_count == 0
    # Privacy analysis was created with message_id=None
    created_call_kwargs = privacy_repository.create_analysis.call_args[1]
    assert created_call_kwargs["message_id"] is None


def test_aggregation_service_requires_explicit_consent():
    """
    Ensure analytics metrics are not updated unless allow_aggregate_analytics is explicitly True.
    """
    service = AggregationService()
    db = MagicMock()

    # Case 1: user_id is None (unauthenticated) -> False
    assert service.record_analysis_if_consented(
        db, user_id=None, risk_level=RiskLevel.low, processing_path=ProcessingPath.pass_through,
        pii_detected=False, sensitive_detected=False
    ) is False

    # Case 2: user_id present but allow_aggregate_analytics is False
    from app.repositories.user_repository import user_repository
    mock_settings = UserPrivacySettings(
        user_id=42,
        allow_aggregate_analytics=False,
    )
    user_repository.get_privacy_settings = MagicMock(return_value=mock_settings)

    assert service.record_analysis_if_consented(
        db, user_id=42, risk_level=RiskLevel.low, processing_path=ProcessingPath.pass_through,
        pii_detected=False, sensitive_detected=False
    ) is False

    # Case 3: user explicitly gave consent
    mock_settings.allow_aggregate_analytics = True
    from app.repositories.analytics_repository import analytics_repository
    analytics_repository.record_daily_analysis = MagicMock()

    assert service.record_analysis_if_consented(
        db, user_id=42, risk_level=RiskLevel.low, processing_path=ProcessingPath.pass_through,
        pii_detected=False, sensitive_detected=False
    ) is True
    assert analytics_repository.record_daily_analysis.call_count == 1
