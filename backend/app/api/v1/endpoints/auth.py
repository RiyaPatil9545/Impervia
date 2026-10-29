from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    UserWithSettingsResponse,
)
from app.schemas.settings import PrivacySettingsResponse
from app.services.auth.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserWithSettingsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Registers a new student or academic user.
    Automatically generates default privacy settings with explicit consent defaults.
    """
    try:
        user = auth_service.register(
            db,
            email=request.email,
            password=request.password,
            name=request.name,
        )
        db.commit()
        db.refresh(user)
        return UserWithSettingsResponse(
            user=UserResponse.model_validate(user),
            settings=PrivacySettingsResponse.model_validate(user.privacy_settings),
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again.",
        ) from e


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and obtain JWT token",
)
def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticates user credentials and issues a signed JWT token.
    """
    user = auth_service.authenticate(db, email=request.email, password=request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_service.create_token_for_user(user)


@router.get(
    "/me",
    response_model=UserWithSettingsResponse,
    summary="Get current authenticated user profile and privacy settings",
)
def get_me(
    current_user: User = Depends(get_current_user),
):
    return UserWithSettingsResponse(
        user=UserResponse.model_validate(current_user),
        settings=PrivacySettingsResponse.model_validate(current_user.privacy_settings),
    )


@router.delete(
    "/account",
    status_code=status.HTTP_200_OK,
    summary="Delete account and cascade personal data removal",
)
def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Permanently deletes user account, chat sessions, messages, settings,
    and associated privacy analyses across the database.
    """
    success = auth_service.delete_account(db, current_user.id)
    if not success:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account.",
        )
    db.commit()
    return {"status": "success", "message": "Account and all associated personal data have been deleted."}
