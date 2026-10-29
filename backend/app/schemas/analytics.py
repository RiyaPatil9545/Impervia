from datetime import date, datetime

from pydantic import BaseModel


class DailyMetricResponse(BaseModel):
    id: int
    metric_date: date
    total_analyses: int
    low_risk_count: int
    mixed_risk_count: int
    high_risk_count: int
    pii_detected_count: int
    sensitive_content_count: int
    pass_through_count: int
    sanitize_count: int
    separate_count: int
    redirect_count: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnalyticsSummaryResponse(BaseModel):
    total_analyses: int
    low_risk: int
    mixed_risk: int
    high_risk: int
    pii_detected: int
    sensitive_detected: int
    pass_through: int
    sanitized: int
    separated: int
    redirected: int
    date_range_start: date | None = None
    date_range_end: date | None = None
