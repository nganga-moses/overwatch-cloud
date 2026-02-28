from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import relationship

from app.database.base import Base, UUIDType


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    operation_id = Column(UUIDType, ForeignKey("operations.id"), nullable=False, index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    source_workstation_id = Column(UUIDType, nullable=True)
    drone_id = Column(String, nullable=True)
    drone_tier = Column(String, nullable=True)
    zone_id = Column(UUIDType, ForeignKey("venue_zones.id"), nullable=True)

    type = Column(String, nullable=True)
    severity = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    description = Column(Text, nullable=True)
    detection_data_json = Column(JSONB, nullable=True)
    snapshot_blob_key = Column(String, nullable=True)

    operator_validated = Column(Integer, nullable=True)  # NULL=unreviewed, 1=TP, 0=FP
    operator_notes = Column(Text, nullable=True)
    escalated = Column(Integer, nullable=True)
    forwarded_to_agents = Column(Integer, nullable=True)

    cloud_version = Column(Integer, nullable=False, default=1)
    detected_at = Column(TIMESTAMP(timezone=True), nullable=True)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    operation = relationship("Operation", back_populates="alerts")
