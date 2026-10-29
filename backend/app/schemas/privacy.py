from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import (
    FindingType,
    PrivacyAction,
    ProcessingPath,
    RelevanceStatus,
    RiskLevel,
)


class PrivacyFindingSchema(BaseModel):
    finding_type: FindingType
    category: str
    relevance: RelevanceStatus
    action_taken: PrivacyAction
    occurrence_count: int = Field(default=1, ge=1)
    confidence: Decimal | None = Field(default=None, ge=0, le=1)

    model_config = {"from_attributes": True}


class PrivacyAnalysisRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000, description="Raw input text to analyze")
    session_id: int | None = Field(default=None, description="Optional chat session context")


class PrivacyAnalysisResponse(BaseModel):
    analysis_id: int | None = None
    pii_detected: bool
    sensitive_content_detected: bool
    context_relevance: RelevanceStatus
    risk_level: RiskLevel
    processing_path: ProcessingPath
    sanitized_text: str
    extracted_academic_query: str | None = None
    redirection_message: str | None = None
    findings: list[PrivacyFindingSchema] = Field(default_factory=list)
    detector_version: str | None = None
    processing_time_ms: int | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
