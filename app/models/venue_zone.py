from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.database.base import Base, UUIDType


class VenueZone(Base):
    __tablename__ = "venue_zones"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    venue_id = Column(UUIDType, ForeignKey("venues.id"), nullable=False, index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    source_workstation_id = Column(UUIDType, nullable=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=True)
    environment = Column(String, nullable=True)  # indoor, outdoor, covered, transition
    tier_requirement = Column(String, nullable=True)  # tier_1, tier_2, either
    floor_level = Column(Integer, nullable=True)
    polygon_json = Column(Text, nullable=True)
    centroid_lat = Column(Float, nullable=True)
    centroid_lon = Column(Float, nullable=True)
    ceiling_height_m = Column(Float, nullable=True)
    area_sq_m = Column(Float, nullable=True)
    coverage_priority = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    cloud_version = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    venue = relationship("Venue", back_populates="zones")
    perch_points = relationship("PerchPoint", back_populates="zone")
