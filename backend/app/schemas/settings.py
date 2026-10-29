from datetime import datetime

from pydantic import BaseModel, Field


class PrivacySettingsResponse(BaseModel):
    user_id: int
    save_chat_history: bool
    allow_aggregate_analytics: bool
    warn_before_high_risk: bool
    retention_days: int | None = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class PrivacySettingsUpdateRequest(BaseModel):
    save_chat_history: bool | None = None
    allow_aggregate_analytics: bool | None = None
    warn_before_high_risk: bool | None = None
    retention_days: int | None = Field(default=None, ge=1, le=3650)
