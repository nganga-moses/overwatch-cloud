from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.database.base import Base, UUIDType


class WMEdge(Base):
    __tablename__ = "wm_edges"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    source_workstation_id = Column(UUIDType, nullable=True)
    from_node = Column(UUIDType, ForeignKey("wm_nodes.id"), nullable=False, index=True)
    to_node = Column(UUIDType, ForeignKey("wm_nodes.id"), nullable=False, index=True)
    relationship = Column(String, nullable=True)
    mechanism = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    observations = Column(Integer, nullable=True, default=0)
    abstraction_level = Column(String, nullable=True)
    cloud_version = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
