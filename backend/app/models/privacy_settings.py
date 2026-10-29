from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserPrivacySettings(Base):
    __tablename__ = "user_privacy_settings"
    __table_args__ = (
        CheckConstraint(
            "retention_days IS NULL OR (retention_days >= 1 AND retention_days <= 3650)",
            name="chk_retention_days",
        ),
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    save_chat_history: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_aggregate_analytics: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    warn_before_high_risk: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    retention_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="privacy_settings")
