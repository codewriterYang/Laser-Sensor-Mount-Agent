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
from .step_parser import ParsedProduct, ParsedPart, parse_step_bytes
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


def _merge_identical_parts(parts: list[ParsedPart]) -> list[tuple[ParsedPart, int]]:
    """合并相同零件（名称+面数+曲面类型相同的视为同一零件）。

    返回 [(part, quantity), ...] 列表。
    """
    groups: dict[tuple, list[ParsedPart]] = {}
    for part in parts:
        # 相同名称 + 相同面数范围（±10%）+ 相同曲面类型集合 = 同一零件
        key = (part.name, tuple(sorted(part.surface_types)))
        groups.setdefault(key, []).append(part)

    merged = []
    for parts_in_group in groups.values():
        representative = parts_in_group[0]
        count = len(parts_in_group)
        merged.append((representative, count))
    return merged


def _build_product_graph(parsed: ParsedProduct, file_path: str = "") -> ProductGraphSchema:
    """从 STEP 解析结果构建 ProductGraph。

    相同零件自动合并，数量显示为 >1。
    颜色信息存储在 metadata 中。
    """
    assembly_id = uuid.uuid4()
    nodes: list[NodeSchema] = []
    edges: list[EdgeSchema] = []

    # 装配体根节点
    root_meta: dict = {}
    if parsed.length > 0:
        root_meta = {"length": parsed.length, "width": parsed.width, "height": parsed.height}
    if file_path:
        root_meta["filePath"] = file_path
    nodes.append(NodeSchema(
        nodeId=assembly_id, nodeType="assembly",
        name=parsed.name, quantity=1,
        metadata=root_meta,
    ))

    # 合并相同零件
    merged_parts = _merge_identical_parts(parsed.parts)

    for part, quantity in merged_parts:
        part_id = uuid.uuid4()
        part_meta: dict = {}
        if part.face_count > 0:
            part_meta["faceCount"] = part.face_count
        if part.surface_types:
            part_meta["surfaceTypes"] = part.surface_types
        if part.length > 0 or part.width > 0 or part.height > 0:
            part_meta["length"] = part.length
            part_meta["width"] = part.width
            part_meta["height"] = part.height
        if part.color:
            # 存储为 RGB 字符串（0-255 范围）
            part_meta["color"] = f"#{int(part.color[0]*255):02x}{int(part.color[1]*255):02x}{int(part.color[2]*255):02x}"

        nodes.append(NodeSchema(
            nodeId=part_id,
            nodeType="assembly" if part.is_assembly else "part",
            name=part.name,
            quantity=quantity,
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
    """STEP 文件解析服务：将上传的 STEP 文件转换为 ProductGraph。"""

    VALID_EXTENSION = ".step"

    def __init__(self, db: Session):
        self.db = db
        self.step_repo = StepFileRepository(db)
        self.pg_repo = ProductGraphRepository(db)

    def analyze(self, file: UploadFile) -> tuple[UUID, UUID, str]:
        """解析上传的 STEP 文件，返回 (step_file_id, product_graph_id, status)。"""
        file_name = file.filename or "unnamed"
        logger.info(f"开始解析 STEP 文件：{file_name}")

        if not file_name.lower().endswith(self.VALID_EXTENSION):
            logger.warning(f"文件格式无效：{file_name}")
            raise StepFileInvalidError(file_name)

        UPLOAD_DIR.mkdir(exist_ok=True)
        file_path = UPLOAD_DIR / file_name
        content = file.file.read()
        file_size = len(content)
        file_path.write_bytes(content)

        sf = StepFile(
            file_name=file_name,
            file_path=str(file_path),
            file_size=file_size,
            status="uploaded",
        )
        self.step_repo.save(sf)
        step_file_id = UUID(sf.id)
        self.step_repo.update_status(step_file_id, "parsing")

        try:
            parsed = parse_step_bytes(content)

            if parsed.name and parsed.name != "未知" and file_size > 100:
                pg = _build_product_graph(parsed, file_path=str(file_path))
                logger.info(f"STEP 解析成功：{parsed.name}，{len(parsed.parts)} 个零件，"
                           f"尺寸 {parsed.length}×{parsed.width}×{parsed.height}mm")
                # 自动从 STEP 文件生成 BOM 库数据
                try:
                    from .bom_library import generate_bom_from_step
                    step_text = content.decode("utf-8", errors="replace")
                    bom_result = generate_bom_from_step(step_text)
                    count = len(bom_result.get("standard_parts", []))
                    logger.info(f"BOM 自动生成：{count} 个零件条目")
                except Exception as e:
                    logger.warning(f"BOM 自动生成失败：{e}")
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

            self.step_repo.update_status(step_file_id, "parsed")
            self.pg_repo.update_status(product_graph_id, "generated")

            return step_file_id, product_graph_id, "parsed"

        except Exception:
            self.step_repo.update_status(step_file_id, "failed")
            raise StepParseFailedError(f"解析失败：{file_name}")
