from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PrivacyDailyMetric(Base):
    __tablename__ = "privacy_daily_metrics"
    __table_args__ = (
        CheckConstraint("total_analyses >= 0", name="chk_metrics_total"),
        CheckConstraint(
            "low_risk_count >= 0 AND mixed_risk_count >= 0 AND high_risk_count >= 0",
            name="chk_metrics_risk_counts",
        ),
        CheckConstraint(
            "pii_detected_count >= 0 AND sensitive_content_count >= 0",
            name="chk_metrics_detection_counts",
        ),
        CheckConstraint(
            "pass_through_count >= 0 AND sanitize_count >= 0 AND separate_count >= 0 AND redirect_count >= 0",
            name="chk_metrics_path_counts",
        ),
        CheckConstraint(
            "low_risk_count + mixed_risk_count + high_risk_count = total_analyses",
            name="chk_metrics_risk_total",
        ),
        CheckConstraint(
            "pass_through_count + sanitize_count + separate_count + redirect_count = total_analyses",
            name="chk_metrics_path_total",
        ),
        CheckConstraint(
            "pii_detected_count <= total_analyses AND sensitive_content_count <= total_analyses",
            name="chk_metrics_detection_total",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)
    total_analyses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_risk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mixed_risk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high_risk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pii_detected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sensitive_content_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pass_through_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sanitize_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    separate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    redirect_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
