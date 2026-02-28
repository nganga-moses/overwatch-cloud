from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import relationship

from app.database.base import Base, UUIDType


class Operation(Base):
    __tablename__ = "operations"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    venue_id = Column(UUIDType, ForeignKey("venues.id"), nullable=False, index=True)
    principal_id = Column(UUIDType, ForeignKey("principals.id"), nullable=True, index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    source_workstation_id = Column(UUIDType, nullable=True)

    name = Column(String, nullable=True)
    type = Column(String, nullable=True)
    status = Column(String, nullable=False, default="planning")
    environment = Column(String, nullable=True)

    assigned_kit_ids = Column(JSONB, nullable=True)
    planned_start = Column(TIMESTAMP(timezone=True), nullable=True)
    planned_end = Column(TIMESTAMP(timezone=True), nullable=True)
    actual_start = Column(TIMESTAMP(timezone=True), nullable=True)
    actual_end = Column(TIMESTAMP(timezone=True), nullable=True)

    drone_count_tier1 = Column(Integer, nullable=True)
    drone_count_tier2 = Column(Integer, nullable=True)
    deploy_time_s = Column(Float, nullable=True)
    total_repositions = Column(Integer, nullable=True)
    total_alerts = Column(Integer, nullable=True)
    alert_summary_json = Column(JSONB, nullable=True)
    coverage_score_avg = Column(Float, nullable=True)

    notes = Column(Text, nullable=True)
    briefing_json = Column(JSONB, nullable=True)
    post_op_json = Column(JSONB, nullable=True)

    cloud_version = Column(Integer, nullable=False, default=1)
    synced_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    venue = relationship("Venue", back_populates="operations")
    principal = relationship("Principal", back_populates="operations")
    alerts = relationship("Alert", back_populates="operation")
