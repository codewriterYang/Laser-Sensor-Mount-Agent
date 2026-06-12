"""ProductGraph repository — persistence for product_graphs table (06_DATABASE.md §5)."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.orm import ProductGraph
from ..models.schemas import ProductGraphSchema


class ProductGraphRepository:
    """CRUD operations for ProductGraph entities."""

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
