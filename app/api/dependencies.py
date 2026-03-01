"""Shared FastAPI dependencies for authentication and database access."""

import hashlib

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models.customer import Customer
from app.models.dashboard_user import DashboardUser


def _hash_api_key(key: str) -> str:
    """Hash an API key with the configured pepper."""
    return hashlib.sha256(f"{settings.API_KEY_PEPPER}:{key}".encode()).hexdigest()


def get_current_customer(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Customer:
    """Validate API key and return the owning Customer."""
    key_hash = _hash_api_key(x_api_key)
    customer = db.query(Customer).filter(Customer.api_key_hash == key_hash).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return customer


def get_dashboard_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
) -> DashboardUser:
    """Validate Supabase JWT and return the DashboardUser."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid auth header")

    token = authorization[7:]
    if not settings.SUPABASE_JWT_SECRET:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="JWT secret not configured")

    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    supabase_uid = payload.get("sub")
    if not supabase_uid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing sub claim")

    user = db.query(DashboardUser).filter(
        DashboardUser.supabase_uid == supabase_uid,
        DashboardUser.is_active == True,
    ).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Dashboard user not found")

    return user
