from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.chat_message import ChatMessage
from app.models.chat_session import ChatSession
from app.models.enums import MessageRole, StorageStatus


class ChatRepository:
    def create_session(self, db: Session, user_id: int) -> ChatSession:
        session = ChatSession(
            user_id=user_id,
            is_archived=False,
        )
        db.add(session)
        db.flush()
        return session

    def get_session(self, db: Session, session_id: int, user_id: int) -> ChatSession | None:
        return db.scalar(
            select(ChatSession).where(
                ChatSession.id == session_id,
                ChatSession.user_id == user_id,
            )
        )

    def list_sessions(
        self, db: Session, user_id: int, limit: int = 50, offset: int = 0
    ) -> list[ChatSession]:
        return list(
            db.scalars(
                select(ChatSession)
                .where(ChatSession.user_id == user_id, ChatSession.is_archived.is_(False))
                .order_by(ChatSession.updated_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )

    def archive_session(self, db: Session, session_id: int, user_id: int) -> bool:
        session = self.get_session(db, session_id, user_id)
        if not session:
            return False
        session.is_archived = True
        session.updated_at = datetime.now(UTC)
        db.flush()
        return True

    def delete_session(self, db: Session, session_id: int, user_id: int) -> bool:
        session = self.get_session(db, session_id, user_id)
        if not session:
            return False
        db.delete(session)
        db.flush()
        return True

    def add_message(
        self,
        db: Session,
        session_id: int,
        role: MessageRole,
        content: str,
        storage_status: StorageStatus,
    ) -> ChatMessage:
        """
        Store a message only when permitted. Content MUST be sanitized.
        Enforces database check constraint: role-to-status alignment.
        """
        content = content.strip()
        if not content:
            raise ValueError("Message content cannot be empty.")

        # Validate database constraint chk_message_role_status
        if role == MessageRole.user and storage_status != StorageStatus.sanitized_text:
            raise ValueError("User messages may only be stored as sanitized_text.")
        if role == MessageRole.assistant and storage_status != StorageStatus.assistant_response:
            raise ValueError("Assistant messages must have assistant_response status.")
        if role == MessageRole.system and storage_status != StorageStatus.system_notice:
            raise ValueError("System messages must have system_notice status.")

        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            storage_status=storage_status,
        )
        db.add(message)

        # Update session updated_at timestamp
        session = db.scalar(select(ChatSession).where(ChatSession.id == session_id))
        if session:
            session.updated_at = datetime.now(UTC)

        db.flush()
        return message

    def list_messages(
        self, db: Session, session_id: int, user_id: int
    ) -> list[ChatMessage]:
        session = self.get_session(db, session_id, user_id)
        if not session:
            return []
        return list(
            db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.asc())
            ).all()
        )

    def purge_messages_by_retention(
        self, db: Session, user_id: int, retention_days: int
    ) -> int:
        """
        Purge chat messages for user older than retention_days.
        """
        if retention_days <= 0:
            return 0
        cutoff_date = datetime.now(UTC) - timedelta(days=retention_days)
        subquery = (
            select(ChatSession.id)
            .where(ChatSession.user_id == user_id)
            .scalar_subquery()
        )
        result = db.execute(
            delete(ChatMessage).where(
                ChatMessage.session_id.in_(subquery),
                ChatMessage.created_at < cutoff_date,
            )
        )
        db.flush()
        return result.rowcount

    def purge_all_user_history(self, db: Session, user_id: int) -> int:
        """
        Explicitly wipe all chat messages and sessions for user upon request.
        """
        subquery = (
            select(ChatSession.id)
            .where(ChatSession.user_id == user_id)
            .scalar_subquery()
        )
        msg_result = db.execute(
            delete(ChatMessage).where(ChatMessage.session_id.in_(subquery))
        )
        db.execute(delete(ChatSession).where(ChatSession.user_id == user_id))
        db.flush()
        return msg_result.rowcount


chat_repository = ChatRepository()
