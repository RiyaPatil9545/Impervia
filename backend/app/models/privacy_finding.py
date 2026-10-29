from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import FindingType, PrivacyAction, RelevanceStatus

if TYPE_CHECKING:
    from app.models.privacy_analysis import PrivacyAnalysis


class PrivacyFinding(Base):
    __tablename__ = "privacy_findings"
    __table_args__ = (
        CheckConstraint(
            "occurrence_count >= 1",
            name="chk_finding_occurrence_count",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="chk_finding_confidence",
        ),
        Index("idx_findings_analysis", "analysis_id"),
        Index("idx_findings_type_category", "finding_type", "category"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("privacy_analyses.id", ondelete="CASCADE"),
        nullable=False,
    )
    finding_type: Mapped[FindingType] = mapped_column(
        SAEnum(FindingType, name="finding_type", create_type=False),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    relevance: Mapped[RelevanceStatus] = mapped_column(
        SAEnum(RelevanceStatus, name="relevance_status", create_type=False),
        nullable=False,
    )
    action_taken: Mapped[PrivacyAction] = mapped_column(
        SAEnum(PrivacyAction, name="privacy_action", create_type=False),
        nullable=False,
    )
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    # Relationships
    analysis: Mapped["PrivacyAnalysis"] = relationship("PrivacyAnalysis", back_populates="findings")
