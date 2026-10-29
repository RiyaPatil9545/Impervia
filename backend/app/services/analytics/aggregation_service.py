from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.models.enums import ProcessingPath, RiskLevel
from app.models.privacy_daily_metric import PrivacyDailyMetric
from app.repositories.analytics_repository import analytics_repository
from app.repositories.user_repository import user_repository


class AggregationService:
    def record_analysis_if_consented(
        self,
        db: Session,
        user_id: int | None,
        risk_level: RiskLevel,
        processing_path: ProcessingPath,
        pii_detected: bool,
        sensitive_detected: bool,
    ) -> bool:
        """
        Records metric ONLY if user has explicitly granted analytics consent.
        Unauthenticated or non-consenting users are NOT included in metrics.
        """
        if user_id is None:
            return False

        settings = user_repository.get_privacy_settings(db, user_id)
        if not settings or not settings.allow_aggregate_analytics:
            return False

        analytics_repository.record_daily_analysis(
            db,
            risk_level=risk_level,
            processing_path=processing_path,
            pii_detected=pii_detected,
            sensitive_detected=sensitive_detected,
        )
        return True

    def get_daily_metrics(
        self,
        db: Session,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[PrivacyDailyMetric]:
        return analytics_repository.get_daily_metrics(db, start_date, end_date)

    def get_summary(self, db: Session) -> dict[str, Any]:
        return analytics_repository.get_summary(db)


aggregation_service = AggregationService()
