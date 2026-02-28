from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.database.base import Base, UUIDType

try:
    from pgvector.sqlalchemy import Vector

    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


class WMNode(Base):
    __tablename__ = "wm_nodes"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    source_workstation_id = Column(UUIDType, nullable=True)

    type = Column(String, nullable=False)  # action, consequence, context, condition, pattern
    description = Column(Text, nullable=True)
    embedding = Column(Vector(768), nullable=True) if HAS_PGVECTOR else Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    decay_weight = Column(Float, nullable=True)
    context = Column(Text, nullable=True)  # JSON

    venue_id = Column(UUIDType, ForeignKey("venues.id"), nullable=True, index=True)
    operation_id = Column(UUIDType, ForeignKey("operations.id"), nullable=True)
    drone_id = Column(String, nullable=True)
    venue_type = Column(String, nullable=True)
    abstraction_level = Column(String, nullable=False, default="specific")  # specific, pattern, principle

    cloud_version = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    last_reinforced = Column(TIMESTAMP(timezone=True), nullable=True)
