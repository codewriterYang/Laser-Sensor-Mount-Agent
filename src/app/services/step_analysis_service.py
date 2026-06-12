"""STEP Analysis Service — parses STEP files → ProductGraph (03_ARCHITECTURE.md §1.2)."""

from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from ..models.orm import ProductGraph, StepFile
from ..models.schemas import EdgeSchema, NodeSchema, ProductGraphSchema
from ..repositories.product_graph_repository import ProductGraphRepository
from ..repositories.step_file_repository import StepFileRepository


class StepFileNotFoundError(Exception):
    pass


class StepFileInvalidError(Exception):
    pass


class StepParseFailedError(Exception):
    pass


# --- Demo ProductGraph (MVP mock — replaces real STEP parser) ---

DEMO_PRODUCT_GRAPH = ProductGraphSchema(
    graphId=UUID("11111111-1111-1111-1111-111111111111"),
    nodes=[
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000001"), nodeType="assembly", name="Laser Sensor Mount Assembly"),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000002"), nodeType="part", name="Base Plate", metadata={"material": "Aluminum 6061", "partNumber": "LSM-BASE-001"}),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000003"), nodeType="part", name="Bracket", metadata={"material": "Steel", "partNumber": "LSM-BRK-001"}),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000004"), nodeType="part", name="Laser Sensor", metadata={"partNumber": "LS-2000"}),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000005"), nodeType="part", name="Screw M4x12", metadata={"material": "Stainless Steel"}),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000006"), nodeType="part", name="Washer M4", metadata={"material": "Stainless Steel"}),
    ],
    edges=[
        EdgeSchema(edgeId=UUID("e1000000-0000-0000-0000-000000000001"), source=UUID("a1000000-0000-0000-0000-000000000001"), target=UUID("a1000000-0000-0000-0000-000000000002"), relation="contains"),
        EdgeSchema(edgeId=UUID("e1000000-0000-0000-0000-000000000002"), source=UUID("a1000000-0000-0000-0000-000000000001"), target=UUID("a1000000-0000-0000-0000-000000000003"), relation="contains"),
        EdgeSchema(edgeId=UUID("e1000000-0000-0000-0000-000000000003"), source=UUID("a1000000-0000-0000-0000-000000000001"), target=UUID("a1000000-0000-0000-0000-000000000004"), relation="contains"),
        EdgeSchema(edgeId=UUID("e1000000-0000-0000-0000-000000000004"), source=UUID("a1000000-0000-0000-0000-000000000001"), target=UUID("a1000000-0000-0000-0000-000000000005"), relation="contains"),
        EdgeSchema(edgeId=UUID("e1000000-0000-0000-0000-000000000005"), source=UUID("a1000000-0000-0000-0000-000000000001"), target=UUID("a1000000-0000-0000-0000-000000000006"), relation="contains"),
        EdgeSchema(edgeId=UUID("e1000000-0000-0000-0000-000000000006"), source=UUID("a1000000-0000-0000-0000-000000000003"), target=UUID("a1000000-0000-0000-0000-000000000004"), relation="attached_to"),
        EdgeSchema(edgeId=UUID("e1000000-0000-0000-0000-000000000007"), source=UUID("a1000000-0000-0000-0000-000000000003"), target=UUID("a1000000-0000-0000-0000-000000000005"), relation="fastened_by"),
        EdgeSchema(edgeId=UUID("e1000000-0000-0000-0000-000000000008"), source=UUID("a1000000-0000-0000-0000-000000000005"), target=UUID("a1000000-0000-0000-0000-000000000006"), relation="contains"),
    ],
)

# Directory where uploaded STEP files are persisted
UPLOAD_DIR = Path("uploads")


class StepAnalysisService:
    """Service: STEP file → ProductGraph.

    MVP: Uses a demo ProductGraph for any valid .step file.
    Future: Real STEP parser.
    """

    VALID_EXTENSION = ".step"

    def __init__(self, db: Session):
        self.db = db
        self.step_repo = StepFileRepository(db)
        self.pg_repo = ProductGraphRepository(db)

    def analyze(self, file: UploadFile) -> tuple[UUID, UUID, str]:
        """Analyze an uploaded STEP file and return (step_file_id, product_graph_id, status).

        Raises:
            StepFileInvalidError: Invalid file extension or empty file.
            StepParseFailedError: Parsing failed.
        """
        file_name = file.filename or "unnamed"

        # Validate file extension
        if not file_name.lower().endswith(self.VALID_EXTENSION):
            raise StepFileInvalidError(file_name)

        # Read file content and persist to disk
        UPLOAD_DIR.mkdir(exist_ok=True)
        file_path = UPLOAD_DIR / file_name
        content = file.file.read()
        file_size = len(content)
        file_path.write_bytes(content)

        # Create StepFile record
        sf = StepFile(
            file_name=file_name,
            file_path=str(file_path),
            file_size=file_size,
            status="uploaded",
        )
        self.step_repo.save(sf)
        step_file_id = UUID(sf.id)

        # Update: uploaded → parsing
        self.step_repo.update_status(step_file_id, "parsing")

        try:
            # Generate demo ProductGraph
            demo_pg = DEMO_PRODUCT_GRAPH.model_copy(deep=True)
            new_graph_id = uuid.uuid4()
            demo_pg.graphId = new_graph_id

            pg = ProductGraph(
                step_file_id=str(step_file_id),
                graph_json=demo_pg.model_dump_json(),
                status="draft",
            )
            self.pg_repo.save(pg)
            product_graph_id = UUID(pg.id)

            # Update: parsing → parsed
            self.step_repo.update_status(step_file_id, "parsed")
            # Update ProductGraph: draft → generated
            self.pg_repo.update_status(product_graph_id, "generated")

            return step_file_id, product_graph_id, "parsed"

        except Exception:
            self.step_repo.update_status(step_file_id, "failed")
            raise StepParseFailedError(f"Failed to parse: {file_name}")
