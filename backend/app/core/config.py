from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    APP_NAME: str = "Restaurant Management API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # PostgreSQL Database URL using psycopg 3 synchronous driver
    DATABASE_URL: str = "postgresql+psycopg://postgres:your_password_here@localhost:5432/restaurant_db"

    # Authentication & JWT Configuration
    JWT_SECRET_KEY: str = "c7d91e6b8a24f0d3e5a1b7c9f8e2d4a6b5c3e1f7a9d8c4b2e6f0a3d5b7c9e1f8"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours shift duration
    COOKIE_NAME: str = "restaurant_access_token"
    CSRF_COOKIE_NAME: str = "restaurant_csrf_token"
    COOKIE_SECURE: bool = False  # Enforced True in production
    COOKIE_SAMESITE: str = "lax"

    # Razorpay Payment Gateway Configuration (Test Mode Sandbox)
    RAZORPAY_KEY_ID: str = "rzp_test_placeholder"
    RAZORPAY_KEY_SECRET: str = "placeholder_secret"
    RAZORPAY_WEBHOOK_SECRET: str = "placeholder_webhook_secret"
    RAZORPAY_CURRENCY: str = "INR"

    # SQLAlchemy connection pool tuning
    # Conservative defaults suit small hosted instances (e.g. Neon free tier).
    # Override via environment variables to raise limits on dedicated databases.
    # Max simultaneous connections = DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW
    DATABASE_POOL_SIZE: int = 3       # steady-state connections kept open
    DATABASE_MAX_OVERFLOW: int = 2    # extra connections allowed under burst load
    DATABASE_POOL_TIMEOUT: int = 30   # seconds to wait for a free connection
    DATABASE_POOL_RECYCLE: int = 1800 # seconds before a connection is recycled

    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context) -> None:
        """Validate safety constraints for production environments."""
        if self.APP_ENV == "production":
            # 1. Force debug mode off in production
            self.DEBUG = False
            # 2. Enforce HTTPS cookies in production
            self.COOKIE_SECURE = True
            # 3. Reject development fallback secrets in production
            insecure_keys = (
                "c7d91e6b8a24f0d3e5a1b7c9f8e2d4a6b5c3e1f7a9d8c4b2e6f0a3d5b7c9e1f8",
                "a4f8e2c7d91b6f3e5a1d7c9b8f0e2a4d6b5c3e1f7a9d8c4b2e6f0a3d5b7c9e1",
                "generate_a_secure_random_hex_key_here_for_production",
                "secret",
                "changeme",
            )
            if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY in insecure_keys or len(self.JWT_SECRET_KEY.strip()) < 32:
                raise ValueError(
                    "Production safety violation: JWT_SECRET_KEY must be explicitly configured "
                    "with a secure random string of at least 32 characters."
                )
            # 4. Reject default database placeholder credentials in production
            if "your_password_here" in self.DATABASE_URL:
                raise ValueError(
                    "Production safety violation: DATABASE_URL contains placeholder credentials."
                )
            # 5. Disallow empty or wildcard CORS in production
            if not self.cors_origins:
                raise ValueError(
                    "Production safety violation: ALLOWED_ORIGINS must specify at least one trusted origin."
                )
            for origin in self.cors_origins:
                if origin == "*":
                    raise ValueError(
                        "Production safety violation: Wildcard origin '*' is not allowed when credentials are enabled."
                    )

    @property
    def cors_origins(self) -> List[str]:
        """Parse comma-separated allowed origins into a list for CORS middleware."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def sanitized_database_url(self) -> str:
        """Return the database URL with the password masked for safe reporting and logging."""
        try:
            if "@" in self.DATABASE_URL:
                user_part, host_part = self.DATABASE_URL.split("@", 1)
                if ":" in user_part:
                    proto_user, _ = user_part.rsplit(":", 1)
                    return f"{proto_user}:***@{host_part}"
        except Exception:
            return "postgresql+psycopg://***"
        return self.DATABASE_URL


settings = Settings()
