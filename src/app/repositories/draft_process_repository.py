"""DraftProcessGraph repository — 06_DATABASE.md §6."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from ..models.orm import DraftProcessGraph


class DraftProcessRepository:
    """CRUD for draft_process_graphs table."""

    def __init__(self, db: Session):
        self.db = db

    def save(self, dpg: DraftProcessGraph) -> DraftProcessGraph:
        self.db.add(dpg)
        self.db.flush()
        return dpg

    def get_by_id(self, process_id: UUID) -> DraftProcessGraph | None:
        return self.db.query(DraftProcessGraph).filter(DraftProcessGraph.id == str(process_id)).first()

    def get_by_product_graph(self, product_graph_id: UUID) -> DraftProcessGraph | None:
        return self.db.query(DraftProcessGraph).filter(DraftProcessGraph.product_graph_id == str(product_graph_id)).first()

    def update_status(self, process_id: UUID, status: str) -> DraftProcessGraph | None:
        dpg = self.get_by_id(process_id)
        if dpg:
            dpg.status = status
            self.db.flush()
        return dpg

    def update_graph_json(self, process_id: UUID, graph_json: str, status: str) -> DraftProcessGraph | None:
        dpg = self.get_by_id(process_id)
        if dpg:
            dpg.graph_json = graph_json
            dpg.status = status
            self.db.flush()
        return dpg
