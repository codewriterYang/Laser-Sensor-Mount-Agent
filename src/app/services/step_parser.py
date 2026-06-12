"""轻量级 ISO 10303-21 实体解析器（MVP 阶段）。

从 STEP AP214 文件中提取产品结构，无需完整的几何解析。
同时支持单零件文件和装配体文件。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StepEntity:
    """解析后的 STEP 实体: {id: int, type: str, attributes: str}。"""
    id: int
    type: str
    attributes: str


@dataclass
class ParsedProduct:
    """从 STEP 文件中提取的产品结构。"""
    name: str = "未知"
    schema: str = ""
    body_count: int = 0
    is_assembly: bool = False
    sub_components: list[str] = field(default_factory=list)


def parse_step_file(file_path: str | Path) -> ParsedProduct:
    """解析 STEP 文件并提取产品结构。

    读取 ISO 10303-21 格式（STEP AP203/AP214）。
    可处理最多约 20 万实体的文件。

    返回包含名称、实体数量及组件信息的 ParsedProduct。
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8", errors="replace")

    result = ParsedProduct()

    # 提取 schema
    schema_match = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", content)
    if schema_match:
        result.schema = schema_match.group(1)

    # 查找 PRODUCT 实体 — 这是根产品名称
    # 格式: #NNN = PRODUCT ( 'id', 'name', 'description', ( #context ) ) ;
    product_match = re.search(r"#\d+\s*=\s*PRODUCT\s*\(\s*'([^']*)'\s*,\s*'([^']*)'", content)
    if product_match:
        result.name = product_match.group(2) or product_match.group(1)

    # 统计 MANIFOLD_SOLID_BREP 实体 — 每个代表一个物理实体
    result.body_count = len(re.findall(r"=\s*MANIFOLD_SOLID_BREP\s*\(", content))

    # 检查 NEXT_ASSEMBLY_USAGE_OCCURRENCE — 表明是装配体结构
    assembly_count = len(re.findall(r"=\s*NEXT_ASSEMBLY_USAGE_OCCURRENCE\s*\(", content))
    result.is_assembly = assembly_count > 0

    # 如果是装配体，提取子组件名称
    if result.is_assembly:
        # 查找引用不同 PRODUCT 的所有 PRODUCT_DEFINITION_FORMATION 实体
        # 目前，将实体组枚举为命名零件
        for i in range(result.body_count):
            result.sub_components.append(f"Component_{i+1}")

    return result


def parse_step_bytes(content: bytes) -> ParsedProduct:
    """从字节流解析 STEP 内容（用于 UploadFile）。"""
    text = content.decode("utf-8", errors="replace")
    result = ParsedProduct()

    schema_match = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", text)
    if schema_match:
        result.schema = schema_match.group(1)

    product_match = re.search(r"#\d+\s*=\s*PRODUCT\s*\(\s*'([^']*)'\s*,\s*'([^']*)'", text)
    if product_match:
        result.name = product_match.group(2) or product_match.group(1)

    result.body_count = len(re.findall(r"=\s*MANIFOLD_SOLID_BREP\s*\(", text))
    assembly_count = len(re.findall(r"=\s*NEXT_ASSEMBLY_USAGE_OCCURRENCE\s*\(", text))
    result.is_assembly = assembly_count > 0

    # 对于单零件文件：为每个实体创建一个零件，或仅创建一个零件
    if result.body_count == 0:
        result.body_count = 1  # 至少有一个隐式实体

    for i in range(result.body_count):
        label = f"Body_{i+1}" if result.body_count > 1 else result.name
        result.sub_components.append(label)

    return result
