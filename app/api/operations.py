"""Operation records routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_customer
from app.database.session import get_db
from app.models.customer import Customer
from app.models.operation import Operation

router = APIRouter(prefix="/operations", tags=["operations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class OperationResponse(BaseModel):
    id: str
    venue_id: str
    principal_id: str | None = None
    name: str | None = None
    type: str | None = None
    status: str
    environment: str | None = None
    drone_count_tier1: int | None = None
    drone_count_tier2: int | None = None
    deploy_time_s: float | None = None
    total_alerts: int | None = None
    coverage_score_avg: float | None = None
    actual_start: str | None = None
    actual_end: str | None = None
    cloud_version: int
    created_at: str

    class Config:
        from_attributes = True


class OperationCreateRequest(BaseModel):
    venue_id: str
    principal_id: str | None = None
    name: str | None = None
    type: str | None = None
    environment: str | None = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=List[OperationResponse])
def list_operations(
    venue_id: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    q = db.query(Operation).filter(Operation.customer_id == customer.id)
    if venue_id:
        q = q.filter(Operation.venue_id == venue_id)
    return q.order_by(Operation.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{operation_id}", response_model=OperationResponse)
def get_operation(
    operation_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    op = db.query(Operation).filter(
        Operation.id == operation_id,
        Operation.customer_id == customer.id,
    ).first()
    if not op:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found")
    return op


@router.post("", response_model=OperationResponse, status_code=status.HTTP_201_CREATED)
def create_operation(
    body: OperationCreateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    op = Operation(customer_id=customer.id, **body.model_dump())
    db.add(op)
    db.commit()
    db.refresh(op)
    return op
