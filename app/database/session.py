from app.database.engine import SessionLocal
from app.database.base import Base


def get_db():
    """Provides a synchronous database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables (for quick dev bootstrap, prefer Alembic in prod)."""
    from app.database.engine import engine

    Base.metadata.create_all(bind=engine)
