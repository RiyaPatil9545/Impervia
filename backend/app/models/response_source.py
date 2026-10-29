from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.academic_response import AcademicResponse
    from app.models.knowledge_source import KnowledgeSource


class ResponseSource(Base):
    __tablename__ = "response_sources"
    __table_args__ = (
        CheckConstraint(
            "relevance_score IS NULL OR (relevance_score >= 0 AND relevance_score <= 1)",
            name="chk_source_relevance_score",
        ),
        Index("idx_response_sources_source", "knowledge_source_id"),
        UniqueConstraint(
            "academic_response_id",
            "knowledge_source_id",
            "chunk_reference",
            name="uq_response_source_chunk",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    academic_response_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("academic_responses.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    chunk_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 5), nullable=True)

    # Relationships
    academic_response: Mapped["AcademicResponse"] = relationship(
        "AcademicResponse",
        back_populates="sources",
    )
    knowledge_source: Mapped["KnowledgeSource"] = relationship(
        "KnowledgeSource",
        back_populates="response_sources",
    )
