from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MessageRole, StorageStatus

if TYPE_CHECKING:
    from app.models.academic_response import AcademicResponse
    from app.models.chat_session import ChatSession
    from app.models.privacy_analysis import PrivacyAnalysis


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "length(btrim(content)) > 0",
            name="chk_message_nonempty",
        ),
        CheckConstraint(
            "((role = 'user' AND storage_status = 'sanitized_text') OR "
            "(role = 'assistant' AND storage_status = 'assistant_response') OR "
            "(role = 'system' AND storage_status = 'system_notice'))",
            name="chk_message_role_status",
        ),
        Index("idx_messages_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(
        SAEnum(MessageRole, name="message_role", create_type=False),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    storage_status: Mapped[StorageStatus] = mapped_column(
        SAEnum(StorageStatus, name="storage_status", create_type=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")
    analyses: Mapped[list["PrivacyAnalysis"]] = relationship(
        "PrivacyAnalysis",
        back_populates="message",
    )
    input_responses: Mapped[list["AcademicResponse"]] = relationship(
        "AcademicResponse",
        foreign_keys="[AcademicResponse.input_message_id]",
        back_populates="input_message",
    )
    output_responses: Mapped[list["AcademicResponse"]] = relationship(
        "AcademicResponse",
        foreign_keys="[AcademicResponse.response_message_id]",
        back_populates="response_message",
    )
