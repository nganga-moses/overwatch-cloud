"""World model knowledge graph routes (nodes and edges)."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_customer
from app.database.session import get_db
from app.models.customer import Customer
from app.models.wm_node import WMNode
from app.models.wm_edge import WMEdge

router = APIRouter(prefix="/world-model", tags=["world-model"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class WMNodeResponse(BaseModel):
    id: str
    type: str
    description: str | None = None
    confidence: float | None = None
    venue_id: str | None = None
    operation_id: str | None = None
    venue_type: str | None = None
    abstraction_level: str
    cloud_version: int
    created_at: str

    class Config:
        from_attributes = True


class WMNodeCreateRequest(BaseModel):
    type: str
    description: str | None = None
    confidence: float | None = None
    venue_id: str | None = None
    operation_id: str | None = None
    drone_id: str | None = None
    venue_type: str | None = None
    abstraction_level: str = "specific"
    context: str | None = None


class WMEdgeResponse(BaseModel):
    id: str
    from_node: str
    to_node: str
    relationship: str | None = None
    mechanism: str | None = None
    confidence: float | None = None
    observations: int | None = None
    abstraction_level: str | None = None
    cloud_version: int
    created_at: str

    class Config:
        from_attributes = True


class WMEdgeCreateRequest(BaseModel):
    from_node: str
    to_node: str
    relationship: str | None = None
    mechanism: str | None = None
    confidence: float | None = None
    abstraction_level: str | None = None


# ---------------------------------------------------------------------------
# Node routes
# ---------------------------------------------------------------------------

@router.get("/nodes", response_model=List[WMNodeResponse])
def list_nodes(
    abstraction_level: str | None = Query(None),
    venue_id: str | None = Query(None),
    node_type: str | None = Query(None, alias="type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    q = db.query(WMNode).filter(WMNode.customer_id == customer.id)
    if abstraction_level:
        q = q.filter(WMNode.abstraction_level == abstraction_level)
    if venue_id:
        q = q.filter(WMNode.venue_id == venue_id)
    if node_type:
        q = q.filter(WMNode.type == node_type)
    return q.order_by(WMNode.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/nodes/{node_id}", response_model=WMNodeResponse)
def get_node(
    node_id: str,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    node = db.query(WMNode).filter(WMNode.id == node_id, WMNode.customer_id == customer.id).first()
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")
    return node


@router.post("/nodes", response_model=WMNodeResponse, status_code=status.HTTP_201_CREATED)
def create_node(
    body: WMNodeCreateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    node = WMNode(customer_id=customer.id, **body.model_dump())
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


# ---------------------------------------------------------------------------
# Edge routes
# ---------------------------------------------------------------------------

@router.get("/edges", response_model=List[WMEdgeResponse])
def list_edges(
    node_id: str | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    q = db.query(WMEdge).filter(WMEdge.customer_id == customer.id)
    if node_id:
        q = q.filter((WMEdge.from_node == node_id) | (WMEdge.to_node == node_id))
    return q.offset(skip).limit(limit).all()


@router.post("/edges", response_model=WMEdgeResponse, status_code=status.HTTP_201_CREATED)
def create_edge(
    body: WMEdgeCreateRequest,
    customer: Customer = Depends(get_current_customer),
    db: Session = Depends(get_db),
):
    edge = WMEdge(customer_id=customer.id, **body.model_dump())
    db.add(edge)
    db.commit()
    db.refresh(edge)
    return edge
