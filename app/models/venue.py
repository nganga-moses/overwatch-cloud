from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.database.base import Base, UUIDType


class Venue(Base):
    __tablename__ = "venues"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    source_workstation_id = Column(UUIDType, nullable=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=True)
    environment = Column(String, nullable=True)  # indoor, outdoor, mixed
    address = Column(Text, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    floor_plan_source = Column(String, nullable=True)
    floor_plan_blob_key = Column(String, nullable=True)
    venue_model_blob_key = Column(String, nullable=True)
    deployment_count = Column(Integer, nullable=False, default=0)
    avg_deploy_time_s = Column(Float, nullable=True)
    last_operated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)  # JSON array
    cloud_version = Column(Integer, nullable=False, default=1)
    synced_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    zones = relationship("VenueZone", back_populates="venue", cascade="all, delete-orphan")
    operations = relationship("Operation", back_populates="venue")
    perch_points = relationship("PerchPoint", back_populates="venue")
