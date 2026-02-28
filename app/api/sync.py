"""Delta sync endpoints — push, pull, bootstrap."""

from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_customer
from app.database.session import get_db
from app.models.customer import Customer
from app.models.workstation import Workstation
from app.services.sync_service import sync_service

router = APIRouter(prefix="/sync", tags=["sync"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SyncEntity(BaseModel):
    """A single entity in a delta payload."""
    table: str
    id: str
    data: Dict[str, Any]
    cloud_version: int | None = None


class DeltaPushRequest(BaseModel):
    workstation_id: str
    entities: List[SyncEntity]


class DeltaPushResponse(BaseModel):
    accepted: int
    rejected: int
    new_cloud_version: int
    conflicts: List[Dict[str, Any]] = []


class DeltaPullResponse(BaseModel):
    entities: List[SyncEntity]
    cloud_version: int


class BootstrapResponse(BaseModel):
    venues: List[Dict[str, Any]]
    venue_zones: List[Dict[str, Any]]
    zone_connections: List[Dict[str, Any]]
    perch_points: List[Dict[str, Any]]
    kits: List[Dict[str, Any]]
    drones: List[Dict[str, Any]]
    principals: List[Dict[str, Any]]
    wm_nodes: List[Dict[str, Any]]
    wm_edges: List[Dict[str, Any]]
    cloud_version: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_workstation(db: Session, customer: Customer, workstation_id: str) -> Workstation:
    ws = db.query(Workstation).filter(
        Workstation.id == workstation_id,
        Workstation.customer_id == customer.id,
    ).first()
    if not ws:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workstation not found or not owned by this customer",
        )
    return ws


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/push", response_model=DeltaPushResponse)
def delta_push(
    body: DeltaPushRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Accept changed entities from a workstation."""
    ws = _get_workstation(db, customer, body.workstation_id)
    result = sync_service.apply_push(db, customer, ws, body.entities)

    ws.last_sync_at = datetime.utcnow()
    ws.last_seen_at = datetime.utcnow()
    db.commit()

    return result


@router.get("/pull", response_model=DeltaPullResponse)
def delta_pull(
    workstation_id: str = Query(...),
    since: int = Query(0, ge=0, description="Cloud version to pull changes since"),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Return entities changed since the given cloud version."""
    ws = _get_workstation(db, customer, workstation_id)
    result = sync_service.build_pull(db, customer, since)

    ws.last_seen_at = datetime.utcnow()
    db.commit()

    return result


@router.get("/bootstrap", response_model=BootstrapResponse)
def bootstrap(
    workstation_id: str = Query(...),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Return full state for a new workstation setup."""
    ws = _get_workstation(db, customer, workstation_id)
    result = sync_service.build_bootstrap(db, customer)

    ws.last_sync_at = datetime.utcnow()
    ws.last_seen_at = datetime.utcnow()
    db.commit()

    return result
