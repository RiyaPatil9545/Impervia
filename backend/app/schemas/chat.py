from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    MessageRole,
    ProcessingPath,
    RelevanceStatus,
    RiskLevel,
    StorageStatus,
)
from app.schemas.privacy import PrivacyFindingSchema


class ChatSessionCreate(BaseModel):
    pass


class ChatSessionResponse(BaseModel):
    id: int
    user_id: int
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    message_count: int | None = 0

    model_config = {"from_attributes": True}


class ChatMessageResponse(BaseModel):
    id: int
    session_id: int
    role: MessageRole
    content: str
    storage_status: StorageStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionDetailResponse(BaseModel):
    session: ChatSessionResponse
    messages: list[ChatMessageResponse] = Field(default_factory=list)


class ChatProcessRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    session_id: int | None = Field(default=None, description="Optional existing session ID")


class ChatProcessResponse(BaseModel):
    session_id: int | None = None
    user_message_id: int | None = None
    user_message_stored: bool
    processing_path: ProcessingPath
    risk_level: RiskLevel
    context_relevance: RelevanceStatus
    sanitized_input: str
    extracted_academic_query: str | None = None
    assistant_response: str
    findings: list[PrivacyFindingSchema] = Field(default_factory=list)
    analysis_id: int | None = None
