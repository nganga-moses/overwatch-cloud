from sqlalchemy import Column, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.database.base import Base, UUIDType


class Workstation(Base):
    __tablename__ = "workstations"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    name = Column(String, nullable=True)
    hardware_serial = Column(String, nullable=False, unique=True)
    software_version = Column(String, nullable=True)
    last_seen_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_sync_at = Column(TIMESTAMP(timezone=True), nullable=True)
    status = Column(String, nullable=False, default="online")
    registered_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    customer = relationship("Customer", back_populates="workstations")
