from sqlalchemy import Column, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.database.base import Base, UUIDType


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    venue_id = Column(UUIDType, ForeignKey("venues.id"), nullable=False, index=True)
    blob_key = Column(String, nullable=False)
    format = Column(String, nullable=False)  # dxf, pdf, image
    floor_level = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="queued")  # queued, processing, completed, failed
    zone_count = Column(Integer, nullable=True)
    connection_count = Column(Integer, nullable=True)
    perch_point_count = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
