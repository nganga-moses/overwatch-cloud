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

    # Blob storage (S3-compatible)
    BLOB_STORAGE_ENDPOINT: str = ""
    BLOB_STORAGE_ACCESS_KEY: str = ""
    BLOB_STORAGE_SECRET_KEY: str = ""
    BLOB_STORAGE_BUCKET: str = "overwatch-blobs"
    BLOB_STORAGE_REGION: str = "us-east-1"
    BLOB_PRESIGN_EXPIRY_SECONDS: int = 900

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
