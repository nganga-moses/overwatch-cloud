import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database.base import Base, UUIDType
from app.models import *  # noqa: F401, F403

config = context.config


def render_item(type_, obj, autogen_context):
    """Ensure UUIDType renders as UUIDType() instead of the full module path."""
    if type_ == "type" and isinstance(obj, UUIDType):
        autogen_context.imports.add("from app.database.base import UUIDType")
        return "UUIDType()"
    return False

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
    if not url:
        raise ValueError("DATABASE_URL environment variable is not set.")

    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    elif url.startswith("postgresql://") and "psycopg2" not in url and "asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+psycopg2://")

    return url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_item=render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
