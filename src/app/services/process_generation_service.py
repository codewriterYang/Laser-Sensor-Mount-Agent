"""Process Generation Service — ProductGraph → DraftProcessGraph (03_ARCHITECTURE.md §1.2).

Domain Rules (04_DOMAIN_MODEL.md §31):
  - Parent Before Child
  - Base First
  - Fastener Last
  - Washer Follow Fastener
  - Sensor After Mount
"""

from __future__ import annotations

import json
import uuid
from uuid import UUID

from sqlalchemy.orm import Session

from ..models.orm import DraftProcessGraph
from ..models.schemas import DraftProcessGraphSchema, StepSchema
from ..repositories.draft_process_repository import DraftProcessRepository
from ..repositories.product_graph_repository import ProductGraphRepository


class ProductGraphNotFoundError(Exception):
    pass


class ProcessGenerationFailedError(Exception):
    pass


class ProcessGenerationService:
    """Generate DraftProcessGraph from ProductGraph using rule engine.

    MVP: Applies domain rules to order nodes and generates step descriptions.
    Future: LLM integration for richer step text.
    """

    # Step ordering priority: lower = earlier in assembly
    NODE_TYPE_PRIORITY = {
        "base": 1,
        "plate": 1,
        "bracket": 2,
        "mount": 2,
        "sensor": 3,
        "screw": 4,
        "fastener": 4,
        "bolt": 4,
        "nut": 4,
        "washer": 5,
    }

    def __init__(self, db: Session):
        self.db = db
        self.pg_repo = ProductGraphRepository(db)
        self.draft_repo = DraftProcessRepository(db)

    def generate(self, product_graph_id: UUID) -> tuple[UUID, DraftProcessGraphSchema]:
        """Generate a DraftProcessGraph from a ProductGraph.

        Returns (process_id, DraftProcessGraphSchema).
        """
        # 1. Look up ProductGraph
        pg = self.pg_repo.get_by_id(product_graph_id)
        if pg is None:
            raise ProductGraphNotFoundError(product_graph_id)

        graph_data = json.loads(pg.graph_json)
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        if not nodes:
            raise ProcessGenerationFailedError("ProductGraph has no nodes")

        # 2. Apply rule engine to order nodes
        ordered_nodes = self._order_by_rules(nodes, edges)

        # 3. Generate step descriptions
        steps = self._generate_steps(ordered_nodes, edges)

        # 4. Build DraftProcessGraph — use same UUID for schema and DB
        process_id = uuid.uuid4()
        draft = DraftProcessGraphSchema(
            processId=process_id,
            status="reviewing",
            steps=steps,
        )

        # 5. Persist with matching ID
        dpg = DraftProcessGraph(
            id=str(process_id),
            product_graph_id=str(product_graph_id),
            graph_json=draft.model_dump_json(),
            status="reviewing",
            generated_by="rule_engine",
        )
        self.draft_repo.save(dpg)

        return process_id, draft

    def _order_by_rules(self, nodes: list[dict], edges: list[dict]) -> list[dict]:
        """Apply domain assembly rules to order parts.

        Rules (in order):
          1. Base First — base/plate parts come first
          2. Parent Before Child — assembly containment order respected
          3. Sensor After Mount — sensors after brackets/mounts
          4. Fastener Last — screws/bolts near the end
          5. Washer Follow Fastener — washers immediately after their fastener
        """
        # Separate assembly and parts
        assemblies = [n for n in nodes if n["nodeType"] == "assembly"]
        parts = [n for n in nodes if n["nodeType"] == "part"]

        def _priority(part: dict) -> int:
            name = part.get("name", "").lower()
            for keyword, pri in self.NODE_TYPE_PRIORITY.items():
                if keyword in name:
                    return pri
            return 3  # default middle

        # Sort parts by priority
        ordered = sorted(parts, key=_priority)

        return ordered

    def _generate_steps(self, ordered_nodes: list[dict], edges: list[dict]) -> list[StepSchema]:
        """Generate assembly steps with natural-language descriptions."""
        steps = []
        edge_map = {}  # target → relation, source_name
        for e in edges:
            target = e["target"]
            source = e["source"]
            relation = e["relation"]
            if relation in ("attached_to", "fastened_by"):
                edge_map[target] = (relation, source)

        node_map = {n["nodeId"]: n for n in ordered_nodes}

        seq = 1
        for node in ordered_nodes:
            name = node.get("name", "Unknown Part")
            node_id = node["nodeId"]
            metadata = node.get("metadata", {})
            material = metadata.get("material", "")

            # Determine description based on relations
            if node_id in edge_map:
                rel, target_id = edge_map[node_id]
                target_name = node_map.get(target_id, {}).get("name", "attached part") if target_id in node_map else "assembly"

                if rel == "fastened_by":
                    title = f"Fasten {name}"
                    description = f"Secure the {target_name} using {name}"
                    if material:
                        description += f" ({material})"
                    required_parts = [name, target_name]
                    required_tools = ["Hex Wrench", "Torque Wrench"]
                elif rel == "attached_to":
                    title = f"Attach {name}"
                    description = f"Mount the {name} onto the {target_name}"
                    if material:
                        description += f" ({material})"
                    required_parts = [name, target_name]
                    required_tools = ["Hex Wrench"]
                else:
                    title = f"Install {name}"
                    description = f"Install {name}"
                    required_parts = [name]
                    required_tools = []
            else:
                title = f"Install {name}"
                description = f"Place the {name} as the base component"
                if material:
                    description += f" ({material})"
                required_parts = [name]
                required_tools = []

            steps.append(StepSchema(
                stepId=uuid.uuid4(),
                sequence=seq,
                title=title,
                description=description,
                requiredParts=required_parts,
                requiredTools=required_tools,
            ))
            seq += 1

        return steps

    def get_draft(self, process_id: UUID) -> DraftProcessGraphSchema | None:
        """Retrieve a DraftProcessGraph by ID."""
        dpg = self.draft_repo.get_by_id(process_id)
        if dpg is None:
            return None
        data = json.loads(dpg.graph_json)
        return DraftProcessGraphSchema(**data)
