from sqlalchemy import Boolean, Column, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.database.base import Base, UUIDType


class Operator(Base):
    __tablename__ = "operators"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="operator")  # admin, operator, viewer
    pin_hash = Column(String, nullable=False)  # bcrypt of full 6-digit PIN
    pin_digits_json = Column(Text, nullable=False)  # JSON array of 6 per-digit SHA-256 hashes
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
