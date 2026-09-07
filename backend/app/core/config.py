from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> project root is 3 levels up
BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    # Falls back to a local SQLite file when DATABASE_URL isn't set (local dev).
    # Railway injects a real DATABASE_URL for its managed PostgreSQL instance.
    DATABASE_URL: str = "sqlite:///./event_ticketing.db"
    SECRET_KEY: str
    MP_ACCESS_TOKEN: str | None = None
    MP_PUBLIC_KEY: str | None = None
    MP_WEBHOOK_SECRET: str | None = None
    RESEND_API_KEY: str | None = None
    RESEND_FROM_EMAIL: str = "Ingressos <ingressos@resend.dev>"
    PORTARIA_SECRET_KEY: str | None = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    # Optional extra exact origin allowed for CORS (e.g. a future custom domain).
    EXTRA_CORS_ORIGIN: str | None = None

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
        case_sensitive=False,
    )

    @field_validator("DATABASE_URL")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        # Railway (and Heroku-style providers) hand out "postgres://", but
        # SQLAlchemy 2.x / psycopg2 require the "postgresql://" scheme.
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql://", 1)
        return value


settings = Settings()
