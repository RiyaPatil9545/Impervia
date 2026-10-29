from typing import Any

from sqlalchemy.orm import Session

from app.repositories.academic_repository import academic_repository


class RAGService:
    """
    Interface for future RAG retrieval and vector store operations.
    Preserves architectural readiness for Phase 2 without misleading claims.
    """

    def retrieve_relevant_chunks(
        self,
        db: Session,
        query: str,
        subject: str | None = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        # Phase 1: Retrieve any active knowledge source references from PostgreSQL
        sources = academic_repository.list_knowledge_sources(db, subject=subject)
        results = []
        for src in sources[:top_k]:
            chunks = academic_repository.get_chunks_for_source(db, src.id)
            for ch in chunks[:1]:
                results.append(
                    {
                        "source_id": src.id,
                        "source_title": src.title,
                        "chunk_reference": ch.chunk_reference,
                        "vector_store": ch.vector_store,
                    }
                )
        return results


rag_service = RAGService()
