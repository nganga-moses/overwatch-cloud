from sqlalchemy import Column, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.database.base import Base, UUIDType


class ProtectionAgent(Base):
    """Member of the protection detail. ReID embeddings stay local."""

    __tablename__ = "protection_agents"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    source_workstation_id = Column(UUIDType, nullable=True)
    callsign = Column(String, nullable=False)
    notes = Column(Text, nullable=True)
    cloud_version = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
