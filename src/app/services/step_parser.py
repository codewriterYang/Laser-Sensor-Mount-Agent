"""轻量级 ISO 10303-21 实体解析器（MVP 阶段）。

从 STEP AP214 文件中提取产品结构，无需完整的几何解析。
支持单零件文件和装配体文件，所有数据均从文件中实际解析得出。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedPart:
    """从 STEP 文件中解析出的单个零件信息。"""
    name: str
    part_id: str = ""
    is_assembly: bool = False
    body_count: int = 0
    # 从坐标点计算的包围盒尺寸（近似，单位：毫米）
    length: float = 0.0   # X 方向
    width: float = 0.0    # Y 方向
    height: float = 0.0   # Z 方向


@dataclass
class ParsedProduct:
    """从 STEP 文件中提取的产品结构。"""
    name: str = "未知"
    schema: str = ""
    is_assembly: bool = False
    # 子零件列表（装配体时才有多个）
    parts: list[ParsedPart] = field(default_factory=list)
    # 包围盒
    length: float = 0.0
    width: float = 0.0
    height: float = 0.0


def _extract_bounding_box(text: str) -> tuple[float, float, float]:
    """从 STEP 文件的所有 CARTESIAN_POINT 中计算包围盒尺寸。

    采样前 5000 个坐标点计算大致尺寸（避免全量解析超时）。
    """
    # 匹配 CARTESIAN_POINT ( 'NONE', ( x, y, z ) )
    pattern = r"CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*([^)]+)\s*\)"
    matches = re.findall(pattern, text)

    if not matches:
        return 0.0, 0.0, 0.0

    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")

    # 采样以控制性能
    sample_count = min(len(matches), 5000)
    step = max(1, len(matches) // sample_count)

    for i, match in enumerate(matches):
        if i % step != 0:
            continue
        try:
            parts = [float(p.strip()) for p in match.split(",")]
            if len(parts) >= 3:
                x, y, z = parts[0], parts[1], parts[2]
                min_x, max_x = min(min_x, x), max(max_x, x)
                min_y, max_y = min(min_y, y), max(max_y, y)
                min_z, max_z = min(min_z, z), max(max_z, z)
        except ValueError:
            continue

    if min_x == float("inf"):
        return 0.0, 0.0, 0.0

    length = round(abs(max_x - min_x), 1)
    width = round(abs(max_y - min_y), 1)
    height = round(abs(max_z - min_z), 1)
    return length, width, height


def _extract_all_products(text: str) -> list[dict]:
    """从 STEP 文件中提取所有 PRODUCT 实体。

    返回产品列表，每个产品包含 {id, name, description}。
    """
    products = []
    # 匹配: #NNN = PRODUCT ( 'id', 'name', 'description', ( #context ) ) ;
    pattern = r"#(\d+)\s*=\s*PRODUCT\s*\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'?\s*,\s*\(\s*#(\d+)\s*\)"
    for m in re.finditer(pattern, text):
        products.append({
            "ref_id": int(m.group(1)),
            "prod_id": m.group(2),
            "name": m.group(3),
            "description": m.group(4),
            "context_ref": int(m.group(5)),
        })
    return products


def _extract_assembly_relations(text: str) -> list[dict]:
    """从 STEP 文件中提取装配关系（NEXT_ASSEMBLY_USAGE_OCCURRENCE）。

    返回关系列表，包含 {parent_id, child_id}。
    """
    relations = []
    # 匹配: #N = NEXT_ASSEMBLY_USAGE_OCCURRENCE ( 'id', 'label', 'desc', #parent_def, #child_prod, $ ) ;
    pattern = r"NEXT_ASSEMBLY_USAGE_OCCURRENCE\s*\([^,]*,[^,]*,[^,]*,\s*#(\d+)\s*,\s*#(\d+)"
    for m in re.finditer(pattern, text):
        relations.append({
            "parent_def_ref": int(m.group(1)),
            "child_prod_ref": int(m.group(2)),
        })
    return relations


def _extract_product_definition_mapping(text: str) -> dict[int, int]:
    """构建 PRODUCT_DEFINITION_FORMATION → PRODUCT 的映射。

    返回 {definition_formation_ref: product_ref}。
    """
    mapping = {}
    # #N = PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE ( ... , #product_ref ) ;
    pattern = r"#(\d+)\s*=\s*PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE\s*\([^)]*,\s*#(\d+)\s*\)"
    for m in re.finditer(pattern, text):
        mapping[int(m.group(1))] = int(m.group(2))
    return mapping


def parse_step_file(file_path: str | Path) -> ParsedProduct:
    """解析 STEP 文件，提取产品结构。"""
    path = Path(file_path)
    content = path.read_text(encoding="utf-8", errors="replace")
    return _parse_content(content)


def parse_step_bytes(content: bytes) -> ParsedProduct:
    """从字节流解析 STEP 内容（用于 UploadFile）。"""
    text = content.decode("utf-8", errors="replace")
    return _parse_content(text)


def _parse_content(text: str) -> ParsedProduct:
    """核心解析逻辑：从 STEP 文本中提取所有可用的产品结构信息。"""
    result = ParsedProduct()

    # 1. 提取 schema 信息
    schema_match = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", text)
    if schema_match:
        result.schema = schema_match.group(1)

    # 2. 提取所有 PRODUCT 实体
    products = _extract_all_products(text)
    if not products:
        return result  # 无产品数据，返回默认

    # 根产品是第一个
    root_product = products[0]
    result.name = root_product["name"] or root_product["prod_id"]

    # 3. 检查是否为装配体
    relations = _extract_assembly_relations(text)
    result.is_assembly = len(relations) > 0

    # 4. 统计 MANIFOLD_SOLID_BREP（几何体数量）
    body_count = len(re.findall(r"=\s*MANIFOLD_SOLID_BREP\s*\(", text))

    # 5. 计算包围盒尺寸
    length, width, height = _extract_bounding_box(text)
    result.length = length
    result.width = width
    result.height = height

    if result.is_assembly and len(products) > 1:
        # 装配体：构建子零件列表
        # 建立 PRODUCT_DEFINITION_FORMATION → PRODUCT 映射
        pdf_map = _extract_product_definition_mapping(text)

        # 建立 PRODUCT ref_id → product info 映射
        prod_map = {p["ref_id"]: p for p in products}

        # 从装配关系中提取子零件
        child_prod_refs = set()
        for rel in relations:
            child_ref = rel["child_prod_ref"]
            # 尝试通过 PRODUCT_DEFINITION_FORMATION 映射解析
            if child_ref in pdf_map:
                child_ref = pdf_map[child_ref]
            child_prod_refs.add(child_ref)

        for prod_ref in child_prod_refs:
            if prod_ref in prod_map:
                p = prod_map[prod_ref]
                part = ParsedPart(
                    name=p["name"] or p["prod_id"],
                    part_id=str(prod_ref),
                    body_count=1,
                )
                result.parts.append(part)

    if not result.parts:
        # 单零件：创建一个零件节点
        result.parts.append(ParsedPart(
            name=result.name,
            part_id="root_part",
            body_count=max(body_count, 1),
            length=length,
            width=width,
            height=height,
        ))

    return result
