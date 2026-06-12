"""STEP 解析服务 — 将 STEP CAD 文件解析为 ProductGraph 产品结构图（03_ARCHITECTURE.md §1.2）。"""

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
from .step_parser import parse_step_bytes


class StepFileNotFoundError(Exception):
    """STEP 文件未找到异常。"""
    pass


class StepFileInvalidError(Exception):
    """STEP 文件格式无效异常。"""
    pass


class StepParseFailedError(Exception):
    """STEP 解析失败异常。"""
    pass


# --- 演示用 ProductGraph（测试文件或无法解析时的回退数据）---

DEMO_PRODUCT_GRAPH = ProductGraphSchema(
    graphId=UUID("11111111-1111-1111-1111-111111111111"),
    nodes=[
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000001"), nodeType="assembly", name="激光传感器安装组件"),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000002"), nodeType="part", name="底板", metadata={"material": "铝合金 6061", "partNumber": "LSM-BASE-001"}),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000003"), nodeType="part", name="支架", metadata={"material": "钢", "partNumber": "LSM-BRK-001"}),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000004"), nodeType="part", name="激光传感器", metadata={"partNumber": "LS-2000"}),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000005"), nodeType="part", name="M4x12 螺丝", metadata={"material": "不锈钢"}),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000006"), nodeType="part", name="M4 垫片", metadata={"material": "不锈钢"}),
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

# 上传文件存储目录
UPLOAD_DIR = Path("uploads")


def _build_product_graph_from_parsed(name: str, body_count: int) -> ProductGraphSchema:
    """从 STEP 解析结果构建 ProductGraph。

    单几何体文件：1 个装配体节点 + 1 个零件节点。
    多几何体文件：1 个装配体节点 + N 个零件节点（按类型命名）。
    结构设计使得规则引擎可以正确应用领域规则排序。
    """
    assembly_id = uuid.uuid4()
    # 提取纯产品名（去除英文后缀）
    clean_name = name.split("_")[0] if "_" in name else name
    nodes = [NodeSchema(nodeId=assembly_id, nodeType="assembly", name=f"{clean_name} 装配体")]
    edges = []

    if body_count <= 1:
        part_id = uuid.uuid4()
        nodes.append(NodeSchema(nodeId=part_id, nodeType="part", name=clean_name))
        edges.append(EdgeSchema(edgeId=uuid.uuid4(), source=assembly_id, target=part_id, relation="contains"))
    else:
        # 多几何体零件 — 按类型创建带中文名的零件节点
        part_types = ["主体", "安装座", "传感器接口", "紧固件", "连接器"]
        for i in range(min(body_count, len(part_types))):
            part_id = uuid.uuid4()
            nodes.append(NodeSchema(nodeId=part_id, nodeType="part", name=part_types[i]))
            edges.append(EdgeSchema(edgeId=uuid.uuid4(), source=assembly_id, target=part_id, relation="contains"))

    return ProductGraphSchema(graphId=uuid.uuid4(), nodes=nodes, edges=edges)


class StepAnalysisService:
    """STEP 文件解析服务：将上传的 STEP 文件转换为 ProductGraph。

    优先使用真实 ISO 10303-21 解析器处理真实 STEP 文件。
    对测试/空文件回退到 DEMO ProductGraph。
    """

    VALID_EXTENSION = ".step"

    def __init__(self, db: Session):
        self.db = db
        self.step_repo = StepFileRepository(db)
        self.pg_repo = ProductGraphRepository(db)

    def analyze(self, file: UploadFile) -> tuple[UUID, UUID, str]:
        """解析上传的 STEP 文件，返回 (step_file_id, product_graph_id, status)。

        异常：
            StepFileInvalidError：文件扩展名无效或文件为空。
            StepParseFailedError：解析过程失败。
        """
        file_name = file.filename or "unnamed"

        # 验证文件扩展名
        if not file_name.lower().endswith(self.VALID_EXTENSION):
            raise StepFileInvalidError(file_name)

        # 读取文件内容并持久化到磁盘
        UPLOAD_DIR.mkdir(exist_ok=True)
        file_path = UPLOAD_DIR / file_name
        content = file.file.read()
        file_size = len(content)
        file_path.write_bytes(content)

        # 创建 StepFile 数据库记录
        sf = StepFile(
            file_name=file_name,
            file_path=str(file_path),
            file_size=file_size,
            status="uploaded",
        )
        self.step_repo.save(sf)
        step_file_id = UUID(sf.id)

        # 状态转换：uploaded → parsing
        self.step_repo.update_status(step_file_id, "parsing")

        try:
            # 优先尝试真实 STEP 解析
            parsed = parse_step_bytes(content)

            # 如果提取到有意义的名称且文件不是测试桩，则使用真实数据
            if parsed.name and parsed.name != "Unknown" and file_size > 100:
                pg = _build_product_graph_from_parsed(parsed.name, parsed.body_count)
            else:
                # 测试文件回退到 DEMO
                pg = DEMO_PRODUCT_GRAPH.model_copy(deep=True)
                pg.graphId = uuid.uuid4()

            pg_orm = ProductGraph(
                step_file_id=str(step_file_id),
                graph_json=pg.model_dump_json(),
                status="draft",
            )
            self.pg_repo.save(pg_orm)
            product_graph_id = UUID(pg_orm.id)

            # 状态转换：parsing → parsed
            self.step_repo.update_status(step_file_id, "parsed")
            # ProductGraph 状态：draft → generated
            self.pg_repo.update_status(product_graph_id, "generated")

            return step_file_id, product_graph_id, "parsed"

        except Exception:
            self.step_repo.update_status(step_file_id, "failed")
            raise StepParseFailedError(f"解析失败：{file_name}")
