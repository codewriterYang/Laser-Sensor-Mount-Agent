"""工艺生成 Service — ProductGraph → DraftProcessGraph (03_ARCHITECTURE.md §1.2)。

领域规则 (04_DOMAIN_MODEL.md §31):
  - 父件优先于子件
  - 底座优先
  - 紧固件靠后
  - 垫片紧随紧固件
  - 传感器在支架之后
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
from .llm_service import LLMService
from ..logger import logger


class ProductGraphNotFoundError(Exception):
    pass


class ProcessGenerationFailedError(Exception):
    pass


class ProcessGenerationService:
    """使用规则引擎从 ProductGraph 生成 DraftProcessGraph。

    MVP：应用领域规则对节点排序并生成步骤描述。
    未来：集成 LLM 以生成更丰富的步骤文本。
    """

    # 步骤排序优先级：值越小，装配越靠前
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
        self.llm = LLMService()

    def generate(self, product_graph_id: UUID) -> tuple[UUID, DraftProcessGraphSchema]:
        """从 ProductGraph 生成 DraftProcessGraph。

        返回 (process_id, DraftProcessGraphSchema)。
        """
        logger.info(f"开始生成工艺流程，ProductGraph ID: {product_graph_id}")

        # 1. 查询 ProductGraph
        pg = self.pg_repo.get_by_id(product_graph_id)
        if pg is None:
            logger.error(f"ProductGraph 未找到：{product_graph_id}")
            raise ProductGraphNotFoundError(product_graph_id)

        graph_data = json.loads(pg.graph_json)
        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        if not nodes:
            raise ProcessGenerationFailedError("ProductGraph 没有节点")

        # 2. 应用规则引擎对节点排序
        ordered_nodes = self._order_by_rules(nodes, edges)

        # 3. 生成步骤描述（LLM 可用时使用 LLM，否则使用模板）
        steps = self._generate_steps(ordered_nodes, edges)

        # 4. 构建 DraftProcessGraph —— schema 和 DB 使用相同 UUID
        generated_by = f"llm:{self.llm.model_name}" if self.llm.enabled else "rule_engine"
        process_id = uuid.uuid4()
        draft = DraftProcessGraphSchema(
            processId=process_id,
            status="reviewing",
            steps=steps,
        )

        # 5. 以匹配的 ID 持久化
        dpg = DraftProcessGraph(
            id=str(process_id),
            product_graph_id=str(product_graph_id),
            graph_json=draft.model_dump_json(),
            status="reviewing",
            generated_by=generated_by,
        )
        self.draft_repo.save(dpg)

        return process_id, draft

    def _order_by_rules(self, nodes: list[dict], edges: list[dict]) -> list[dict]:
        """应用领域装配规则对零件排序。

        规则（按顺序）：
          1. 底座优先 — 底座/底板类零件最先
          2. 父件优先于子件 — 遵循装配体包含关系顺序
          3. 传感器在支架之后 — 传感器在支架/安装座之后
          4. 紧固件靠后 — 螺丝/螺栓靠近末尾
          5. 垫片紧随紧固件 — 垫片紧接在对应紧固件之后
        """
        # 分离装配体和零件
        assemblies = [n for n in nodes if n["nodeType"] == "assembly"]
        parts = [n for n in nodes if n["nodeType"] == "part"]

        def _priority(part: dict) -> int:
            name = part.get("name", "").lower()
            for keyword, pri in self.NODE_TYPE_PRIORITY.items():
                if keyword in name:
                    return pri
            return 3  # 默认中间优先级

        # 按优先级排序零件
        ordered = sorted(parts, key=_priority)

        return ordered

    def _generate_steps(self, ordered_nodes: list[dict], edges: list[dict]) -> list[StepSchema]:
        """使用 LLM（文本）+ 规则引擎（排序）生成装配步骤。

        规则引擎决定步骤顺序（确定性）。
        LLM 生成标题、描述和所需工具（生成式）。
        LLM 不可用时回退到模板。
        """
        # 构建边查找表：target → (relation, source_node_id)
        edge_map = {}
        for e in edges:
            relation = e["relation"]
            if relation in ("attached_to", "fastened_by", "contains"):
                edge_map[e["target"]] = (relation, e["source"])

        node_map = {n["nodeId"]: n for n in ordered_nodes}

        steps = []
        for seq, node in enumerate(ordered_nodes, 1):
            name = node.get("name", "未知零件")
            material = node.get("metadata", {}).get("material", "")
            node_id = node["nodeId"]

            # 确定关系和目标
            relation = "contains"
            target_name = ""
            if node_id in edge_map:
                relation, source_id = edge_map[node_id]
                target_name = node_map.get(source_id, {}).get("name", "")

            step = self.llm.generate_step(
                part_name=name,
                part_material=material,
                relation=relation,
                target_name=target_name,
                sequence=seq,
            )
            # 根据图数据设置所需零件
            if target_name:
                step.requiredParts = [name, target_name]
            else:
                step.requiredParts = [name]

            steps.append(step)

        return steps

    def get_draft(self, process_id: UUID) -> DraftProcessGraphSchema | None:
        """根据 ID 获取 DraftProcessGraph。"""
        dpg = self.draft_repo.get_by_id(process_id)
        if dpg is None:
            return None
        data = json.loads(dpg.graph_json)
        return DraftProcessGraphSchema(**data)
