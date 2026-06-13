"""ProductGraph 仓库 — product_graphs 表的持久化层 (06_DATABASE.md §5)。"""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.orm import ProductGraph
from ..models.schemas import ProductGraphSchema


class ProductGraphRepository:
    """ProductGraph 实体的 CRUD 操作。"""

    def __init__(self, db: Session):
        self.db = db

    def save(self, pg: ProductGraph) -> ProductGraph:
        self.db.add(pg)
        self.db.flush()
        return pg

    def get_by_id(self, product_graph_id: UUID) -> ProductGraph | None:
        return self.db.query(ProductGraph).filter(ProductGraph.id == str(product_graph_id)).first()

    def get_by_step_file(self, step_file_id: UUID) -> ProductGraph | None:
        return self.db.query(ProductGraph).filter(ProductGraph.step_file_id == str(step_file_id)).first()

    def update_status(self, product_graph_id: UUID, status: str) -> ProductGraph | None:
        pg = self.get_by_id(product_graph_id)
        if pg:
            pg.status = status
            self.db.flush()
        return pg

    def update_graph_json(self, product_graph_id: UUID, graph_json: str, status: str | None = None) -> ProductGraph | None:
        """更新 ProductGraph 的 JSON 数据和状态。"""
        pg = self.get_by_id(product_graph_id)
        if pg:
            pg.graph_json = graph_json
            if status:
                pg.status = status
            self.db.flush()
        return pg
