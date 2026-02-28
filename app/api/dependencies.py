"""Shared FastAPI dependencies for authentication and database access."""

import hashlib

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db
from app.models.customer import Customer


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
