"""Presigned URL generation for blob storage (floor plans, 3D models, snapshots)."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.dependencies import get_current_customer
from app.models.customer import Customer
from app.services.blob_service import blob_service

router = APIRouter(prefix="/blobs", tags=["blobs"])


class PresignedUrlResponse(BaseModel):
    url: str
    key: str
    expires_in: int


@router.get("/upload-url", response_model=PresignedUrlResponse)
def get_upload_url(
    key: str = Query(..., description="Object key, e.g. venues/{id}/floorplan.pdf"),
    content_type: str = Query("application/octet-stream"),
    customer: Customer = Depends(get_current_customer),
):
    """Generate a presigned PUT URL for uploading a blob."""
    namespaced_key = f"{customer.id}/{key}"
    url = blob_service.presign_upload(namespaced_key, content_type)
    return PresignedUrlResponse(
        url=url,
        key=namespaced_key,
        expires_in=blob_service.expiry_seconds,
    )


@router.get("/download-url", response_model=PresignedUrlResponse)
def get_download_url(
    key: str = Query(..., description="Full object key"),
    customer: Customer = Depends(get_current_customer),
):
    """Generate a presigned GET URL for downloading a blob."""
    if not key.startswith(str(customer.id)):
        namespaced_key = f"{customer.id}/{key}"
    else:
        namespaced_key = key

    url = blob_service.presign_download(namespaced_key)
    return PresignedUrlResponse(
        url=url,
        key=namespaced_key,
        expires_in=blob_service.expiry_seconds,
    )
