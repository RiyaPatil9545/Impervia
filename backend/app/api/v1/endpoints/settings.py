from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.audit_repository import audit_repository
from app.repositories.chat_repository import chat_repository
from app.repositories.user_repository import user_repository
from app.schemas.settings import PrivacySettingsResponse, PrivacySettingsUpdateRequest

router = APIRouter(prefix="/settings", tags=["Privacy Settings"])


@router.get(
    "",
    response_model=PrivacySettingsResponse,
    summary="Get user privacy preferences and retention settings",
)
def get_privacy_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = user_repository.get_privacy_settings(db, current_user.id)
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Privacy settings not found for this user.",
        )
    return PrivacySettingsResponse.model_validate(settings)


@router.put(
    "",
    response_model=PrivacySettingsResponse,
    summary="Update privacy preferences, consent, and retention days",
)
def update_privacy_settings(
    request: PrivacySettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updates = request.model_dump(exclude_unset=True)
    updated = user_repository.update_privacy_settings(db, current_user.id, updates)
    if not updated:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Settings could not be updated.",
        )

    audit_repository.log_event(
        db,
        event_type="privacy_settings_updated",
        user_id=current_user.id,
        details={"updated_fields": list(updates.keys())},
    )

    db.commit()
    db.refresh(updated)
    return PrivacySettingsResponse.model_validate(updated)


@router.post(
    "/purge-history",
    status_code=status.HTTP_200_OK,
    summary="Purge stored chat history based on retention or user request",
)
def purge_chat_history(
    purge_all: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Purges chat messages for the current user.
    If purge_all=True, deletes all saved messages and sessions.
    Otherwise, applies the user's configured retention_days.
    """
    settings = user_repository.get_privacy_settings(db, current_user.id)
    retention_days = (settings.retention_days if settings else None) or 30

    if purge_all:
        count = chat_repository.purge_all_user_history(db, current_user.id)
        msg = f"All {count} stored messages have been purged."
    else:
        count = chat_repository.purge_messages_by_retention(db, current_user.id, retention_days)
        msg = f"Purged {count} messages older than {retention_days} days."

    audit_repository.log_event(
        db,
        event_type="chat_history_purged",
        user_id=current_user.id,
        details={"purge_all": purge_all, "purged_count": count},
    )
    db.commit()
    return {"status": "success", "purged_count": count, "message": msg}
