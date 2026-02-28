from sqlalchemy import Column, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import TIMESTAMP

from app.database.base import Base, UUIDType


class WeatherObservation(Base):
    __tablename__ = "weather_observations"

    id = Column(UUIDType, primary_key=True, default=func.gen_random_uuid(), index=True)
    operation_id = Column(UUIDType, ForeignKey("operations.id"), nullable=True, index=True)
    customer_id = Column(UUIDType, ForeignKey("customers.id"), nullable=False, index=True)
    source_workstation_id = Column(UUIDType, nullable=True)
    source = Column(String, nullable=True)  # api, drone_telemetry, manual
    wind_speed_m_s = Column(Float, nullable=True)
    wind_heading_deg = Column(Float, nullable=True)
    gust_speed_m_s = Column(Float, nullable=True)
    temperature_c = Column(Float, nullable=True)
    precipitation = Column(String, nullable=True)
    visibility_m = Column(Float, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    observed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
