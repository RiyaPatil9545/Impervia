from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models.enums import ProcessingPath, RiskLevel
from app.models.privacy_daily_metric import PrivacyDailyMetric


class AnalyticsRepository:
    def record_daily_analysis(
        self,
        db: Session,
        risk_level: RiskLevel,
        processing_path: ProcessingPath,
        pii_detected: bool,
        sensitive_detected: bool,
        target_date: date | None = None,
    ) -> None:
        """
        Atomically increment privacy daily metrics for the given date.
        Ensures exact compliance with all table CHECK constraints:
        - risk_total = total_analyses
        - path_total = total_analyses
        - detection_counts <= total_analyses
        """
        metric_date = target_date or datetime.now(UTC).date()

        low_inc = 1 if risk_level == RiskLevel.low else 0
        mixed_inc = 1 if risk_level == RiskLevel.mixed else 0
        high_inc = 1 if risk_level == RiskLevel.high else 0

        pass_inc = 1 if processing_path == ProcessingPath.pass_through else 0
        san_inc = 1 if processing_path == ProcessingPath.sanitize else 0
        sep_inc = 1 if processing_path == ProcessingPath.separate else 0
        redir_inc = 1 if processing_path == ProcessingPath.redirect else 0

        pii_inc = 1 if pii_detected else 0
        sens_inc = 1 if sensitive_detected else 0

        stmt = text("""
            INSERT INTO privacy_daily_metrics (
                metric_date,
                total_analyses,
                low_risk_count,
                mixed_risk_count,
                high_risk_count,
                pii_detected_count,
                sensitive_content_count,
                pass_through_count,
                sanitize_count,
                separate_count,
                redirect_count,
                updated_at
            ) VALUES (
                :metric_date,
                1,
                :low_inc,
                :mixed_inc,
                :high_inc,
                :pii_inc,
                :sens_inc,
                :pass_inc,
                :san_inc,
                :sep_inc,
                :redir_inc,
                now()
            )
            ON CONFLICT (metric_date) DO UPDATE SET
                total_analyses = privacy_daily_metrics.total_analyses + 1,
                low_risk_count = privacy_daily_metrics.low_risk_count + EXCLUDED.low_risk_count,
                mixed_risk_count = privacy_daily_metrics.mixed_risk_count + EXCLUDED.mixed_risk_count,
                high_risk_count = privacy_daily_metrics.high_risk_count + EXCLUDED.high_risk_count,
                pii_detected_count = privacy_daily_metrics.pii_detected_count + EXCLUDED.pii_detected_count,
                sensitive_content_count = privacy_daily_metrics.sensitive_content_count + EXCLUDED.sensitive_content_count,
                pass_through_count = privacy_daily_metrics.pass_through_count + EXCLUDED.pass_through_count,
                sanitize_count = privacy_daily_metrics.sanitize_count + EXCLUDED.sanitize_count,
                separate_count = privacy_daily_metrics.separate_count + EXCLUDED.separate_count,
                redirect_count = privacy_daily_metrics.redirect_count + EXCLUDED.redirect_count,
                updated_at = now();
        """)

        db.execute(
            stmt,
            {
                "metric_date": metric_date,
                "low_inc": low_inc,
                "mixed_inc": mixed_inc,
                "high_inc": high_inc,
                "pii_inc": pii_inc,
                "sens_inc": sens_inc,
                "pass_inc": pass_inc,
                "san_inc": san_inc,
                "sep_inc": sep_inc,
                "redir_inc": redir_inc,
            },
        )
        db.flush()

    def get_daily_metrics(
        self,
        db: Session,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 30,
    ) -> list[PrivacyDailyMetric]:
        stmt = select(PrivacyDailyMetric).order_by(PrivacyDailyMetric.metric_date.desc()).limit(limit)
        if start_date:
            stmt = stmt.where(PrivacyDailyMetric.metric_date >= start_date)
        if end_date:
            stmt = stmt.where(PrivacyDailyMetric.metric_date <= end_date)
        return list(db.scalars(stmt).all())

    def get_summary(self, db: Session) -> dict[str, Any]:
        """
        Computes aggregate metrics across all historical daily entries.
        Contains strictly anonymous counts and categories.
        """
        row = db.execute(
            select(
                func.coalesce(func.sum(PrivacyDailyMetric.total_analyses), 0).label("total"),
                func.coalesce(func.sum(PrivacyDailyMetric.low_risk_count), 0).label("low"),
                func.coalesce(func.sum(PrivacyDailyMetric.mixed_risk_count), 0).label("mixed"),
                func.coalesce(func.sum(PrivacyDailyMetric.high_risk_count), 0).label("high"),
                func.coalesce(func.sum(PrivacyDailyMetric.pii_detected_count), 0).label("pii"),
                func.coalesce(func.sum(PrivacyDailyMetric.sensitive_content_count), 0).label("sensitive"),
                func.coalesce(func.sum(PrivacyDailyMetric.pass_through_count), 0).label("pass_through"),
                func.coalesce(func.sum(PrivacyDailyMetric.sanitize_count), 0).label("sanitize"),
                func.coalesce(func.sum(PrivacyDailyMetric.separate_count), 0).label("separate"),
                func.coalesce(func.sum(PrivacyDailyMetric.redirect_count), 0).label("redirect"),
                func.min(PrivacyDailyMetric.metric_date).label("min_date"),
                func.max(PrivacyDailyMetric.metric_date).label("max_date"),
            )
        ).one()

        return {
            "total_analyses": int(row.total),
            "low_risk": int(row.low),
            "mixed_risk": int(row.mixed),
            "high_risk": int(row.high),
            "pii_detected": int(row.pii),
            "sensitive_detected": int(row.sensitive),
            "pass_through": int(row.pass_through),
            "sanitized": int(row.sanitize),
            "separated": int(row.separate),
            "redirected": int(row.redirect),
            "date_range_start": row.min_date,
            "date_range_end": row.max_date,
        }


analytics_repository = AnalyticsRepository()
