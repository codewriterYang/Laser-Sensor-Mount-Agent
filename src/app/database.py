"""数据库引擎与会话工厂。"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models.orm import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./laser_sensor_mount.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(bind=engine)


def create_tables() -> None:
    """创建所有表（如果尚不存在）—— MVP 阶段，暂未使用 Alembic 迁移。"""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """生成数据库会话（FastAPI 依赖注入）。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
