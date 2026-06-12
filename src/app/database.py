"""Database engine and session factory."""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models.orm import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./laser_sensor_mount.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(bind=engine)


def create_tables() -> None:
    """Create all tables if they don't exist (MVP — no Alembic migration yet)."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Yields a database session (FastAPI dependency)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
