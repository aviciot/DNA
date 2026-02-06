"""
DNA Authentication Service - Configuration Settings
====================================================
All configuration loaded from environment variables with sensible defaults.
"""

import os
from typing import Optional


class Settings:
    """Application settings loaded from environment variables."""

    # Server Configuration
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8401"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Application Metadata
    APP_TITLE: str = os.getenv("APP_TITLE", "DNA Auth Service")
    APP_DESCRIPTION: str = os.getenv("APP_DESCRIPTION", "Authentication and authorization for DNA Dashboard")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")

    # Database Configuration
    DATABASE_HOST: str = os.getenv("DATABASE_HOST", "dna-postgres")
    DATABASE_PORT: int = int(os.getenv("DATABASE_PORT", "5432"))
    DATABASE_NAME: str = os.getenv("DATABASE_NAME", "dna")
    DATABASE_USER: str = os.getenv("DATABASE_USER", "dna_user")
    DATABASE_PASSWORD: str = os.getenv("DATABASE_PASSWORD", "dna_password_dev")
    DATABASE_SCHEMA: str = os.getenv("DATABASE_SCHEMA", "auth")
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct database URL from components."""
        return (
            f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
            f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            f"?options=-c%20search_path={self.DATABASE_SCHEMA}"
        )
    
    DB_POOL_MIN_SIZE: int = int(os.getenv("DB_POOL_MIN_SIZE", "5"))
    DB_POOL_MAX_SIZE: int = int(os.getenv("DB_POOL_MAX_SIZE", "20"))

    # JWT Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dna-secret-key-change-in-production")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dna-jwt-secret-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    # CORS Configuration
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    
    @property
    def CORS_ORIGINS_LIST(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # Authentication Configuration
    DEFAULT_ROLE: str = os.getenv("DEFAULT_ROLE", "viewer")

    @classmethod
    def validate(cls) -> None:
        """Validate critical settings."""
        instance = cls()
        
        # Check secrets are not defaults in production
        environment = os.getenv("APP_ENV", "development")
        if environment == "production":
            if instance.SECRET_KEY == "dna-secret-key-change-in-production":
                raise ValueError(
                    "SECRET_KEY must be set to a secure value in production! "
                    "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
            if instance.JWT_SECRET_KEY == "dna-jwt-secret-change-in-production":
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a secure value in production! "
                    "Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
                )
        
        # Validate database credentials
        if not instance.DATABASE_PASSWORD:
            raise ValueError("DATABASE_PASSWORD must be set!")
        
        # Validate token expiry
        if instance.ACCESS_TOKEN_EXPIRE_MINUTES < 1:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be at least 1")
        if instance.REFRESH_TOKEN_EXPIRE_DAYS < 1:
            raise ValueError("REFRESH_TOKEN_EXPIRE_DAYS must be at least 1")


# Create global settings instance
settings = Settings()
