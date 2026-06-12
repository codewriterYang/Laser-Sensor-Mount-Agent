"""Test fixtures shared across all test types."""

from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Temp file database — ensures all connections share the same DB
_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.name}"

# Import app — it uses the above DATABASE_URL
from src.app.database import SessionLocal, create_tables, get_db
from src.app.main import app


def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test, drop after."""
    create_tables()
    yield
    from src.app.models.orm import Base
    from src.app.database import engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
