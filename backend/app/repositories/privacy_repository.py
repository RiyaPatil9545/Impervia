
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import ProcessingPath, RelevanceStatus, RiskLevel
from app.models.privacy_analysis import PrivacyAnalysis
from app.models.privacy_finding import PrivacyFinding
from app.schemas.privacy import PrivacyFindingSchema


class PrivacyRepository:
    def create_analysis(
        self,
        db: Session,
        user_id: int | None,
        session_id: int | None,
        message_id: int | None,
        pii_detected: bool,
        sensitive_content_detected: bool,
        context_relevance: RelevanceStatus,
        risk_level: RiskLevel,
        processing_path: ProcessingPath,
        detector_version: str | None = None,
        processing_time_ms: int | None = None,
    ) -> PrivacyAnalysis:
        analysis = PrivacyAnalysis(
            user_id=user_id,
            session_id=session_id,
            message_id=message_id,
            pii_detected=pii_detected,
            sensitive_content_detected=sensitive_content_detected,
            context_relevance=context_relevance,
            risk_level=risk_level,
            processing_path=processing_path,
            detector_version=detector_version,
            processing_time_ms=processing_time_ms,
        )
        db.add(analysis)
        db.flush()
        return analysis

    def add_findings(
        self,
        db: Session,
        analysis_id: int,
        findings: list[PrivacyFindingSchema],
    ) -> list[PrivacyFinding]:
        db_findings: list[PrivacyFinding] = []
        for f in findings:
            finding = PrivacyFinding(
                analysis_id=analysis_id,
                finding_type=f.finding_type,
                category=f.category,
                relevance=f.relevance,
                action_taken=f.action_taken,
                occurrence_count=max(1, f.occurrence_count),
                confidence=f.confidence,
            )
            db.add(finding)
            db_findings.append(finding)
        db.flush()
        return db_findings

    def get_analysis(
        self, db: Session, analysis_id: int, user_id: int | None = None
    ) -> PrivacyAnalysis | None:
        stmt = (
            select(PrivacyAnalysis)
            .options(selectinload(PrivacyAnalysis.findings))
            .where(PrivacyAnalysis.id == analysis_id)
        )
        if user_id is not None:
            stmt = stmt.where(PrivacyAnalysis.user_id == user_id)
        return db.scalar(stmt)

    def list_analyses(
        self, db: Session, user_id: int, limit: int = 50, offset: int = 0
    ) -> list[PrivacyAnalysis]:
        return list(
            db.scalars(
                select(PrivacyAnalysis)
                .options(selectinload(PrivacyAnalysis.findings))
                .where(PrivacyAnalysis.user_id == user_id)
                .order_by(PrivacyAnalysis.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )


privacy_repository = PrivacyRepository()
