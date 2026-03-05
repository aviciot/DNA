"""Automation Service Configuration — loaded from env vars + DB."""
import os


class Settings:
    # Database (same as other services)
    DATABASE_HOST: str = os.getenv("DATABASE_HOST", "dna-postgres")
    DATABASE_PORT: int = int(os.getenv("DATABASE_PORT", "5432"))
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "dna")
    DATABASE_USER: str = os.getenv("DATABASE_USER", "dna_user")
    DATABASE_PASSWORD: str = os.getenv("DATABASE_PASSWORD", "dna_password_dev")
    DATABASE_APP_SCHEMA: str = os.getenv("DATABASE_APP_SCHEMA", "dna_app")

    @property
    def DATABASE_URL(self) -> str:
        return (f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
                f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}")

    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "dna-redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    @property
    def REDIS_URL(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # LLM API keys (read from env; active provider/model read from DB)
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # Encryption key (must match backend SECRET_KEY so credentials decrypt correctly)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dna-secret-key-change-in-production")

    # Storage
    CUSTOMER_STORAGE_PATH: str = os.getenv("CUSTOMER_STORAGE_PATH", "/app/storage/customers")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
