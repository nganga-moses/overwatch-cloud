"""Application configuration loaded from environment variables."""

from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str

    API_KEY_PEPPER: str = ""

    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
    ]

    API_V1_PREFIX: str = "/api/v1"

    # Google Cloud Storage (uses ADC — no explicit credentials)
    GCS_BUCKET: str = "overwatch-blobs"
    GCS_PRESIGN_EXPIRY_SECONDS: int = 900

    # Supabase JWT validation (for dashboard auth)
    SUPABASE_JWT_SECRET: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
