
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.repositories.chat_repository import chat_repository
from app.schemas.chat import (
    ChatMessageResponse,
    ChatProcessRequest,
    ChatProcessResponse,
    ChatSessionDetailResponse,
    ChatSessionResponse,
)
from app.services.privacy.chat_service import chat_service

router = APIRouter(prefix="/chat", tags=["Chat & Academic Interaction"])


@router.post(
    "/sessions",
    response_model=ChatSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
)
def create_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = chat_repository.create_session(db, current_user.id)
    db.commit()
    db.refresh(session)
    return ChatSessionResponse.model_validate(session)


@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
    summary="List active chat sessions for the current user",
)
def list_sessions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = chat_repository.list_sessions(db, current_user.id, limit=limit, offset=offset)
    return [
        ChatSessionResponse(
            id=s.id,
            user_id=s.user_id,
            is_archived=s.is_archived,
            created_at=s.created_at,
            updated_at=s.updated_at,
            message_count=len(s.messages),
        )
        for s in sessions
    ]


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionDetailResponse,
    summary="Get details and permitted history for a session",
)
def get_session_details(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = chat_repository.get_session(db, session_id, current_user.id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or unauthorized.",
        )
    messages = chat_repository.list_messages(db, session_id, current_user.id)
    return ChatSessionDetailResponse(
        session=ChatSessionResponse(
            id=session.id,
            user_id=session.user_id,
            is_archived=session.is_archived,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=len(messages),
        ),
        messages=[ChatMessageResponse.model_validate(m) for m in messages],
    )


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete or archive a chat session",
)
def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    success = chat_repository.delete_session(db, session_id, current_user.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or unauthorized.",
        )
    db.commit()
    return {"status": "success", "message": f"Session {session_id} has been deleted."}


@router.post(
    "/process",
    response_model=ChatProcessResponse,
    summary="Submit user question to the Privacy-Aware Academic Assistant",
)
def process_message(
    request: ChatProcessRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Core interaction endpoint:
    - Analyzes incoming message in memory.
    - Masks PII or separates sensitive parts if mixed.
    - Redirects if high risk / personal crisis.
    - Persists sanitized text only if user explicitly consented to save_chat_history.
    - Preserves academic question for downstream assistance.
    """
    try:
        response = chat_service.process_user_input(
            db,
            raw_message=request.message,
            user_id=current_user.id,
            session_id=request.session_id,
        )
        db.commit()
        return response
    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Processing encountered an error. Personal data was protected in memory.",
        ) from e
