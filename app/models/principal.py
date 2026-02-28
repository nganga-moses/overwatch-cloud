from sqlalchemy import Column, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.database.base import Base, UUIDType


class Principal(Base):
    """Protected person, stored by codename only — no PII in cloud."""

    __tablename__ = "principals"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    source_workstation_id = Column(UUIDType, nullable=True)
    codename = Column(String, nullable=False)
    ble_beacon_id = Column(String, nullable=True)
    # ReID embeddings stay local, never synced to cloud
    operation_count = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    cloud_version = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    operations = relationship("Operation", back_populates="principal")
