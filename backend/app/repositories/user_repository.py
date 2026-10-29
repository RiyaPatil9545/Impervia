from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.privacy_settings import UserPrivacySettings
from app.models.user import User


class UserRepository:
    def get_by_id(self, db: Session, user_id: int) -> User | None:
        return db.scalar(select(User).where(User.id == user_id))

    def get_by_email(self, db: Session, email: str) -> User | None:
        return db.scalar(select(User).where(User.email == email.lower().strip()))

    def create_user(
        self,
        db: Session,
        email: str,
        password_hash: str,
        name: str | None = None,
    ) -> User:
        user = User(
            email=email.lower().strip(),
            password_hash=password_hash,
            name=name.strip() if name else None,
            is_active=True,
        )
        db.add(user)
        db.flush()

        # Automatic creation of default user privacy settings (explicit consent defaults to false)
        settings = UserPrivacySettings(
            user_id=user.id,
            save_chat_history=False,
            allow_aggregate_analytics=False,
            warn_before_high_risk=True,
            retention_days=30,
        )
        db.add(settings)
        db.flush()
        return user

    def get_privacy_settings(self, db: Session, user_id: int) -> UserPrivacySettings | None:
        return db.scalar(
            select(UserPrivacySettings).where(UserPrivacySettings.user_id == user_id)
        )

    def update_privacy_settings(
        self,
        db: Session,
        user_id: int,
        updates: dict[str, Any],
    ) -> UserPrivacySettings | None:
        settings = self.get_privacy_settings(db, user_id)
        if not settings:
            return None

        for field, value in updates.items():
            if value is not None and hasattr(settings, field):
                setattr(settings, field, value)

        settings.updated_at = datetime.now(UTC)
        db.flush()
        return settings

    def delete_user_account(self, db: Session, user_id: int) -> bool:
        """
        Delete user account and cascade to all personal records.
        """
        user = self.get_by_id(db, user_id)
        if not user:
            return False
        db.delete(user)
        db.flush()
        return True


user_repository = UserRepository()
