from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.v1.endpoints import analytics, auth, chat, privacy, settings
from app.core.config import settings as app_settings

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(settings.router)
api_router.include_router(privacy.router)
api_router.include_router(chat.router)
api_router.include_router(analytics.router)


@api_router.get("/health", tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """
    Verifies backend application status and read-only PostgreSQL database connectivity.
    """
    try:
        db.execute(text("SELECT 1")).scalar()
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {e!s}"

    return {
        "status": "online",
        "app_name": app_settings.APP_NAME,
        "version": app_settings.APP_VERSION,
        "database": db_status,
        "detector_version": app_settings.DETECTOR_VERSION,
    }
