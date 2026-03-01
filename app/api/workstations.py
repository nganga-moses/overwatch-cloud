"""Workstation management and heartbeat routes."""

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_customer
from app.database.session import get_db
from app.models.customer import Customer
from app.models.workstation import Workstation

router = APIRouter(prefix="/workstations", tags=["workstations"])


class WorkstationResponse(BaseModel):
    id: str
    name: str | None
    hardware_serial: str
    software_version: str | None
    status: str
    last_seen_at: str | None
    last_sync_at: str | None
    registered_at: str

    class Config:
        from_attributes = True


class HeartbeatRequest(BaseModel):
    status: str = "online"
    software_version: str | None = None
    world_model_nodes: int | None = None
    world_model_edges: int | None = None


@router.get("", response_model=List[WorkstationResponse])
def list_workstations(
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    wss = db.query(Workstation).filter(
        Workstation.customer_id == customer.id,
    ).order_by(Workstation.registered_at.desc()).all()
    return [
        WorkstationResponse(
            id=str(ws.id),
            name=ws.name,
            hardware_serial=ws.hardware_serial,
            software_version=ws.software_version,
            status=ws.status,
            last_seen_at=ws.last_seen_at.isoformat() if ws.last_seen_at else None,
            last_sync_at=ws.last_sync_at.isoformat() if ws.last_sync_at else None,
            registered_at=ws.registered_at.isoformat(),
        )
        for ws in wss
    ]


@router.patch("/{workstation_id}/heartbeat")
def heartbeat(
    workstation_id: str,
    body: HeartbeatRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    ws = db.query(Workstation).filter(
        Workstation.id == workstation_id,
        Workstation.customer_id == customer.id,
    ).first()
    if not ws:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workstation not found")

    ws.last_seen_at = datetime.now(timezone.utc)
    ws.status = body.status
    if body.software_version:
        ws.software_version = body.software_version

    db.commit()
    return {"status": "ok"}
