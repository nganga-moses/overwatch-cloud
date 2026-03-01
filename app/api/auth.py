"""Authentication, workstation activation, and operator management."""

import hashlib
import json
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.hash import bcrypt
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_customer, get_dashboard_user
from app.core.config import settings
from app.database.session import get_db
from app.models.activation_code import ActivationCode
from app.models.customer import Customer
from app.models.dashboard_user import DashboardUser
from app.models.operator import Operator
from app.models.workstation import Workstation

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CustomerCreateRequest(BaseModel):
    name: str
    subscription_tier: str = "starter"
    max_kits: int = 5


class CustomerCreateResponse(BaseModel):
    customer_id: str
    name: str
    api_key: str


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


class ActivationCodeResponse(BaseModel):
    code: str
    expires_at: str


class ActivateRequest(BaseModel):
    code: str
    hardware_serial: str
    name: str | None = None
    software_version: str | None = None


class OperatorResponse(BaseModel):
    id: str
    name: str
    role: str
    pin_digits_json: str
    is_active: bool
    created_at: str

    class Config:
        from_attributes = True


class ActivateResponse(BaseModel):
    api_key: str
    workstation_id: str
    customer_id: str
    customer_name: str
    operators: List[OperatorResponse]


class OperatorCreateRequest(BaseModel):
    name: str
    role: str = "operator"
    pin: str  # 6 digits


class OperatorUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    pin: str | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# PIN hashing helpers
# ---------------------------------------------------------------------------

def _hash_pin_digits(operator_id: str, pin: str) -> str:
    """Generate per-digit SHA-256 hashes for partial PIN challenge."""
    hashes = []
    for digit in pin:
        h = hashlib.sha256(f"{operator_id}:{digit}".encode()).hexdigest()
        hashes.append(h)
    return json.dumps(hashes)


def _validate_pin(pin: str) -> None:
    if not pin or len(pin) != 6 or not pin.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PIN must be exactly 6 digits",
        )


# ---------------------------------------------------------------------------
# Customer creation (kept for backward compat — admin.py has the dashboard version)
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


# ---------------------------------------------------------------------------
# Workstation registration (API key auth)
# ---------------------------------------------------------------------------

@router.post("/workstations/register", response_model=WorkstationRegisterResponse, status_code=status.HTTP_201_CREATED)
def register_workstation(
    body: WorkstationRegisterRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    existing = db.query(Workstation).filter(
        Workstation.hardware_serial == body.hardware_serial,
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


# ---------------------------------------------------------------------------
# Activation codes
# ---------------------------------------------------------------------------

@router.post("/activation-codes", response_model=ActivationCodeResponse, status_code=status.HTTP_201_CREATED)
def create_activation_code(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    """Generate a short-lived activation code for workstation provisioning."""
    chars = string.ascii_uppercase + string.digits
    code = "".join(secrets.choice(chars) for _ in range(8))

    ac = ActivationCode(
        customer_id=customer.id,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(ac)
    db.commit()
    db.refresh(ac)

    return ActivationCodeResponse(
        code=ac.code,
        expires_at=ac.expires_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Workstation activation (no auth — uses activation code)
# ---------------------------------------------------------------------------

@router.post("/activate", response_model=ActivateResponse)
def activate_workstation(
    body: ActivateRequest,
    db: Session = Depends(get_db),
):
    """Activate a workstation using a one-time activation code."""
    ac = db.query(ActivationCode).filter(ActivationCode.code == body.code).first()
    if not ac:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid activation code")

    if ac.claimed_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Activation code already used")

    if ac.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Activation code expired")

    existing = db.query(Workstation).filter(
        Workstation.hardware_serial == body.hardware_serial,
    ).first()
    if existing:
        ws = existing
    else:
        ws = Workstation(
            customer_id=ac.customer_id,
            hardware_serial=body.hardware_serial,
            name=body.name,
            software_version=body.software_version,
        )
        db.add(ws)
        db.flush()

    ac.claimed_by_workstation_id = ws.id
    ac.claimed_at = datetime.now(timezone.utc)

    customer = db.query(Customer).filter(Customer.id == ac.customer_id).first()

    raw_key = secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(f"{settings.API_KEY_PEPPER}:{raw_key}".encode()).hexdigest()
    customer.api_key_hash = key_hash

    operators = db.query(Operator).filter(
        Operator.customer_id == ac.customer_id,
        Operator.is_active == True,
    ).all()

    db.commit()

    op_responses = [
        OperatorResponse(
            id=str(op.id),
            name=op.name,
            role=op.role,
            pin_digits_json=op.pin_digits_json,
            is_active=op.is_active,
            created_at=op.created_at.isoformat(),
        )
        for op in operators
    ]

    return ActivateResponse(
        api_key=raw_key,
        workstation_id=str(ws.id),
        customer_id=str(customer.id),
        customer_name=customer.name,
        operators=op_responses,
    )


# ---------------------------------------------------------------------------
# Operator CRUD (API key or dashboard auth)
# ---------------------------------------------------------------------------

@router.get("/operators", response_model=List[OperatorResponse])
def list_operators(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    ops = db.query(Operator).filter(
        Operator.customer_id == customer.id,
    ).order_by(Operator.name).all()
    return [
        OperatorResponse(
            id=str(op.id),
            name=op.name,
            role=op.role,
            pin_digits_json=op.pin_digits_json,
            is_active=op.is_active,
            created_at=op.created_at.isoformat(),
        )
        for op in ops
    ]


@router.post("/operators", response_model=OperatorResponse, status_code=status.HTTP_201_CREATED)
def create_operator(
    body: OperatorCreateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    _validate_pin(body.pin)

    op = Operator(
        customer_id=customer.id,
        name=body.name,
        role=body.role,
        pin_hash="placeholder",
        pin_digits_json="[]",
    )
    db.add(op)
    db.flush()

    op.pin_hash = bcrypt.hash(body.pin)
    op.pin_digits_json = _hash_pin_digits(str(op.id), body.pin)
    db.commit()
    db.refresh(op)

    return OperatorResponse(
        id=str(op.id),
        name=op.name,
        role=op.role,
        pin_digits_json=op.pin_digits_json,
        is_active=op.is_active,
        created_at=op.created_at.isoformat(),
    )


@router.patch("/operators/{operator_id}", response_model=OperatorResponse)
def update_operator(
    operator_id: str,
    body: OperatorUpdateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    op = db.query(Operator).filter(
        Operator.id == operator_id,
        Operator.customer_id == customer.id,
    ).first()
    if not op:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")

    if body.name is not None:
        op.name = body.name
    if body.role is not None:
        op.role = body.role
    if body.is_active is not None:
        op.is_active = body.is_active
    if body.pin is not None:
        _validate_pin(body.pin)
        op.pin_hash = bcrypt.hash(body.pin)
        op.pin_digits_json = _hash_pin_digits(str(op.id), body.pin)

    db.commit()
    db.refresh(op)

    return OperatorResponse(
        id=str(op.id),
        name=op.name,
        role=op.role,
        pin_digits_json=op.pin_digits_json,
        is_active=op.is_active,
        created_at=op.created_at.isoformat(),
    )


@router.delete("/operators/{operator_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_operator(
    operator_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    op = db.query(Operator).filter(
        Operator.id == operator_id,
        Operator.customer_id == customer.id,
    ).first()
    if not op:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operator not found")
    op.is_active = False
    db.commit()
