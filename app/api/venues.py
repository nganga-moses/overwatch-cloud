"""Venue CRUD, zone/perch-point/connection CRUD, and floor plan ingestion."""

import json
import logging
import tempfile
import uuid
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_customer
from app.database.session import get_db
from app.models.customer import Customer
from app.models.ingestion_job import IngestionJob
from app.models.perch_point import PerchPoint
from app.models.venue import Venue
from app.models.venue_zone import VenueZone
from app.models.zone_connection import ZoneConnection
from app.services.blob_service import blob_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/venues", tags=["venues"])


# ---------------------------------------------------------------------------
# Venue schemas
# ---------------------------------------------------------------------------

class VenueResponse(BaseModel):
    id: str
    name: str
    type: str | None = None
    environment: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    floor_plan_source: str | None = None
    floor_plan_blob_key: str | None = None
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
# Zone schemas
# ---------------------------------------------------------------------------

class ZoneResponse(BaseModel):
    id: str
    venue_id: str
    name: str
    type: str | None = None
    environment: str | None = None
    tier_requirement: str | None = None
    floor_level: int | None = None
    polygon_json: str | None = None
    centroid_lat: float | None = None
    centroid_lon: float | None = None
    ceiling_height_m: float | None = None
    area_sq_m: float | None = None
    coverage_priority: str | None = None
    notes: str | None = None
    perch_point_count: int = 0

    class Config:
        from_attributes = True


class ZoneCreateRequest(BaseModel):
    name: str
    type: str | None = None
    environment: str | None = None
    tier_requirement: str | None = None
    floor_level: int | None = 0
    polygon_json: str | None = None
    centroid_lat: float | None = None
    centroid_lon: float | None = None
    ceiling_height_m: float | None = None
    area_sq_m: float | None = None
    coverage_priority: str | None = None
    notes: str | None = None


class ZoneUpdateRequest(BaseModel):
    name: str | None = None
    type: str | None = None
    environment: str | None = None
    tier_requirement: str | None = None
    floor_level: int | None = None
    polygon_json: str | None = None
    centroid_lat: float | None = None
    centroid_lon: float | None = None
    ceiling_height_m: float | None = None
    area_sq_m: float | None = None
    coverage_priority: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Connection schemas
# ---------------------------------------------------------------------------

class ConnectionResponse(BaseModel):
    id: str
    venue_id: str
    from_zone_id: str
    to_zone_id: str
    connection_type: str | None = None
    position_json: str | None = None
    width_m: float | None = None
    height_m: float | None = None

    class Config:
        from_attributes = True


class ConnectionCreateRequest(BaseModel):
    from_zone_id: str
    to_zone_id: str
    connection_type: str | None = None
    position_json: str | None = None
    width_m: float | None = None
    height_m: float | None = None


# ---------------------------------------------------------------------------
# Perch point schemas
# ---------------------------------------------------------------------------

class PerchPointResponse(BaseModel):
    id: str
    venue_id: str
    zone_id: str | None = None
    position_json: str | None = None
    height_m: float | None = None
    surface_class: str | None = None
    surface_orientation: str | None = None
    attachment_method: str | None = None
    tier_required: str | None = None
    spine_confidence: float | None = None
    suction_confidence: float | None = None
    landing_gear_viable: int | None = None
    coverage_value: float | None = None
    attempt_count: int = 0
    success_count: int = 0
    avg_hold_duration_s: float | None = None
    status: str | None = None

    class Config:
        from_attributes = True


class PerchPointCreateRequest(BaseModel):
    position_json: str | None = None
    height_m: float | None = None
    surface_class: str | None = None
    surface_orientation: str | None = None
    attachment_method: str | None = None
    tier_required: str | None = None
    coverage_value: float | None = None


class PerchPointUpdateRequest(BaseModel):
    position_json: str | None = None
    height_m: float | None = None
    surface_class: str | None = None
    surface_orientation: str | None = None
    attachment_method: str | None = None
    tier_required: str | None = None
    coverage_value: float | None = None
    status: str | None = None


# ---------------------------------------------------------------------------
# Ingestion schemas
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    blob_key: str
    format: str  # dxf, pdf, image
    floor_level: int = 0
    scale_m_per_unit: float | None = None
    page_number: int | None = None  # None = all pages (PDF only), N = specific page (1-indexed)


class IngestResponse(BaseModel):
    job_id: str
    status: str
    zone_count: int | None = None
    connection_count: int | None = None
    perch_point_count: int | None = None
    pages_processed: int | None = None
    error_message: str | None = None


class PageCountResponse(BaseModel):
    page_count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_venue(db: Session, customer: Customer, venue_id: str) -> Venue:
    venue = db.query(Venue).filter(
        Venue.id == venue_id, Venue.customer_id == customer.id,
    ).first()
    if not venue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venue not found")
    return venue


