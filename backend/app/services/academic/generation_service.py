

from app.core.config import settings
from app.services.academic.gemini_service import (
    GeminiAcademicService,
    gemini_academic_service,
)


class AcademicGenerationService:
    """
    Coordinates academic explanation generation for student queries.
    Delegates sanitized queries to Google Gemini Academic LLM.
    Ensures ONLY queries pre-sanitized by the Privacy Handler reach the model.
    """

    def __init__(self, llm_service: GeminiAcademicService | None = None) -> None:
        self.llm_service = llm_service or gemini_academic_service

    @property
    def MODEL_NAME(self) -> str:
        return self.llm_service.model_name or settings.GEMINI_MODEL

    def generate_response(
        self,
        sanitized_academic_query: str | None,
        system_context: str | None = None,
    ) -> str:
        """
        Generates an educational response for the sanitized academic query.
        Never calls Gemini if no query was provided.
        """
        if not sanitized_academic_query or not sanitized_academic_query.strip():
            return "No academic question was provided for processing."

        return self.llm_service.generate_academic_response(sanitized_academic_query.strip())


academic_generation_service = AcademicGenerationService()
