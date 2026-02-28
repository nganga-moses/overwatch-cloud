from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import relationship

from app.database.base import Base, UUIDType


class Drone(Base):
    __tablename__ = "drones"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    kit_id = Column(UUIDType, ForeignKey("kits.id"), nullable=False, index=True)
    serial = Column(String, unique=True, nullable=False, index=True)
    tier = Column(String, nullable=False)  # tier_1, tier_2
    callsign = Column(String, nullable=True)
    hardware_class = Column(String, nullable=True)

    # Maintenance state
    spine_array_condition = Column(String, nullable=True, default="good")
    suction_pump_condition = Column(String, nullable=True, default="good")
    landing_gear_condition = Column(String, nullable=True)  # N/A for Tier 1

    # Lifetime stats
    total_flight_hours = Column(Float, nullable=True, default=0.0)
    total_perch_hours = Column(Float, nullable=True, default=0.0)
    total_attachments = Column(Integer, nullable=True, default=0)
    attachment_success_rate = Column(Float, nullable=True)
    battery_cycles = Column(Integer, nullable=True, default=0)
    battery_health_pct = Column(Float, nullable=True)
    surface_performance = Column(JSONB, nullable=True)
    reliability_score = Column(Float, nullable=True)

    last_deployed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_maintained_at = Column(TIMESTAMP(timezone=True), nullable=True)
    source_workstation_id = Column(UUIDType, nullable=True)
    cloud_version = Column(Integer, nullable=False, default=1)
    synced_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    kit = relationship("Kit", back_populates="drones")