def _get_zone(db: Session, customer: Customer, zone_id: str) -> VenueZone:
    zone = db.query(VenueZone).filter(
        VenueZone.id == zone_id, VenueZone.customer_id == customer.id,
    ).first()
    if not zone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zone not found")
    return zone


# ---------------------------------------------------------------------------
# Venue routes
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
    return _get_venue(db, customer, venue_id)


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
    venue = _get_venue(db, customer, venue_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(venue, field, value)
    venue.cloud_version += 1
    db.commit()
    db.refresh(venue)
    return venue


@router.delete("/{venue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_venue(
    venue_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    venue = _get_venue(db, customer, venue_id)
    db.delete(venue)
    db.commit()


# ---------------------------------------------------------------------------
# Zone routes
# ---------------------------------------------------------------------------

@router.get("/{venue_id}/zones", response_model=List[ZoneResponse])
def list_zones(
    venue_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    _get_venue(db, customer, venue_id)
    zones = db.query(VenueZone).filter(
        VenueZone.venue_id == venue_id,
        VenueZone.customer_id == customer.id,
    ).all()
    result = []
    for z in zones:
        pp_count = db.query(PerchPoint).filter(PerchPoint.zone_id == z.id).count()
        resp = ZoneResponse.model_validate(z)
        resp.perch_point_count = pp_count
        result.append(resp)
    return result


@router.post("/{venue_id}/zones", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
def create_zone(
    venue_id: str,
    body: ZoneCreateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    _get_venue(db, customer, venue_id)
    zone = VenueZone(
        venue_id=venue_id,
        customer_id=customer.id,
        **body.model_dump(),
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    resp = ZoneResponse.model_validate(zone)
    resp.perch_point_count = 0
    return resp


@router.patch("/zones/{zone_id}", response_model=ZoneResponse)
def update_zone(
    zone_id: str,
    body: ZoneUpdateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    zone = _get_zone(db, customer, zone_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(zone, field, value)
    zone.cloud_version += 1
    db.commit()
    db.refresh(zone)
    pp_count = db.query(PerchPoint).filter(PerchPoint.zone_id == zone.id).count()
    resp = ZoneResponse.model_validate(zone)
    resp.perch_point_count = pp_count
    return resp


@router.delete("/zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(
    zone_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    zone = _get_zone(db, customer, zone_id)
    db.delete(zone)
    db.commit()


# ---------------------------------------------------------------------------
# Connection routes
# ---------------------------------------------------------------------------

@router.get("/{venue_id}/connections", response_model=List[ConnectionResponse])
def list_connections(
    venue_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    _get_venue(db, customer, venue_id)
    return db.query(ZoneConnection).filter(
        ZoneConnection.venue_id == venue_id,
        ZoneConnection.customer_id == customer.id,
    ).all()


@router.post("/{venue_id}/connections", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
def create_connection(
    venue_id: str,
    body: ConnectionCreateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    _get_venue(db, customer, venue_id)
    conn = ZoneConnection(
        venue_id=venue_id,
        customer_id=customer.id,
        **body.model_dump(),
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    conn = db.query(ZoneConnection).filter(
        ZoneConnection.id == connection_id,
        ZoneConnection.customer_id == customer.id,
    ).first()
    if not conn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Connection not found")
    db.delete(conn)
    db.commit()


# ---------------------------------------------------------------------------
# Perch point routes
# ---------------------------------------------------------------------------

@router.get("/zones/{zone_id}/perch-points", response_model=List[PerchPointResponse])
def list_perch_points(
    zone_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    _get_zone(db, customer, zone_id)
    return db.query(PerchPoint).filter(
        PerchPoint.zone_id == zone_id,
        PerchPoint.customer_id == customer.id,
    ).all()


@router.post("/zones/{zone_id}/perch-points", response_model=PerchPointResponse, status_code=status.HTTP_201_CREATED)
def create_perch_point(
    zone_id: str,
    body: PerchPointCreateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    zone = _get_zone(db, customer, zone_id)
    pp = PerchPoint(
        venue_id=zone.venue_id,
        zone_id=zone_id,
        customer_id=customer.id,
        **body.model_dump(),
    )
    db.add(pp)
    db.commit()
    db.refresh(pp)
    return pp


@router.patch("/perch-points/{point_id}", response_model=PerchPointResponse)
def update_perch_point(
    point_id: str,
    body: PerchPointUpdateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    pp = db.query(PerchPoint).filter(
        PerchPoint.id == point_id, PerchPoint.customer_id == customer.id,
    ).first()
    if not pp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perch point not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(pp, field, value)
    pp.cloud_version += 1
    db.commit()
    db.refresh(pp)
    return pp


@router.delete("/perch-points/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_perch_point(
    point_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    pp = db.query(PerchPoint).filter(
        PerchPoint.id == point_id, PerchPoint.customer_id == customer.id,
    ).first()
    if not pp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perch point not found")
    db.delete(pp)
    db.commit()


# ---------------------------------------------------------------------------
# Floor plan ingestion
# ---------------------------------------------------------------------------

@router.post("/{venue_id}/page-count", response_model=PageCountResponse)
def get_page_count(
    venue_id: str,
    body: IngestRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Get page count for a PDF blob. Returns 1 for non-PDF formats."""
    _get_venue(db, customer, venue_id)

    if body.format != "pdf":
        return PageCountResponse(page_count=1)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    try:
        blob_service.download_to_file(body.blob_key, tmp.name)
        tmp.close()

        from app.services.floor_plan_ingestion import get_pdf_page_count
        count = get_pdf_page_count(tmp.name)
        return PageCountResponse(page_count=count)
    finally:
        import os
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


@router.post("/{venue_id}/ingest", response_model=IngestResponse)
def ingest_floor_plan(
    venue_id: str,
    body: IngestRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    venue = _get_venue(db, customer, venue_id)

    job = IngestionJob(
        customer_id=customer.id,
        venue_id=venue_id,
        blob_key=body.blob_key,
        format=body.format,
        floor_level=body.floor_level,
        status="processing",
    )
    db.add(job)
    db.flush()

    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=f".{body.format}")
        blob_service.download_to_file(body.blob_key, tmp.name)
        tmp.close()

        from app.services.floor_plan_ingestion import ingest

        result = ingest(
            file_path=tmp.name,
            fmt=body.format if body.format != "image" else "image",
            venue_lat=venue.lat or 0.0,
            venue_lon=venue.lon or 0.0,
            floor_level=body.floor_level,
            scale_m_per_unit=body.scale_m_per_unit,
            page_number=body.page_number,
        )

        for z in result.zones:
            zone = VenueZone(
                id=uuid.UUID(z.id),
                venue_id=venue_id,
                customer_id=customer.id,
                name=z.name,
                type=z.type,
                environment=z.environment,
                tier_requirement=z.tier_requirement,
                floor_level=z.floor_level,
                polygon_json=json.dumps(z.polygon),
                centroid_lat=z.centroid_lat,
                centroid_lon=z.centroid_lon,
                area_sq_m=z.area_sq_m,
                coverage_priority=str(z.coverage_priority),
            )
            db.add(zone)

        for c in result.connections:
            conn = ZoneConnection(
                id=uuid.UUID(c.id),
                venue_id=venue_id,
                customer_id=customer.id,
                from_zone_id=uuid.UUID(c.from_zone_id),
                to_zone_id=uuid.UUID(c.to_zone_id),
                connection_type=c.connection_type,
                position_json=json.dumps(c.position) if c.position else None,
            )
            db.add(conn)

        for pp in result.perch_points:
            perch = PerchPoint(
                id=uuid.UUID(pp.id),
                venue_id=venue_id,
                zone_id=uuid.UUID(pp.zone_id),
                customer_id=customer.id,
                surface_class=pp.surface_class,
                surface_orientation=pp.surface_orientation,
                tier_required=pp.tier_required,
                position_json=json.dumps({"lat": pp.position_lat, "lon": pp.position_lon}),
                height_m=pp.height_m,
                wall_normal_json=json.dumps(pp.wall_normal) if pp.wall_normal else None,
                coverage_value=pp.coverage_value,
                status="candidate",
            )
            db.add(perch)

        venue.floor_plan_blob_key = body.blob_key
        venue.floor_plan_source = body.format
        venue.cloud_version += 1

        floor_levels_seen = set(z.floor_level for z in result.zones)
        pages_processed = len(floor_levels_seen) if floor_levels_seen else 1

        job.status = "completed"
        job.zone_count = len(result.zones)
        job.connection_count = len(result.connections)
        job.perch_point_count = len(result.perch_points)
        job.completed_at = datetime.now(timezone.utc)

        db.commit()

        return IngestResponse(
            job_id=str(job.id),
            status="completed",
            zone_count=job.zone_count,
            connection_count=job.connection_count,
            perch_point_count=job.perch_point_count,
            pages_processed=pages_processed,
        )

    except Exception as e:
        logger.exception("Ingestion failed for venue %s", venue_id)
        job.status = "failed"
        job.error_message = str(e)
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        return IngestResponse(
            job_id=str(job.id),
            status="failed",
            error_message=str(e),
        )
    finally:
        import os
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


@router.get("/{venue_id}/ingest/{job_id}", response_model=IngestResponse)
def get_ingestion_status(
    venue_id: str,
    job_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    _get_venue(db, customer, venue_id)
    job = db.query(IngestionJob).filter(
        IngestionJob.id == job_id,
        IngestionJob.customer_id == customer.id,
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ingestion job not found")
    return IngestResponse(
        job_id=str(job.id),
        status=job.status,
        zone_count=job.zone_count,
        connection_count=job.connection_count,
        perch_point_count=job.perch_point_count,
        error_message=job.error_message,
    )
