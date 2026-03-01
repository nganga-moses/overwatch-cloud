"""Google Cloud Storage service using Application Default Credentials."""

import logging
from datetime import timedelta

from google.cloud import storage

from app.core.config import settings

logger = logging.getLogger(__name__)


class BlobService:
    def __init__(self):
        self._client: storage.Client | None = None
        self.bucket_name = settings.GCS_BUCKET
        self.expiry_seconds = settings.GCS_PRESIGN_EXPIRY_SECONDS

    @property
    def client(self) -> storage.Client:
        if self._client is None:
            self._client = storage.Client()
        return self._client

    @property
    def bucket(self) -> storage.Bucket:
        return self.client.bucket(self.bucket_name)

    def presign_upload(self, key: str, content_type: str = "application/octet-stream") -> str:
        blob = self.bucket.blob(key)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=self.expiry_seconds),
            method="PUT",
            content_type=content_type,
        )

    def presign_download(self, key: str) -> str:
        blob = self.bucket.blob(key)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=self.expiry_seconds),
            method="GET",
        )

    def download_to_file(self, key: str, destination_path: str) -> None:
        blob = self.bucket.blob(key)
        blob.download_to_filename(destination_path)

    def ensure_bucket(self):
        try:
            self.bucket.reload()
        except Exception:
            try:
                self.client.create_bucket(self.bucket_name)
                logger.info("Created bucket: %s", self.bucket_name)
            except Exception as e:
                logger.warning("Could not create bucket %s: %s", self.bucket_name, e)


blob_service = BlobService()
