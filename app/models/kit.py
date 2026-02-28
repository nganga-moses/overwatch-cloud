from sqlalchemy import Column, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import relationship

from app.database.base import Base, UUIDType


class Kit(Base):
    __tablename__ = "kits"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    serial = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    config = Column(String, nullable=False)  # alpha, bravo, charlie
    tier_composition = Column(JSONB, nullable=True)  # {"tier_1": 6, "tier_2": 4}
    status = Column(String, nullable=False, default="available")
    charger_serial = Column(String, nullable=True)
    case_model = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    cloud_registered_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    customer = relationship("Customer", back_populates="kits")
    drones = relationship("Drone", back_populates="kit")
