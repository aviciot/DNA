"""
AI Service Configuration
========================

All configuration loaded from environment variables.
"""

import os


class Settings:
    """AI Service settings."""

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
        )

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "dna-redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    @property
    def REDIS_URL(self) -> str:
        """Construct Redis URL."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # LLM Provider Configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini")  # "anthropic" or "gemini"

    # Anthropic (Claude)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")

    # Google (Gemini)
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

    # OpenAI (for future use)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Worker Configuration
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "3"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    ENABLE_COST_TRACKING: bool = os.getenv("ENABLE_COST_TRACKING", "true").lower() == "true"
    MAX_COST_PER_TASK_USD: float = float(os.getenv("MAX_COST_PER_TASK_USD", "5.00"))

    # File Upload Path (shared volume with backend)
    UPLOAD_PATH: str = os.getenv("UPLOAD_PATH", "/app/uploads")

    def validate(self) -> None:
        """Validate critical settings."""
        # Validate LLM provider
        if self.LLM_PROVIDER not in ["anthropic", "gemini"]:
            raise ValueError("LLM_PROVIDER must be 'anthropic' or 'gemini'")

        # Check appropriate API key is set
        if self.LLM_PROVIDER == "anthropic" and not self.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY must be set when using Anthropic provider!")

        if self.LLM_PROVIDER == "gemini" and not self.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY must be set when using Gemini provider!")

        if self.WORKER_CONCURRENCY < 1:
            raise ValueError("WORKER_CONCURRENCY must be at least 1")

        if self.MAX_COST_PER_TASK_USD <= 0:
            raise ValueError("MAX_COST_PER_TASK_USD must be positive")


settings = Settings()
