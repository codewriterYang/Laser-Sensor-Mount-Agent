"""SQLAlchemy ORM 模型，对应 06_DATABASE.md 规范。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StepFile(Base):
    __tablename__ = "step_files"

    id = Column(String(36), primary_key=True, default=_uuid)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False, default="uploaded")  # uploaded|parsing|parsed|failed
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class ProductGraph(Base):
    __tablename__ = "product_graphs"

    id = Column(String(36), primary_key=True, default=_uuid)
    step_file_id = Column(String(36), ForeignKey("step_files.id"), nullable=False)
    graph_json = Column(Text, nullable=False)  # JSON 编码的 ProductGraph
    status = Column(String(20), nullable=False, default="draft")  # draft|generated|approved
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class DraftProcessGraph(Base):
    __tablename__ = "draft_process_graphs"

    id = Column(String(36), primary_key=True, default=_uuid)
    product_graph_id = Column(String(36), ForeignKey("product_graphs.id"), nullable=False)
    graph_json = Column(Text, nullable=False)  # JSON 编码的 DraftProcessGraph
    status = Column(String(20), nullable=False, default="draft")  # draft|reviewing|approved|rejected
    generated_by = Column(String(50), nullable=False, default="system")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"

    id = Column(String(36), primary_key=True, default=_uuid)
    process_id = Column(String(36), ForeignKey("draft_process_graphs.id"), nullable=False)
    step_id = Column(String(36), nullable=False)
    action = Column(String(20), nullable=False)  # accept|modify|delete|insert
    reason = Column(Text, nullable=False, default="")
    reviewer = Column(String(100), nullable=False, default="Engineer")
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class ApprovedProcessGraph(Base):
    __tablename__ = "approved_process_graphs"

    id = Column(String(36), primary_key=True, default=_uuid)
    draft_process_id = Column(String(36), ForeignKey("draft_process_graphs.id"), nullable=False)
    graph_json = Column(Text, nullable=False)
    approved_by = Column(String(100), nullable=False)
    approved_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)


class AssemblyInstruction(Base):
    __tablename__ = "assembly_instructions"

    id = Column(String(36), primary_key=True, default=_uuid)
    approved_process_id = Column(String(36), ForeignKey("approved_process_graphs.id"), nullable=False)
    instruction_json = Column(Text, nullable=False)
    pdf_path = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
