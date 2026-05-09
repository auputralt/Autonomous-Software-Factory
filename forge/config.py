"""Centralised configuration via Pydantic v2 settings."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Core API Secrets (Using SecretStr to prevent log leaks)
    GEMINI_API_KEY: SecretStr = Field(
        default=SecretStr(""),
        description="Google Gemini API Key",
    )

    # Infrastructure
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0")

    # Sandbox & Limits
    MAX_BUILD_ATTEMPTS: int = Field(default=5, ge=1, le=10)
    SANDBOX_TIMEOUT_SECS: int = Field(default=30, ge=5, le=300)
    SANDBOX_MAX_MEMORY_MB: int = Field(default=512, ge=128)
    DOWNLOAD_DIR: str = Field(default="/tmp/forge_builds")
    DAILY_REQUEST_LIMIT: int = Field(default=200, ge=1)

    # Model Selection
    MANAGER_MODEL: str = Field(default="gemini-2.0-flash")
    DEVELOPER_MODEL: str = Field(default="gemini-2.0-flash")
    TESTER_MODEL: str = Field(default="gemini-2.0-flash")

    # Pydantic v2 Config
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
