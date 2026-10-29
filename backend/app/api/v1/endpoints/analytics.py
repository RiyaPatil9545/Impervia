from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.analytics import AnalyticsSummaryResponse, DailyMetricResponse
from app.services.analytics.aggregation_service import aggregation_service

router = APIRouter(prefix="/analytics", tags=["Aggregate Analytics"])


@router.get(
    "/daily",
    response_model=list[DailyMetricResponse],
    summary="Get daily aggregate privacy metrics (strictly anonymous)",
)
def get_daily_metrics(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns daily aggregated counts of privacy analyses, detections, and risk paths.
    No personal identifiers, prompts, or messages are ever exposed.
    """
    metrics = aggregation_service.get_daily_metrics(db, start_date=start_date, end_date=end_date)
    return [DailyMetricResponse.model_validate(m) for m in metrics]


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
    summary="Get aggregate overall summary of privacy preservation",
)
def get_analytics_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    summary = aggregation_service.get_summary(db)
    return AnalyticsSummaryResponse.model_validate(summary)
