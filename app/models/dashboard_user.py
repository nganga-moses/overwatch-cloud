from sqlalchemy import Boolean, Column, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.database.base import Base, UUIDType


class DashboardUser(Base):
    __tablename__ = "dashboard_users"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=True, index=True)
    supabase_uid = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=False)
    role = Column(String, nullable=False, default="customer_admin")  # platform_admin, customer_admin
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
