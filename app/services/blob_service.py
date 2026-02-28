"""S3-compatible blob storage service for presigned URL generation."""

import logging

import boto3
from botocore.config import Config as BotoConfig

from app.core.config import settings

logger = logging.getLogger(__name__)


class BlobService:
    def __init__(self):
        self._client = None
        self.bucket = settings.BLOB_STORAGE_BUCKET
        self.expiry_seconds = settings.BLOB_PRESIGN_EXPIRY_SECONDS

    @property
    def client(self):
        if self._client is None:
            kwargs = {
                "service_name": "s3",
                "aws_access_key_id": settings.BLOB_STORAGE_ACCESS_KEY,
                "aws_secret_access_key": settings.BLOB_STORAGE_SECRET_KEY,
                "region_name": settings.BLOB_STORAGE_REGION,
                "config": BotoConfig(signature_version="s3v4"),
            }
            if settings.BLOB_STORAGE_ENDPOINT:
                kwargs["endpoint_url"] = settings.BLOB_STORAGE_ENDPOINT
            self._client = boto3.client(**kwargs)
        return self._client

    def presign_upload(self, key: str, content_type: str = "application/octet-stream") -> str:
        return self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=self.expiry_seconds,
        )

    def presign_download(self, key: str) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=self.expiry_seconds,
        )

    def ensure_bucket(self):
        """Create the bucket if it does not exist (useful for dev with MinIO)."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                self.client.create_bucket(Bucket=self.bucket)
                logger.info("Created bucket: %s", self.bucket)
            except Exception as e:
                logger.warning("Could not create bucket %s: %s", self.bucket, e)


blob_service = BlobService()
