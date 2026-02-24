"""
DNA Backend - Configuration
============================
"""

import os
from typing import List


class Settings:
    """Application settings."""

    # Server
    HOST: str = os.getenv("APP_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("APP_PORT", "3010"))
    ENV: str = os.getenv("APP_ENV", "development")
    RELOAD: bool = os.getenv("APP_RELOAD", "true").lower() == "true"

    # Database
    DATABASE_HOST: str = os.getenv("DATABASE_HOST", "dna-postgres")
    DATABASE_PORT: int = int(os.getenv("DATABASE_PORT", "5432"))
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "dna")
    DATABASE_USER: str = os.getenv("DATABASE_USER", "dna_user")
    DATABASE_PASSWORD: str = os.getenv("DATABASE_PASSWORD", "dna_password_dev")
    DATABASE_APP_SCHEMA: str = os.getenv("DATABASE_APP_SCHEMA", "dna_app")
    DATABASE_AUTH_SCHEMA: str = os.getenv("DATABASE_AUTH_SCHEMA", "auth")
    DATABASE_CUSTOMER_SCHEMA: str = os.getenv("DATABASE_CUSTOMER_SCHEMA", "customer")

    @property
    def DATABASE_URL(self) -> str:
        """Construct database URL."""
        return (
            f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            f"?options=-c%20search_path={self.DATABASE_APP_SCHEMA}"
        )

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "dna-redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")  # Optional, empty in dev
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # Auth Service
    AUTH_SERVICE_URL: str = os.getenv("AUTH_SERVICE_URL", "http://dna-auth:3011")

    # LLM Provider (mirrors ai-service config — used by admin UI)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
    ANTHROPIC_MAX_TOKENS: int = int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096"))
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "3"))
    MAX_COST_PER_TASK_USD: float = float(os.getenv("MAX_COST_PER_TASK_USD", "5.00"))

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dna-secret-key-change-in-production")

    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")

    @property
    def CORS_ORIGINS_LIST(self) -> List[str]:
        """Parse CORS origins."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    def validate(self) -> None:
        """Validate critical settings."""
        pass  # API keys are optional — ai-service holds the real keys


settings = Settings()
