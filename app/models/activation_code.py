from sqlalchemy import Column, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.database.base import Base, UUIDType


class ActivationCode(Base):
    __tablename__ = "activation_codes"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    code = Column(String(8), nullable=False, unique=True, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    claimed_by_workstation_id = Column(UUIDType, ForeignKey("workstations.id"), nullable=True)
    claimed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
