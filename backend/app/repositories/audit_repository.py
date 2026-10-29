from typing import Any

from sqlalchemy.orm import Session

from app.models.privacy_audit_log import PrivacyAuditLog


class AuditRepository:
    def log_event(
        self,
        db: Session,
        event_type: str,
        user_id: int | None = None,
        session_id: int | None = None,
        analysis_id: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> PrivacyAuditLog:
        """
        Store audit log event containing strictly operational metadata.
        Never stores user prompts, credentials, or sensitive text.
        """
        # Strip any disallowed keys from details if present
        clean_details: dict[str, Any] | None = None
        if details:
            clean_details = {
                k: v
                for k, v in details.items()
                if k.lower() not in {"prompt", "password", "token", "raw_text", "sensitive_text", "message"}
            }

        log_entry = PrivacyAuditLog(
            user_id=user_id,
            session_id=session_id,
            analysis_id=analysis_id,
            event_type=event_type,
            details=clean_details,
        )
        db.add(log_entry)
        db.flush()
        return log_entry


audit_repository = AuditRepository()
