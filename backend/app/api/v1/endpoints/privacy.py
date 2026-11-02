
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_optional_current_user
from app.models.chat_session import ChatSession
from app.models.user import User
from app.repositories.analytics_repository import analytics_repository
from app.repositories.audit_repository import audit_repository
from app.repositories.privacy_repository import privacy_repository
from app.repositories.user_repository import user_repository
from app.schemas.privacy import (
    PrivacyAnalysisRequest,
    PrivacyAnalysisResponse,
    PrivacyFindingSchema,
)
from app.services.privacy.privacy_pipeline import privacy_pipeline

logger = logging.getLogger("impervia")

router = APIRouter(prefix="/privacy", tags=["Privacy Pipeline"])


@router.post(
    "/analyze",
    response_model=PrivacyAnalysisResponse,
    summary="Analyze input text through the Privacy Pipeline",
)
def analyze_text(
    request: PrivacyAnalysisRequest,
    current_user: User | None = Depends(get_optional_current_user),
    db: Session = Depends(get_db),
):
    """
    Direct endpoint for evaluating input text through the Privacy Handler:
    Preprocessing -> PII Detection -> Sensitive Content Detection ->
    Academic Relevance -> Risk Assessment -> Sanitization / Redirection.
    """
    result = privacy_pipeline.process(request.text)

    user_id = current_user.id if current_user else None

    # Validate session_id exists in chat_sessions table before using as foreign key
    valid_session_id = None
    if request.session_id and request.session_id > 0:
        stmt = select(ChatSession.id).where(ChatSession.id == request.session_id)
        if current_user:
            stmt = stmt.where(ChatSession.user_id == current_user.id)
        if db.scalar(stmt):
            valid_session_id = request.session_id

    analysis_id: int | None = None
    created_at = datetime.now(UTC)

    # Persist privacy analysis record (supports both authenticated and anonymous requests)
    try:
        analysis = privacy_repository.create_analysis(
            db,
            user_id=user_id,
            session_id=valid_session_id,
            message_id=None,
            pii_detected=result.pii_detected,
            sensitive_content_detected=result.sensitive_content_detected,
            context_relevance=result.context_relevance,
            risk_level=result.risk_level,
            processing_path=result.processing_path,
            detector_version=result.detector_version,
            processing_time_ms=result.processing_time_ms,
        )

        if result.findings:
            privacy_repository.add_findings(db, analysis.id, result.findings)

        if current_user:
            settings = user_repository.get_privacy_settings(db, current_user.id)
            allow_analytics = settings.allow_aggregate_analytics if settings else False

            # Audit log (metadata only - no raw sensitive text)
            audit_repository.log_event(
                db,
                event_type="privacy_analysis_run",
                user_id=current_user.id,
                session_id=valid_session_id,
                analysis_id=analysis.id,
                details={
                    "risk_level": result.risk_level.value,
                    "processing_path": result.processing_path.value,
                    "findings_count": len(result.findings),
                },
            )

            # Increment aggregate daily metrics ONLY if consent given
            if allow_analytics:
                analytics_repository.record_daily_analysis(
                    db,
                    risk_level=result.risk_level,
                    processing_path=result.processing_path,
                    pii_detected=result.pii_detected,
                    sensitive_detected=result.sensitive_content_detected,
                )

        db.commit()
        db.refresh(analysis)
        analysis_id = analysis.id
        created_at = analysis.created_at
    except Exception as exc:
        db.rollback()
        logger.warning(f"Could not persist privacy analysis record: {exc.__class__.__name__}")

    return PrivacyAnalysisResponse(
        analysis_id=analysis_id,
        pii_detected=result.pii_detected,
        sensitive_content_detected=result.sensitive_content_detected,
        context_relevance=result.context_relevance,
        risk_level=result.risk_level,
        processing_path=result.processing_path,
        sanitized_text=result.sanitized_text,
        extracted_academic_query=result.extracted_academic_query,
        redirection_message=result.redirection_message,
        findings=result.findings,
        detector_version=result.detector_version,
        processing_time_ms=result.processing_time_ms,
        created_at=created_at,
    )


@router.get(
    "/analyses",
    response_model=list[PrivacyAnalysisResponse],
    summary="List past privacy analyses for the authenticated user",
)
def list_user_analyses(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = privacy_repository.list_analyses(db, current_user.id, limit=limit, offset=offset)
    responses = []
    for r in records:
        findings_schemas = [PrivacyFindingSchema.model_validate(f) for f in r.findings]
        responses.append(
            PrivacyAnalysisResponse(
                analysis_id=r.id,
                pii_detected=r.pii_detected,
                sensitive_content_detected=r.sensitive_content_detected,
                context_relevance=r.context_relevance,
                risk_level=r.risk_level,
                processing_path=r.processing_path,
                sanitized_text="[HISTORY_VIEW]",
                extracted_academic_query=None,
                redirection_message=None,
                findings=findings_schemas,
                detector_version=r.detector_version,
                processing_time_ms=r.processing_time_ms,
                created_at=r.created_at,
            )
        )
    return responses


@router.get(
    "/analyses/{analysis_id}",
    response_model=PrivacyAnalysisResponse,
    summary="Get details of a specific privacy analysis (with ownership verification)",
)
def get_analysis_detail(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    analysis = privacy_repository.get_analysis(db, analysis_id=analysis_id, user_id=current_user.id)
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis record not found or access unauthorized.",
        )
    findings_schemas = [PrivacyFindingSchema.model_validate(f) for f in analysis.findings]
    return PrivacyAnalysisResponse(
        analysis_id=analysis.id,
        pii_detected=analysis.pii_detected,
        sensitive_content_detected=analysis.sensitive_content_detected,
        context_relevance=analysis.context_relevance,
        risk_level=analysis.risk_level,
        processing_path=analysis.processing_path,
        sanitized_text="[HISTORY_VIEW]",
        extracted_academic_query=None,
        redirection_message=None,
        findings=findings_schemas,
        detector_version=analysis.detector_version,
        processing_time_ms=analysis.processing_time_ms,
        created_at=analysis.created_at,
    )
