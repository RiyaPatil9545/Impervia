from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.academic_response import AcademicResponse
    from app.models.chat_session import ChatSession
    from app.models.privacy_analysis import PrivacyAnalysis
    from app.models.privacy_audit_log import PrivacyAuditLog
    from app.models.privacy_settings import UserPrivacySettings


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    privacy_settings: Mapped[Optional["UserPrivacySettings"]] = relationship(
        "UserPrivacySettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    privacy_analyses: Mapped[list["PrivacyAnalysis"]] = relationship(
        "PrivacyAnalysis",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[list["PrivacyAuditLog"]] = relationship(
        "PrivacyAuditLog",
        back_populates="user",
    )
    academic_responses: Mapped[list["AcademicResponse"]] = relationship(
        "AcademicResponse",
        back_populates="user",
    )
