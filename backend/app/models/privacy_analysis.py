from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
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
from app.models.enums import ProcessingPath, RelevanceStatus, RiskLevel

if TYPE_CHECKING:
    from app.models.chat_message import ChatMessage
    from app.models.chat_session import ChatSession
    from app.models.privacy_audit_log import PrivacyAuditLog
    from app.models.privacy_finding import PrivacyFinding
    from app.models.user import User


class PrivacyAnalysis(Base):
    __tablename__ = "privacy_analyses"
    __table_args__ = (
        CheckConstraint(
            "processing_time_ms IS NULL OR processing_time_ms >= 0",
            name="chk_analysis_processing_time",
        ),
        Index("idx_analyses_user_created", "user_id", "created_at"),
        Index("idx_analyses_session_created", "session_id", "created_at"),
        Index("idx_analyses_message_created", "message_id", "created_at"),
        Index("idx_analyses_created_risk", "created_at", "risk_level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    session_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    message_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    pii_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sensitive_content_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    context_relevance: Mapped[RelevanceStatus] = mapped_column(
        SAEnum(RelevanceStatus, name="relevance_status", create_type=False),
        nullable=False,
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        SAEnum(RiskLevel, name="risk_level", create_type=False),
        nullable=False,
    )
    processing_path: Mapped[ProcessingPath] = mapped_column(
        SAEnum(ProcessingPath, name="processing_path", create_type=False),
        nullable=False,
    )
    detector_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    findings: Mapped[list["PrivacyFinding"]] = relationship(
        "PrivacyFinding",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    user: Mapped[Optional["User"]] = relationship("User", back_populates="privacy_analyses")
    session: Mapped[Optional["ChatSession"]] = relationship("ChatSession", back_populates="analyses")
    message: Mapped[Optional["ChatMessage"]] = relationship("ChatMessage", back_populates="analyses")
    audit_logs: Mapped[list["PrivacyAuditLog"]] = relationship(
        "PrivacyAuditLog",
        back_populates="analysis",
    )
