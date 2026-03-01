"""Shared FastAPI dependencies for authentication and database access."""

import hashlib

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.orm import Session
from supabase import create_client, Client

from app.core.config import settings
from app.database.session import get_db
from app.models.customer import Customer
from app.models.dashboard_user import DashboardUser

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _hash_api_key(key: str) -> str:
    """Hash an API key with the configured pepper."""
    return hashlib.sha256(f"{settings.API_KEY_PEPPER}:{key}".encode()).hexdigest()


def get_current_customer(
    x_api_key: str | None = Depends(api_key_header),
    db: Session = Depends(get_db),
) -> Customer:
    """Validate API key and return the owning Customer."""
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )
    key_hash = _hash_api_key(x_api_key)
    customer = db.query(Customer).filter(Customer.api_key_hash == key_hash).first()
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return customer


def get_dashboard_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> DashboardUser:
    """
    Verify Supabase JWT token and return the DashboardUser.
    Creates the DashboardUser record on first login (auto-provision).
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    token = credentials.credentials

    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase not configured",
        )

    supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

    try:
        user_response = supabase.auth.get_user(token)

        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )

        supabase_user = user_response.user

        dashboard_user = db.query(DashboardUser).filter(
            DashboardUser.supabase_uid == supabase_user.id,
        ).first()

        if not dashboard_user:
            dashboard_user = DashboardUser(
                supabase_uid=supabase_user.id,
                email=supabase_user.email or "",
                role="customer_admin",
            )
            db.add(dashboard_user)
            db.commit()
            db.refresh(dashboard_user)
        else:
            if supabase_user.email and supabase_user.email != dashboard_user.email:
                dashboard_user.email = supabase_user.email
                db.commit()
                db.refresh(dashboard_user)

        if not dashboard_user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account deactivated",
            )

        return dashboard_user

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
        )
