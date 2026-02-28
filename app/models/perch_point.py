from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.database.base import Base, UUIDType


class PerchPoint(Base):
    __tablename__ = "perch_points"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    venue_id = Column(UUIDType, ForeignKey("venues.id"), nullable=False, index=True)
    zone_id = Column(UUIDType, ForeignKey("venue_zones.id"), nullable=True, index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    source_workstation_id = Column(UUIDType, nullable=True)

    position_json = Column(Text, nullable=True)
    wall_normal_json = Column(Text, nullable=True)
    height_m = Column(Float, nullable=True)
    surface_class = Column(String, nullable=True)
    surface_orientation = Column(String, nullable=True)  # vertical, horizontal, tubular
    attachment_method = Column(String, nullable=True)
    tier_required = Column(String, nullable=True)  # tier_1, tier_2, either

    spine_confidence = Column(Float, nullable=True)
    spine_wet_confidence = Column(Float, nullable=True)
    suction_confidence = Column(Float, nullable=True)
    landing_gear_viable = Column(Integer, nullable=True)
    landing_surface_width_mm = Column(Float, nullable=True)

    coverage_value = Column(Float, nullable=True)
    mesh_quality = Column(Float, nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    avg_hold_duration_s = Column(Float, nullable=True)
    status = Column(String, nullable=True, default="untested")

    last_used_at = Column(TIMESTAMP(timezone=True), nullable=True)
    cloud_version = Column(Integer, nullable=False, default=1)
    synced_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    venue = relationship("Venue", back_populates="perch_points")
    zone = relationship("VenueZone", back_populates="perch_points")
    surface_assessments = relationship("SurfaceAssessment", back_populates="perch_point")
