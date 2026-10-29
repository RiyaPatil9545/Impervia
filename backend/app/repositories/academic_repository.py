
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic_response import AcademicResponse
from app.models.enums import GenerationStatus
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_source import KnowledgeSource


class AcademicRepository:
    """
    Data-access repository for academic responses and RAG knowledge structures.
    Preserves future compatibility without fake or unverified generation claims.
    """

    def create_academic_response_record(
        self,
        db: Session,
        user_id: int | None,
        session_id: int | None,
        input_message_id: int | None,
        response_message_id: int | None,
        model_name: str,
        generation_status: GenerationStatus = GenerationStatus.completed,
        latency_ms: int | None = None,
    ) -> AcademicResponse:
        record = AcademicResponse(
            user_id=user_id,
            session_id=session_id,
            input_message_id=input_message_id,
            response_message_id=response_message_id,
            model_name=model_name,
            generation_status=generation_status,
            latency_ms=latency_ms,
        )
        db.add(record)
        db.flush()
        return record

    def list_knowledge_sources(
        self, db: Session, subject: str | None = None
    ) -> list[KnowledgeSource]:
        stmt = select(KnowledgeSource).where(KnowledgeSource.is_active.is_(True))
        if subject:
            stmt = stmt.where(KnowledgeSource.subject == subject)
        return list(db.scalars(stmt).all())

    def get_chunks_for_source(
        self, db: Session, source_id: int
    ) -> list[KnowledgeChunk]:
        stmt = (
            select(KnowledgeChunk)
            .where(KnowledgeChunk.knowledge_source_id == source_id)
            .order_by(KnowledgeChunk.chunk_index.asc())
        )
        return list(db.scalars(stmt).all())


academic_repository = AcademicRepository()
