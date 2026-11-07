from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    APP_NAME: str = "Impervia"
    APP_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # Security
    SECRET_KEY: str = "impervia-privacy-aware-secret-key-change-in-production-min32chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Aiven PostgreSQL Database
    DB_HOST: str
    DB_PORT: int = 5432
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    DB_SSLMODE: str = "require"

    # Privacy Pipeline Defaults
    DEFAULT_RETENTION_DAYS: int = 30
    DETECTOR_VERSION: str = "impervia-pipeline-v1.0"

    # Local SLM Intelligence Layer (Zero-Cloud Privacy Configuration)
    SLM_ENABLED: bool = True
    SLM_AUTO_START: bool = True
    SLM_PROVIDER: str = "ollama"  # "ollama" or "custom_http"
    SLM_ENDPOINT: str = "http://127.0.0.1:11434"
    SLM_MODEL_NAME: str = "qwen2.5:1.5b"  # e.g. "qwen2.5:1.5b", "gemma2:2b", "llama3.2:1b", "phi3:mini"
    SLM_TIMEOUT_SECONDS: float = 6.0
    SLM_TEMPERATURE: float = 0.0

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
