
from sqlalchemy.orm import Session

from app.models.enums import MessageRole, ProcessingPath, StorageStatus
from app.repositories.academic_repository import academic_repository
from app.repositories.analytics_repository import analytics_repository
from app.repositories.audit_repository import audit_repository
from app.repositories.chat_repository import chat_repository
from app.repositories.privacy_repository import privacy_repository
from app.repositories.user_repository import user_repository
from app.schemas.chat import ChatProcessResponse
from app.services.academic.generation_service import academic_generation_service
from app.services.privacy.privacy_pipeline import privacy_pipeline


class ChatService:
    def process_user_input(
        self,
        db: Session,
        raw_message: str,
        user_id: int,
        session_id: int | None = None,
    ) -> ChatProcessResponse:
        # 1. Fetch user privacy settings
        settings = user_repository.get_privacy_settings(db, user_id)
        save_history = settings.save_chat_history if settings else False
        allow_analytics = settings.allow_aggregate_analytics if settings else False

        # 2. Validate or create session if history is enabled
        active_session_id = session_id
        if save_history:
            if active_session_id:
                session = chat_repository.get_session(db, active_session_id, user_id)
                if not session:
                    raise ValueError(f"Chat session {active_session_id} not found or unauthorized.")
            else:
                session = chat_repository.create_session(db, user_id)
                active_session_id = session.id

        # 3. Process through Privacy Pipeline in memory
        result = privacy_pipeline.process(raw_message)

        # 4. Formulate assistant response based on decision path
        if result.processing_path == ProcessingPath.redirect:
            assistant_text = result.redirection_message or "Your request cannot be processed due to privacy restrictions."
        elif result.processing_path == ProcessingPath.separate:
            # Generate academic response for separated query and attach privacy notice
            academic_part = result.extracted_academic_query or result.sanitized_text
            gen_resp = academic_generation_service.generate_response(academic_part)
            assistant_text = f"{result.redirection_message}\n\n{gen_resp}"
        else:
            # pass_through or sanitize
            academic_part = result.extracted_academic_query or result.sanitized_text
            assistant_text = academic_generation_service.generate_response(academic_part)

        user_message_id: int | None = None
        assistant_message_id: int | None = None

        # 5. Respect data retention & storage policy:
        # Only store messages if save_chat_history is explicitly enabled
        if save_history and active_session_id:
            # Store sanitized user message (NEVER raw un-sanitized text)
            user_msg = chat_repository.add_message(
                db,
                session_id=active_session_id,
                role=MessageRole.user,
                content=result.sanitized_text,
                storage_status=StorageStatus.sanitized_text,
            )
            user_message_id = user_msg.id

            # Store assistant response message
            asst_msg = chat_repository.add_message(
                db,
                session_id=active_session_id,
                role=MessageRole.assistant,
                content=assistant_text,
                storage_status=StorageStatus.assistant_response,
            )
            assistant_message_id = asst_msg.id

            # Log academic generation link if relevant
            if result.processing_path in {ProcessingPath.pass_through, ProcessingPath.sanitize, ProcessingPath.separate}:
                academic_repository.create_academic_response_record(
                    db,
                    user_id=user_id,
                    session_id=active_session_id,
                    input_message_id=user_message_id,
                    response_message_id=assistant_message_id,
                    model_name=academic_generation_service.MODEL_NAME,
                    latency_ms=result.processing_time_ms,
                )

        # 6. Store Privacy Analysis & Findings (linked to message_id if stored, else message_id=None)
        analysis = privacy_repository.create_analysis(
            db,
            user_id=user_id,
            session_id=active_session_id if save_history else None,
            message_id=user_message_id,  # NULL when save_history is False
            pii_detected=result.pii_detected,
            sensitive_content_detected=result.sensitive_content_detected,
            context_relevance=result.context_relevance,
            risk_level=result.risk_level,
            processing_path=result.processing_path,
            detector_version=result.detector_version,
            processing_time_ms=result.processing_time_ms,
        )

        if result.findings:
            privacy_repository.add_findings(db, analysis.id, result.findings)

        # 7. Audit log (metadata only, no raw sensitive prompts)
        audit_repository.log_event(
            db,
            event_type="chat_message_processed",
            user_id=user_id,
            session_id=active_session_id if save_history else None,
            analysis_id=analysis.id,
            details={
                "risk_level": result.risk_level.value,
                "processing_path": result.processing_path.value,
                "save_chat_history": save_history,
                "user_message_stored": save_history,
                "findings_count": len(result.findings),
            },
        )

        # 8. Record aggregate analytics ONLY if explicit consent granted
        if allow_analytics:
            analytics_repository.record_daily_analysis(
                db,
                risk_level=result.risk_level,
                processing_path=result.processing_path,
                pii_detected=result.pii_detected,
                sensitive_detected=result.sensitive_content_detected,
            )

        return ChatProcessResponse(
            session_id=active_session_id if save_history else None,
            user_message_id=user_message_id,
            user_message_stored=save_history,
            processing_path=result.processing_path,
            risk_level=result.risk_level,
            context_relevance=result.context_relevance,
            sanitized_input=result.sanitized_text,
            extracted_academic_query=result.extracted_academic_query,
            assistant_response=assistant_text,
            findings=result.findings,
            analysis_id=analysis.id,
        )


chat_service = ChatService()
