from app.core.config import settings
from app.services.academic.gemini_service import (
    GeminiAcademicService,
    gemini_academic_service,
)


class AcademicGenerationService:
    """
    Academic Generation Service for Impervia Phase 2.
    Integrates Google Gemini Flash as a dedicated Academic LLM.
    Enforces that only privacy-sanitized queries reach the Academic model.
    """

    def __init__(self, gemini_service: GeminiAcademicService | None = None) -> None:
        self.gemini_service = gemini_service or gemini_academic_service
        self.last_model_name: str = settings.GEMINI_MODEL
        self.last_latency_ms: int = 0

    @property
    def MODEL_NAME(self) -> str:
        """Returns the active Academic model identifier for metadata and DB auditing."""
        return settings.GEMINI_MODEL

    def generate_response(
        self,
        sanitized_academic_query: str,
        system_context: str | None = None,
    ) -> str:
        """
        Generates an educational response for sanitized academic inquiries
        using Google Gemini Flash via the official google-genai SDK.

        Guarantees:
        - Never queries Gemini if the query is empty or redacted.
        - Receives only privacy-sanitized text (PII masked, sensitive disclosures removed).
        """
        cleaned_query = (sanitized_academic_query or "").strip()
        if not cleaned_query or cleaned_query == "[CONTENT_REMOVED_BY_PRIVACY_HANDLER]":
            return "No valid academic inquiry was detected for Academic AI generation."

        text, model, latency = self.gemini_service.generate_academic_response(
            cleaned_query,
            system_context=system_context,
        )
        self.last_model_name = model
        self.last_latency_ms = latency
        return text


academic_generation_service = AcademicGenerationService()
