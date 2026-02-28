"""Kit registry and drone assignment routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_customer
from app.database.session import get_db
from app.models.customer import Customer
from app.models.drone import Drone
from app.models.kit import Kit

router = APIRouter(prefix="/kits", tags=["kits"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DroneResponse(BaseModel):
    id: str
    serial: str
    tier: str
    callsign: str | None = None
    hardware_class: str | None = None
    spine_array_condition: str | None = None
    suction_pump_condition: str | None = None
    landing_gear_condition: str | None = None

    class Config:
        from_attributes = True


class KitResponse(BaseModel):
    id: str
    serial: str
    name: str | None = None
    config: str
    tier_composition: dict | None = None
    status: str
    charger_serial: str | None = None
    case_model: str | None = None
    drones: List[DroneResponse] = []

    class Config:
        from_attributes = True


class KitCreateRequest(BaseModel):
    serial: str
    name: str | None = None
    config: str  # alpha, bravo, charlie
    tier_composition: dict | None = None
    charger_serial: str | None = None
    case_model: str | None = None


class DroneCreateRequest(BaseModel):
    serial: str
    tier: str  # tier_1, tier_2
    callsign: str | None = None
    hardware_class: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=List[KitResponse])
def list_kits(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    kits = (
        db.query(Kit)
        .filter(Kit.customer_id == customer.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return kits


@router.get("/{serial}", response_model=KitResponse)
def get_kit_by_serial(
    serial: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Fetch a kit by its physical serial number (used during onboarding)."""
    kit = (
        db.query(Kit)
        .filter(Kit.customer_id == customer.id, Kit.serial == serial)
        .first()
    )
    if not kit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kit not found")
    return kit


@router.post("", response_model=KitResponse, status_code=status.HTTP_201_CREATED)
def create_kit(
    body: KitCreateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    kit = Kit(customer_id=customer.id, **body.model_dump())
    db.add(kit)
    db.commit()
    db.refresh(kit)
    return kit


@router.post("/{kit_id}/drones", response_model=DroneResponse, status_code=status.HTTP_201_CREATED)
def add_drone_to_kit(
    kit_id: str,
    body: DroneCreateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    kit = db.query(Kit).filter(Kit.id == kit_id, Kit.customer_id == customer.id).first()
    if not kit:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kit not found")

    drone = Drone(customer_id=customer.id, kit_id=kit.id, **body.model_dump())
    db.add(drone)
    db.commit()
    db.refresh(drone)
    return drone
