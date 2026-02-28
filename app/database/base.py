import uuid
from typing import Any, Optional

from sqlalchemy import Dialect, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql.type_api import TypeEngine
from sqlalchemy.types import TypeDecorator

Base = declarative_base()


class UUIDType(TypeDecorator):
    """UUID column that falls back to String(36) on non-PostgreSQL dialects."""

    impl = UUID
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value: Optional[Any], dialect: Dialect) -> Any:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(uuid.UUID(value))

    def process_result_value(self, value: Optional[Any], dialect: Dialect) -> Optional[uuid.UUID]:
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)
