from sqlalchemy import Column, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

from app.database.base import Base, UUIDType


class SyncEvent(Base):
    __tablename__ = "sync_events"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    workstation_id = Column(UUIDType, ForeignKey("workstations.id"), nullable=False, index=True)
    direction = Column(String, nullable=False)  # push, pull, bootstrap
    entity_counts = Column(JSONB, nullable=True)
    status = Column(String, nullable=False, default="completed")
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    cloud_version_before = Column(Integer, nullable=True)
    cloud_version_after = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
