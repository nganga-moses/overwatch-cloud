"""Authentication and workstation registration routes."""

import hashlib
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models.customer import Customer
from app.models.workstation import Workstation
from app.api.dependencies import get_current_customer

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WorkstationRegisterRequest(BaseModel):
    hardware_serial: str
    name: str | None = None
    software_version: str | None = None


class WorkstationRegisterResponse(BaseModel):
    workstation_id: str
    customer_name: str
    registered_at: str

    class Config:
        from_attributes = True


class CustomerCreateRequest(BaseModel):
    """Admin-only: provision a new customer with an API key."""
    name: str
    subscription_tier: str = "starter"
    max_kits: int = 5


class CustomerCreateResponse(BaseModel):
    customer_id: str
    name: str
    api_key: str  # returned once, never stored in plaintext


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/customers", response_model=CustomerCreateResponse, status_code=status.HTTP_201_CREATED)
def create_customer(body: CustomerCreateRequest, db: Session = Depends(get_db)):
    """Provision a new customer and return a one-time API key."""
    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(f"{settings.API_KEY_PEPPER}:{raw_key}".encode()).hexdigest()

    customer = Customer(
        name=body.name,
        api_key_hash=key_hash,
        subscription_tier=body.subscription_tier,
        max_kits=body.max_kits,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    return CustomerCreateResponse(
        customer_id=str(customer.id),
        name=customer.name,
        api_key=raw_key,
    )


@router.post("/workstations/register", response_model=WorkstationRegisterResponse, status_code=status.HTTP_201_CREATED)
def register_workstation(
    body: WorkstationRegisterRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Register a new workstation for the authenticated customer."""
    existing = db.query(Workstation).filter(
        Workstation.hardware_serial == body.hardware_serial
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Workstation with serial {body.hardware_serial} already registered",
        )

    ws = Workstation(
        customer_id=customer.id,
        hardware_serial=body.hardware_serial,
        name=body.name,
        software_version=body.software_version,
    )
    db.add(ws)
    db.commit()
    db.refresh(ws)

    return WorkstationRegisterResponse(
        workstation_id=str(ws.id),
        customer_name=customer.name,
        registered_at=ws.registered_at.isoformat(),
    )
