from app.repositories.academic_repository import AcademicRepository, academic_repository
from app.repositories.analytics_repository import (
    AnalyticsRepository,
    analytics_repository,
)
from app.repositories.audit_repository import AuditRepository, audit_repository
from app.repositories.chat_repository import ChatRepository, chat_repository
from app.repositories.privacy_repository import PrivacyRepository, privacy_repository
from app.repositories.user_repository import UserRepository, user_repository

__all__ = [
    "AcademicRepository",
    "AnalyticsRepository",
    "AuditRepository",
    "ChatRepository",
    "PrivacyRepository",
    "UserRepository",
    "academic_repository",
    "analytics_repository",
    "audit_repository",
    "chat_repository",
    "privacy_repository",
    "user_repository",
]
