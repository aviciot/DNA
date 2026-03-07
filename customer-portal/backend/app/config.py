from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://portal_user:portal_pass@dna-postgres:5432/dna"
    redis_url: str = "redis://dna-redis:6379/2"
    database_app_schema: str = "dna_app"
    portal_token_max_age_days: int = 7
    max_upload_size_mb: int = 20
    storage_path: str = "/app/storage"
    require_av_scan: bool = True
    clamav_host: str = "portal-clamav"
    clamav_port: int = 3310
    secret_key: str = "dna-secret-key-change-in-production"
    host: str = "0.0.0.0"
    port: int = 4010
    mcp_url: str = "http://customer_portal_mcp:8000"
    mcp_enabled: bool = True

    class Config:
        env_file = ".env"


settings = Settings()
