from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.database.base import Base, UUIDType


class SurfaceAssessment(Base):
    __tablename__ = "surface_assessments"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    perch_point_id = Column(UUIDType, ForeignKey("perch_points.id"), nullable=False, index=True)
    operation_id = Column(UUIDType, ForeignKey("operations.id"), nullable=True, index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    source_workstation_id = Column(UUIDType, nullable=True)
    drone_id = Column(String, nullable=True)
    drone_tier = Column(String, nullable=True)

    surface_class_predicted = Column(String, nullable=True)
    surface_class_actual = Column(String, nullable=True)
    surface_orientation = Column(String, nullable=True)
    tof_roughness = Column(Float, nullable=True)
    weather_conditions = Column(String, nullable=True)

    spine_engaged = Column(Integer, nullable=True)
    suction_engaged = Column(Integer, nullable=True)
    landing_gear_used = Column(Integer, nullable=True)
    hold_duration_s = Column(Float, nullable=True)
    failure_mode = Column(String, nullable=True)
    approach_image_blob_key = Column(String, nullable=True)

    cloud_version = Column(Integer, nullable=False, default=1)
    assessed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    perch_point = relationship("PerchPoint", back_populates="surface_assessments")
