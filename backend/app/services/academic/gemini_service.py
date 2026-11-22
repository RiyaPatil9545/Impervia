import logging
import time

from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.core.config import settings

logger = logging.getLogger("impervia")

ACADEMIC_TUTOR_SYSTEM_PROMPT = (
    "You are Impervia's Academic AI Tutor. Your role is strictly educational, helpful, "
    "and objective. Assist students with coursework, conceptual explanations, mathematical derivations, "
    "code debugging, and study guidance.\n\n"
    "Core Guidelines:\n"
    "1. Focus entirely on academic and pedagogical reasoning.\n"
    "2. Provide clear, structured, step-by-step explanations.\n"
    "3. If input contains redaction tokens (such as [REDACTED_NAME], [REDACTED_EMAIL], [REDACTED_STUDENT_ID], "
    "[REDACTED_PHONE], [REDACTED_FINANCIAL_INFO], etc.), treat them as anonymous placeholders. "
    "Never comment on, speculate about, or attempt to recover the redacted information.\n"
    "4. Maintain a supportive, encouraging, and respectful academic tone.\n"
    "5. Keep responses concise, focused, and directly addressing the question without excessive verbosity.\n"
    "6. If a question is ambiguous, state your assumptions clearly before answering."
)


class GeminiAcademicService:
    """
    Interface to Google Gemini API for Phase 2 Academic LLM inference.
    Enforces strict privacy boundaries:
    - Only receives pre-sanitized or separated academic queries.
    - Never receives raw student input or sensitive disclosures.
    - Enforces strict token ceilings to minimize API credit consumption.
    """

    def __init__(self, client: genai.Client | None = None) -> None:
        self._client = client

    def get_client(self) -> genai.Client | None:
        """
        Retrieves or initializes the official Google GenAI Client.
        Never logs or exposes the API key.
        """
        if self._client is not None:
            return self._client

        api_key = settings.GEMINI_API_KEY
        if not api_key:
            return None

        try:
            self._client = genai.Client(api_key=api_key)
            return self._client
        except Exception as exc:
            logger.error("Failed to initialize Google GenAI Client: %s", type(exc).__name__)
            return None

    def set_client(self, client: genai.Client | None) -> None:
        """Injects a custom or mock client (useful for unit testing)."""
        self._client = client

    def generate_academic_response(
        self,
        sanitized_query: str,
        system_context: str | None = None,
    ) -> tuple[str, str, int]:
        """
        Executes academic inference on a sanitized student query.

        Args:
            sanitized_query: Pre-sanitized academic query with all PII masked.
            system_context: Optional specialized system instruction.

        Returns:
            Tuple of (response_text, model_name, latency_ms)
        """
        cleaned_query = (sanitized_query or "").strip()
        model_name = settings.GEMINI_MODEL

        # Defensive guard: Do not query Gemini with empty or stripped placeholders
        if not cleaned_query or cleaned_query == "[CONTENT_REMOVED_BY_PRIVACY_HANDLER]":
            return (
                "No valid academic query was found for Academic AI processing.",
                model_name,
                0,
            )

        client = self.get_client()
        if client is None:
            # Graceful fallback when API key is not yet configured
            fallback_text = (
                f"[Impervia Academic Assistant - Gemini Configuration Notice]\n"
                f"Your sanitized academic query was approved by the Privacy Handler:\n"
                f'"{cleaned_query}"\n\n'
                f"Notice: GEMINI_API_KEY is not configured in the environment. "
                f"Please set GEMINI_API_KEY in your .env file to enable live {model_name} responses."
            )
            return fallback_text, model_name, 0

        start_time = time.perf_counter()

        try:
            instruction = system_context or ACADEMIC_TUTOR_SYSTEM_PROMPT
            config = types.GenerateContentConfig(
                system_instruction=instruction,
                max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
                temperature=settings.GEMINI_TEMPERATURE,
            )

            response = client.models.generate_content(
                model=model_name,
                contents=cleaned_query,
                config=config,
            )

            elapsed_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            response_text = (
                response.text
                if response and response.text
                else "The Academic Assistant did not return an explanation. Please try asking your question differently."
            )
            return response_text, model_name, elapsed_ms

        except APIError as e:
            elapsed_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            err_msg = str(e).upper()
            code = getattr(e, "code", None)

            logger.error("Gemini APIError during academic generation (code=%s)", code)

            if code == 429 or "RESOURCE_EXHAUSTED" in err_msg or "QUOTA" in err_msg:
                return (
                    "The Academic Assistant is currently at peak capacity or quota limit. "
                    "Please wait a moment and try your question again.",
                    model_name,
                    elapsed_ms,
                )
            if "DEADLINE_EXCEEDED" in err_msg or "TIMEOUT" in err_msg:
                return (
                    "The Academic Assistant timed out while processing your inquiry. "
                    "Please try submitting your question again.",
                    model_name,
                    elapsed_ms,
                )
            return (
                "The Academic Assistant encountered a service error while processing your request. "
                "Please try again later.",
                model_name,
                elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            logger.error("Unexpected error during Gemini academic generation: %s", type(e).__name__)
            err_str = str(e).upper()

            if "TIMEOUT" in err_str or "TIMED OUT" in err_str:
                return (
                    "The Academic Assistant timed out while processing your inquiry. "
                    "Please try submitting your question again.",
                    model_name,
                    elapsed_ms,
                )

            return (
                "The Academic Assistant is temporarily unavailable. "
                "Your question was validated by the Privacy Handler, but inference could not be completed.",
                model_name,
                elapsed_ms,
            )


gemini_academic_service = GeminiAcademicService()
