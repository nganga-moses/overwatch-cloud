"""Platform admin routes — customer + dashboard user management via Supabase JWT."""

import hashlib
import secrets
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_dashboard_user
from app.core.config import settings
from app.database.session import get_db
from app.models.customer import Customer
from app.models.dashboard_user import DashboardUser

router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CustomerResponse(BaseModel):
    id: str
    name: str
    subscription_tier: str
    max_kits: int
    created_at: str

    class Config:
        from_attributes = True


class CustomerCreateRequest(BaseModel):
    name: str
    subscription_tier: str = "starter"
    max_kits: int = 5


class CustomerCreateResponse(BaseModel):
    customer_id: str
    name: str
    api_key: str


class DashboardUserResponse(BaseModel):
    id: str
    customer_id: str | None
    supabase_uid: str
    email: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class DashboardUserCreateRequest(BaseModel):
    supabase_uid: str
    email: str
    customer_id: str | None = None
    role: str = "customer_admin"


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def _require_platform_admin(user: DashboardUser) -> None:
    if user.role != "platform_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )


# ---------------------------------------------------------------------------
# Customer management
# ---------------------------------------------------------------------------

@router.get("/customers", response_model=List[CustomerResponse])
def list_customers(
    user: DashboardUser = Depends(get_dashboard_user),
    db: Session = Depends(get_db),
):
    _require_platform_admin(user)
    customers = db.query(Customer).order_by(Customer.created_at.desc()).all()
    return [
        CustomerResponse(
            id=str(c.id),
            name=c.name,
            subscription_tier=c.subscription_tier,
            max_kits=c.max_kits,
            created_at=c.created_at.isoformat(),
        )
        for c in customers
    ]


@router.post("/customers", response_model=CustomerCreateResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    body: CustomerCreateRequest,
    user: DashboardUser = Depends(get_dashboard_user),
    db: Session = Depends(get_db),
):
    _require_platform_admin(user)

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
# Dashboard user management
# ---------------------------------------------------------------------------

@router.get("/dashboard-users", response_model=List[DashboardUserResponse])
def list_dashboard_users(
    user: DashboardUser = Depends(get_dashboard_user),
    db: Session = Depends(get_db),
):
    _require_platform_admin(user)
    users = db.query(DashboardUser).order_by(DashboardUser.created_at.desc()).all()
    return [
        DashboardUserResponse(
            id=str(u.id),
            customer_id=str(u.customer_id) if u.customer_id else None,
            supabase_uid=u.supabase_uid,
            email=u.email,
            role=u.role,
            is_active=u.is_active,
        )
        for u in users
    ]


@router.post("/dashboard-users", response_model=DashboardUserResponse, status_code=status.HTTP_201_CREATED)
def create_dashboard_user(
    body: DashboardUserCreateRequest,
    user: DashboardUser = Depends(get_dashboard_user),
    db: Session = Depends(get_db),
):
    _require_platform_admin(user)

    existing = db.query(DashboardUser).filter(
        DashboardUser.supabase_uid == body.supabase_uid,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")

    du = DashboardUser(
        supabase_uid=body.supabase_uid,
        email=body.email,
        customer_id=body.customer_id,
        role=body.role,
    )
    db.add(du)
    db.commit()
    db.refresh(du)

    return DashboardUserResponse(
        id=str(du.id),
        customer_id=str(du.customer_id) if du.customer_id else None,
        supabase_uid=du.supabase_uid,
        email=du.email,
        role=du.role,
        is_active=du.is_active,
    )
