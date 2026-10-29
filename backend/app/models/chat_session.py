from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.academic_response import AcademicResponse
    from app.models.chat_message import ChatMessage
    from app.models.privacy_analysis import PrivacyAnalysis
    from app.models.privacy_audit_log import PrivacyAuditLog
    from app.models.user import User


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = (
        Index("idx_sessions_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="chat_sessions")
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )
    analyses: Mapped[list["PrivacyAnalysis"]] = relationship(
        "PrivacyAnalysis",
        back_populates="session",
    )
    audit_logs: Mapped[list["PrivacyAuditLog"]] = relationship(
        "PrivacyAuditLog",
        back_populates="session",
    )
    academic_responses: Mapped[list["AcademicResponse"]] = relationship(
        "AcademicResponse",
        back_populates="session",
    )
