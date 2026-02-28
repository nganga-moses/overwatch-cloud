"""Venue CRUD and search routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_customer
from app.database.session import get_db
from app.models.customer import Customer
from app.models.venue import Venue

router = APIRouter(prefix="/venues", tags=["venues"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class VenueResponse(BaseModel):
    id: str
    name: str
    type: str | None = None
    environment: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    deployment_count: int
    avg_deploy_time_s: float | None = None
    tags: str | None = None
    cloud_version: int
    created_at: str

    class Config:
        from_attributes = True


class VenueCreateRequest(BaseModel):
    name: str
    type: str | None = None
    environment: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    tags: str | None = None
    notes: str | None = None


class VenueUpdateRequest(BaseModel):
    name: str | None = None
    type: str | None = None
    environment: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    tags: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=List[VenueResponse])
def list_venues(
    venue_type: str | None = Query(None, alias="type"),
    search: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    q = db.query(Venue).filter(Venue.customer_id == customer.id)
    if venue_type:
        q = q.filter(Venue.type == venue_type)
    if search:
        q = q.filter(Venue.name.ilike(f"%{search}%"))
    return q.order_by(Venue.updated_at.desc()).offset(skip).limit(limit).all()


@router.get("/{venue_id}", response_model=VenueResponse)
def get_venue(
    venue_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    venue = db.query(Venue).filter(Venue.id == venue_id, Venue.customer_id == customer.id).first()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found")
    return venue


@router.post("", response_model=VenueResponse, status_code=status.HTTP_201_CREATED)
def create_venue(
    body: VenueCreateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    venue = Venue(customer_id=customer.id, **body.model_dump())
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


@router.patch("/{venue_id}", response_model=VenueResponse)
def update_venue(
    venue_id: str,
    body: VenueUpdateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    venue = db.query(Venue).filter(Venue.id == venue_id, Venue.customer_id == customer.id).first()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(venue, field, value)

    venue.cloud_version += 1
    db.commit()
    db.refresh(venue)
    return venue
