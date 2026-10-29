
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.repositories.audit_repository import audit_repository
from app.repositories.user_repository import user_repository
from app.schemas.auth import TokenResponse


class AuthService:
    def register(
        self,
        db: Session,
        email: str,
        password: str,
        name: str | None = None,
    ) -> User:
        existing = user_repository.get_by_email(db, email)
        if existing:
            raise ValueError("A user with this email already exists.")

        hashed = get_password_hash(password)
        user = user_repository.create_user(db, email=email, password_hash=hashed, name=name)

        audit_repository.log_event(
            db,
            event_type="user_registered",
            user_id=user.id,
            details={"email_domain": email.split("@")[-1]},
        )
        return user

    def authenticate(
        self,
        db: Session,
        email: str,
        password: str,
    ) -> User | None:
        user = user_repository.get_by_email(db, email)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    def create_token_for_user(self, user: User) -> TokenResponse:
        token = create_access_token(
            subject=user.id,
            claims={"email": user.email, "name": user.name},
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def delete_account(self, db: Session, user_id: int) -> bool:
        """
        Completely delete user account and associated personal data.
        """
        audit_repository.log_event(
            db,
            event_type="account_deleted",
            user_id=None,  # Do not link deleted user
            details={"action": "full_account_deletion", "deleted_user_id": user_id},
        )
        return user_repository.delete_user_account(db, user_id)


auth_service = AuthService()
