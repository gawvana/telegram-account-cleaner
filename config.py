import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator


def is_serverless() -> bool:
    return bool(
        os.environ.get("VERCEL")
        or os.environ.get("VERCEL_ENV")
        or os.environ.get("AWS_LAMBDA_FUNCTION_NAME")
        or os.environ.get("LAMBDA_TASK_ROOT")
        or os.path.exists("/var/task")
        or "/var/task" in str(Path(__file__).resolve()).replace("\\", "/")
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Brand & Identity
    APP_NAME: str = "CLIN"
    APP_TITLE: str = "CLIN — Telegram Account Cleaner"
    APP_VERSION: str = "2.1.0"

    # Consent Versions
    AGREEMENT_VERSION: int = 1
    PRIVACY_VERSION: int = 1

    # Telegram Bot
    BOT_TOKEN: str = Field(default="", description="Telegram Bot API Token")
    WEBHOOK_SECRET_TOKEN: str = Field(default="", description="Secret token for Telegram Webhook validation")

    # Telegram MTProto Credentials:
    # Each user provides their own API_ID and API_HASH via the UI (my.telegram.org -> API development tools).
    # No global shared credentials or hardcoded fallback keys are used in production.
    TELEGRAM_API_ID: Optional[int] = Field(default=None, description="Optional default API ID for testing")
    TELEGRAM_API_HASH: Optional[str] = Field(default=None, description="Optional default API Hash for testing")
    API_ID: Optional[int] = Field(default=None, description="Optional default API ID for testing")
    API_HASH: Optional[str] = Field(default=None, description="Optional default API Hash for testing")

    @property
    def effective_api_id(self) -> Optional[int]:
        """Strictly test-only fallback during automated pytest runs; production requires per-user credentials."""
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TESTING"):
            return 12345
        return None

    @property
    def effective_api_hash(self) -> Optional[str]:
        """Strictly test-only fallback during automated pytest runs; production requires per-user credentials."""
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("TESTING"):
            return "0123456789abcdef0123456789abcdef"
        return None

    # Database & Storage (uses /tmp in serverless environment)
    DATABASE_PATH: str = Field(
        default_factory=lambda: "/tmp/cleaner.db" if is_serverless() else "cleaner.db",
        description="Path to SQLite database"
    )
    SESSION_DIR: str = Field(
        default_factory=lambda: "/tmp/sessions" if is_serverless() else "sessions",
        description="Directory for encrypted session files"
    )
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Telegram Mini App (FastAPI)
    WEBAPP_URL: str = Field(default="http://localhost:8080", description="Public HTTPS WebApp URL")
    WEBAPP_HOST: str = Field(default="0.0.0.0", description="FastAPI host")
    WEBAPP_PORT: int = Field(default=8080, description="FastAPI port")

    # Security & Encryption
    ENCRYPTION_MASTER_KEY: str = Field(
        default="",
        description="Base64 Fernet master key for encrypting sessions and sensitive fields"
    )
    JWT_SECRET: str = Field(
        default="",
        description="Secret key for signing JWT tokens (if empty, derived securely or generated)"
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440  # 24 hours

    # Auth State Machine & Timeouts
    AUTH_TIMEOUT_SECONDS: int = 300  # 5 minutes maximum for transient login handshake

    # Rate Limiting
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_SCAN: str = "3/minute"
    RATE_LIMIT_CLEANUP: str = "2/minute"

    # Scheduler (disabled in serverless Vercel)
    SCHEDULER_ENABLED: bool = Field(
        default_factory=lambda: False if is_serverless() else True,
        description="Enable automated scheduled jobs"
    )
    SCHEDULER_TIMEZONE: str = Field(default="UTC", description="Scheduler timezone")

    # Internationalization
    DEFAULT_LANGUAGE: str = Field(default="ru", description="Default language (ru / en / uz)")

    # Welcome Video
    START_VIDEO_PATH: str = Field(default="assets/welcome.mp4", description="Path to welcome video for /start")
    START_VIDEO_FILE_ID: Optional[str] = Field(default=None, description="Telegram file_id of welcome video")

    # Rate Limiting & Safety Limits
    MAX_CONCURRENT_CLIENTS: int = 10
    FLOOD_WAIT_MAX_SLEEP: int = 120  # Max seconds to sleep automatically on FloodWait
    MAX_RETRIES: int = 3
    RATE_LIMIT_DELAY: float = 0.5  # Seconds between destructive actions

    def get_effective_jwt_secret(self) -> str:
        """Returns the configured JWT_SECRET or falls back to a deterministic hash of BOT_TOKEN / MASTER_KEY."""
        insecure_keys = {
            "telegram-account-cleaner-secret-key-change-in-prod",
            "your_super_secret_jwt_key_change_in_production",
        }
        if self.JWT_SECRET and self.JWT_SECRET not in insecure_keys:
            return self.JWT_SECRET
        if self.ENCRYPTION_MASTER_KEY:
            import hashlib
            return hashlib.sha256(f"clin-jwt:{self.ENCRYPTION_MASTER_KEY}".encode()).hexdigest()
        if self.BOT_TOKEN:
            import hashlib
            return hashlib.sha256(f"clin-jwt:{self.BOT_TOKEN}".encode()).hexdigest()
        return "clin-ephemeral-secret-key-development-only"

    def ensure_directories(self) -> None:
        """Ensure necessary storage directories exist."""
        try:
            Path(self.SESSION_DIR).mkdir(parents=True, exist_ok=True)
            db_parent = Path(self.DATABASE_PATH).parent
            if db_parent and str(db_parent) != ".":
                db_parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    @model_validator(mode="after")
    def _apply_serverless_overrides(self) -> "Settings":
        if is_serverless() or "/var/task" in str(Path(self.SESSION_DIR).resolve()).replace("\\", "/"):
            object.__setattr__(self, "SESSION_DIR", "/tmp/sessions")
            object.__setattr__(self, "DATABASE_PATH", "/tmp/cleaner.db")
            object.__setattr__(self, "SCHEDULER_ENABLED", False)
        return self


settings = Settings()
settings.ensure_directories()
