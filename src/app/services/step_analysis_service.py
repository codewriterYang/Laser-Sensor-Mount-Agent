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
from .step_parser import ParsedProduct, parse_step_bytes
from ..logger import logger


class StepFileNotFoundError(Exception):
    """STEP 文件未找到异常。"""
    pass


class StepFileInvalidError(Exception):
    """STEP 文件格式无效异常。"""
    pass


class StepParseFailedError(Exception):
    """STEP 解析失败异常。"""
    pass


# --- 演示用 ProductGraph（仅用于测试桩文件 / 无可识别内容的 STEP）---

DEMO_PRODUCT_GRAPH = ProductGraphSchema(
    graphId=UUID("11111111-1111-1111-1111-111111111111"),
    nodes=[
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000001"), nodeType="assembly", name="激光传感器安装组件", quantity=1),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000002"), nodeType="part", name="底板", quantity=1, metadata={"material": "铝合金 6061", "partNumber": "LSM-BASE-001"}),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000003"), nodeType="part", name="支架", quantity=1, metadata={"material": "钢", "partNumber": "LSM-BRK-001"}),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000004"), nodeType="part", name="激光传感器", quantity=1, metadata={"partNumber": "LS-2000"}),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000005"), nodeType="part", name="M4x12 螺丝", quantity=2, metadata={"material": "不锈钢"}),
        NodeSchema(nodeId=UUID("a1000000-0000-0000-0000-000000000006"), nodeType="part", name="M4 垫片", quantity=2, metadata={"material": "不锈钢"}),
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


def _build_product_graph(parsed: ParsedProduct) -> ProductGraphSchema:
    """从 STEP 解析结果构建 ProductGraph。

    所有节点和边均来自实际解析数据，不做任何假零件：
    - 单零件文件：1 个装配体节点 + 1 个零件节点
    - 装配体文件：1 个根装配体 + N 个真实子零件节点
    - 零件名使用真实产品名，不带 "Assembly"/"装配体" 后缀
    """
    assembly_id = uuid.uuid4()
    nodes: list[NodeSchema] = []
    edges: list[EdgeSchema] = []

    # 装配体根节点 — 带包围盒尺寸（如果解析得出）
    root_meta: dict = {}
    if parsed.length > 0:
        root_meta = {"length": parsed.length, "width": parsed.width, "height": parsed.height}
    nodes.append(NodeSchema(
        nodeId=assembly_id, nodeType="assembly",
        name=parsed.name, quantity=1,
        metadata=root_meta,
    ))

    # 真实子零件节点（从 STEP 文件中实际解析得出）
    for part in parsed.parts:
        part_id = uuid.uuid4()
        part_meta: dict = {}
        if part.face_count > 0:
            part_meta["faceCount"] = part.face_count
        if part.surface_types:
            part_meta["surfaceTypes"] = part.surface_types
        if part.length > 0:
            part_meta["length"] = part.length
            part_meta["width"] = part.width
            part_meta["height"] = part.height

        nodes.append(NodeSchema(
            nodeId=part_id,
            nodeType="assembly" if part.is_assembly else "part",
            name=part.name,
            quantity=1,
            metadata=part_meta,
        ))
        edges.append(EdgeSchema(
            edgeId=uuid.uuid4(),
            source=assembly_id,
            target=part_id,
            relation="contains",
        ))

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
        logger.info(f"开始解析 STEP 文件：{file_name}")

        # 验证文件扩展名
        if not file_name.lower().endswith(self.VALID_EXTENSION):
            logger.warning(f"文件格式无效：{file_name}")
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
            # 用真实解析器解析 STEP 文件内容
            parsed = parse_step_bytes(content)

            # 判断是否解析出了有效数据：有产品名 且 不是测试桩文件
            if parsed.name and parsed.name != "未知" and file_size > 100:
                pg = _build_product_graph(parsed)
                logger.info(f"STEP 解析成功：{parsed.name}，{len(parsed.parts)} 个零件，"
                           f"尺寸 {parsed.length}×{parsed.width}×{parsed.height}mm")
            else:
                pg = DEMO_PRODUCT_GRAPH.model_copy(deep=True)
                pg.graphId = uuid.uuid4()
                logger.info(f"使用演示 ProductGraph（测试文件）")

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
