from sqlalchemy import Column, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.database.base import Base, UUIDType


class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    name = Column(String, nullable=False)
    api_key_hash = Column(String, nullable=False)
    subscription_tier = Column(String, nullable=False, default="starter")
    max_kits = Column(Integer, nullable=False, default=5)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    workstations = relationship("Workstation", back_populates="customer")
    kits = relationship("Kit", back_populates="customer")
