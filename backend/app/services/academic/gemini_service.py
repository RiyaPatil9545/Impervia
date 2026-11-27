import logging
from typing import Any

from google import genai
from google.genai import errors, types

from app.core.config import settings

logger = logging.getLogger("impervia")

TIMEOUT_EXCEPTIONS: tuple[type[BaseException], ...] = (TimeoutError,)
if hasattr(errors, "httpx") and hasattr(errors.httpx, "TimeoutException"):
    TIMEOUT_EXCEPTIONS = (*TIMEOUT_EXCEPTIONS, errors.httpx.TimeoutException)
if hasattr(errors, "httpx2") and hasattr(errors.httpx2, "TimeoutException"):
    TIMEOUT_EXCEPTIONS = (*TIMEOUT_EXCEPTIONS, errors.httpx2.TimeoutException)


class GeminiAcademicService:
    """
    Academic reasoning and explanation service powered by Google Gemini.
    Provides structured academic tutoring for sanitized queries approved by the Privacy Pipeline.
    """

    SYSTEM_INSTRUCTION = (
        "You are Impervia's Academic Tutor, an expert educational AI assistant for students.\n"
        "Your role is to explain academic coursework and subjects (such as computer science, "
        "engineering, mathematics, natural sciences, and humanities) clearly, concisely, and accurately.\n\n"
        "Pedagogical Guidelines:\n"
        "1. Provide structured explanations with clear definitions, practical examples, and key takeaways.\n"
        "2. Maintain an encouraging, respectful, and academically rigorous tone.\n"
        "3. Keep your explanation focused on the requested topic and strictly within the response length limit.\n"
        "4. If the query contains privacy redaction placeholders (e.g., [REDACTED_EMAIL], [REDACTED_PHONE], "
        "[REDACTED_NAME]), treat them as anonymous placeholders in examples without commenting on them or requesting real details.\n"
        "5. Never ask the student for real-world personal identifiers, passwords, payment info, or confidential personal disclosures."
    )

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        max_output_tokens: int | None = None,
        temperature: float | None = None,
        timeout: float | None = None,
        client: Any = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self.max_output_tokens = max_output_tokens or settings.GEMINI_MAX_TOKENS
        self.temperature = temperature if temperature is not None else settings.GEMINI_TEMPERATURE
        self.timeout = timeout if timeout is not None else settings.GEMINI_TIMEOUT_SECONDS
        self._client = client

    def _get_client(self) -> genai.Client:
        """Instantiate or reuse genai.Client with configured credentials and timeout."""
        if self._client is not None:
            return self._client

        if not self.api_key or self.api_key.strip() in {"", "your_actual_api_key", "your_gemini_api_key"}:
            raise ValueError("GEMINI_API_KEY is not configured or uses a placeholder value.")

        # HttpOptions.timeout is in milliseconds; settings.GEMINI_TIMEOUT_SECONDS is in seconds.
        http_options = types.HttpOptions(timeout=float(self.timeout) * 1000.0)
        self._client = genai.Client(
            api_key=self.api_key,
            http_options=http_options,
        )
        return self._client

    def generate_academic_response(self, sanitized_query: str) -> str:
        """
        Calls Gemini Flash with the sanitized academic query.
        Never receives unmasked PII or non-academic raw disclosures.
        Handles errors gracefully to ensure zero backend crash.
        """
        if not sanitized_query or not sanitized_query.strip():
            return "No academic question was provided for processing."

        try:
            client = self._get_client()

            config = types.GenerateContentConfig(
                system_instruction=self.SYSTEM_INSTRUCTION,
                max_output_tokens=self.max_output_tokens,
                temperature=self.temperature,
            )

            response = client.models.generate_content(
                model=self.model_name,
                contents=sanitized_query.strip(),
                config=config,
            )

            if response.candidates:
                candidate = response.candidates[0]
                finish_reason = getattr(candidate, "finish_reason", None)
                if finish_reason and "MAX_TOKENS" in str(finish_reason):
                    logger.warning(
                        f"Gemini response reached MAX_TOKENS limit ({self.max_output_tokens}). "
                        "Response may be truncated by model."
                    )

            response_text = (response.text or "").strip()
            if not response_text:
                return (
                    "The Academic AI generated an empty response. "
                    "Please rephrase your question or try again."
                )

            return response_text

        except ValueError as val_err:
            logger.warning(f"Academic LLM configuration error: {val_err.__class__.__name__}")
            return (
                "The Academic AI service is currently unavailable (API key not configured). "
                "Please check backend environment settings."
            )

        except errors.APIError as api_err:
            logger.error(f"Gemini API error during generation: {api_err.__class__.__name__}")
            status_code = getattr(api_err, "code", None)
            if (
                status_code in (429, 503)
                or "RESOURCE_EXHAUSTED" in str(api_err)
                or "UNAVAILABLE" in str(api_err)
            ):
                return (
                    "The Academic AI service is temporarily experiencing high demand or rate limits. "
                    "Please wait a moment and try submitting your question again."
                )
            elif status_code == 403 or "PERMISSION_DENIED" in str(api_err):
                return (
                    "The Academic AI service could not authenticate with the provided credentials. "
                    "Please contact your administrator."
                )
            return (
                "The Academic AI service encountered an issue while processing your question. "
                "Please try again shortly."
            )

        except TIMEOUT_EXCEPTIONS:
            logger.warning("Gemini API request timed out.")
            return (
                "The Academic AI service timed out while generating your explanation. "
                "Please try again with a more specific query."
            )

        except Exception as exc:
            # Safe logging: never leak query or student text
            logger.error(f"Unexpected error during academic generation: {exc.__class__.__name__}")
            # If the exception message indicates a timeout, give timeout message
            if "timeout" in exc.__class__.__name__.lower() or "timeout" in str(exc).lower():
                return (
                    "The Academic AI service timed out while generating your explanation. "
                    "Please try again."
                )
            return (
                "An unexpected error occurred while communicating with the Academic AI service. "
                "Please try again later."
            )


gemini_academic_service = GeminiAcademicService()
