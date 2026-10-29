from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import GenerationStatus

if TYPE_CHECKING:
    from app.models.chat_message import ChatMessage
    from app.models.chat_session import ChatSession
    from app.models.response_source import ResponseSource
    from app.models.user import User


class AcademicResponse(Base):
    __tablename__ = "academic_responses"
    __table_args__ = (
        CheckConstraint(
            "input_message_id IS NULL OR response_message_id IS NULL OR input_message_id <> response_message_id",
            name="chk_response_distinct_messages",
        ),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="chk_response_latency",
        ),
        Index("idx_responses_user_created", "user_id", "created_at"),
        Index("idx_responses_session_created", "session_id", "created_at"),
        Index("idx_responses_input", "input_message_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    input_message_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    response_message_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generation_status: Mapped[GenerationStatus] = mapped_column(
        SAEnum(GenerationStatus, name="generation_status", create_type=False),
        default=GenerationStatus.pending,
        nullable=False,
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="academic_responses")
    session: Mapped[Optional["ChatSession"]] = relationship("ChatSession", back_populates="academic_responses")
    input_message: Mapped[Optional["ChatMessage"]] = relationship(
        "ChatMessage",
        foreign_keys=[input_message_id],
        back_populates="input_responses",
    )
    response_message: Mapped[Optional["ChatMessage"]] = relationship(
        "ChatMessage",
        foreign_keys=[response_message_id],
        back_populates="output_responses",
    )
    sources: Mapped[list["ResponseSource"]] = relationship(
        "ResponseSource",
        back_populates="academic_response",
        cascade="all, delete-orphan",
    )
