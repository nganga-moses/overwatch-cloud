from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.database.base import Base, UUIDType


class ZoneConnection(Base):
    __tablename__ = "zone_connections"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    venue_id = Column(UUIDType, ForeignKey("venues.id"), nullable=False, index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    from_zone_id = Column(UUIDType, ForeignKey("venue_zones.id"), nullable=False)
    to_zone_id = Column(UUIDType, ForeignKey("venue_zones.id"), nullable=False)
    connection_type = Column(String, nullable=True)
    position_json = Column(Text, nullable=True)
    width_m = Column(Float, nullable=True)
    height_m = Column(Float, nullable=True)
    is_accessible = Column(Integer, nullable=True, default=1)
    last_verified_at = Column(TIMESTAMP(timezone=True), nullable=True)
    cloud_version = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
