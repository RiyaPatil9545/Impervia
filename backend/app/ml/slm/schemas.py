from typing import Any

from pydantic import BaseModel, Field, field_validator


class SLMContextAnalysis(BaseModel):
    """
    Structured contextual output from local Small Language Model (SLM).
    Used to supplement rule-based detection for nuanced sentiment,
    slang, subtle distress, typos, and academic query boundary extraction.
    """

    has_academic_intent: bool = Field(
        ...,
        description="True if the message contains an authentic educational or academic inquiry",
    )
    academic_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Confidence score for academic intent from 0.0 to 1.0",
    )
    primary_academic_domain: str | None = Field(
        default=None,
        description="Detected academic subject domain (e.g., computer_science, mathematics, natural_sciences, humanities)",
    )

    @field_validator("academic_score", mode="before")
    @classmethod
    def coerce_null_academic_score(cls, v: Any) -> float:
        if v is None:
            return 0.0
        return v

    @field_validator("sensitive_category", mode="before")
    @classmethod
    def normalize_sensitive_category(cls, v: Any) -> str | None:
        if isinstance(v, str) and v.lower() in {"suicide", "suicidal", "self_harm", "self-harm", "crisis"}:
            return "mental_health"
        return v
    has_sensitive_content: bool = Field(
        ...,
        description="True if personal emotional venting, distress, relationship, or confidential disclosure is present",
    )
    sensitive_category: str | None = Field(
        default=None,
        description="Category: mental_health, relationship, health_medical, financial_hardship, personal_confession, or None",
    )
    distress_severity: str | None = Field(
        default=None,
        description="Severity of distress: 'high' for acute crisis/suicidal ideation, 'medium' for stress/anxiety/venting, or None",
    )
    is_crisis: bool = Field(
        default=False,
        description="True if the disclosure involves immediate self-harm, suicidal ideation, or extreme acute crisis",
    )
    extracted_academic_query: str | None = Field(
        default=None,
        description="The clean academic portion of the question stripped of personal venting, or None if no academic question exists",
    )
    extracted_sensitive_disclosure: str | None = Field(
        default=None,
        description="The personal or sensitive statement portion, or None if clean",
    )
    reasoning: str | None = Field(
        default=None,
        description="Brief concise rationale for the contextual classification",
    )


class SLMAnalysisResult(BaseModel):
    """Execution wrapper including latency, availability, and error telemetry."""

    analysis: SLMContextAnalysis | None = None
    is_available: bool = False
    latency_ms: int = 0
    error_message: str | None = None
    model_used: str | None = None
