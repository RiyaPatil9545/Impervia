from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.knowledge_source import KnowledgeSource


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        CheckConstraint("chunk_index >= 0", name="chk_chunk_index"),
        CheckConstraint(
            "vector_store IN ('pgvector', 'qdrant', 'external')",
            name="chk_vector_store",
        ),
        Index("idx_chunks_source", "knowledge_source_id"),
        UniqueConstraint("knowledge_source_id", "chunk_index", name="uq_source_chunk_index"),
        UniqueConstraint("vector_store", "chunk_reference", name="uq_chunk_store_reference"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    vector_store: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    knowledge_source: Mapped["KnowledgeSource"] = relationship(
        "KnowledgeSource",
        back_populates="chunks",
    )
