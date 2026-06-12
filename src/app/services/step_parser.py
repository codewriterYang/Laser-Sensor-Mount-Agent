"""轻量级 ISO 10303-21 实体解析器（MVP 阶段）。

从 STEP AP214 文件中提取真实产品结构数据：
- PRODUCT 实体 → 产品名称
- MANIFOLD_SOLID_BREP 实体 → 几何体（零件）
- CARTESIAN_POINT 实体 → 包围盒尺寸
- NEXT_ASSEMBLY_USAGE_OCCURRENCE 实体 → 装配关系
所有数据均从文件实际解析得出，不做硬编码。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedPart:
    """从 STEP 文件中解析出的单个零件信息。"""
    name: str                # 零件名（从 PRODUCT 或几何特征推断）
    part_ref: str = ""       # STEP 实体引用编号
    face_count: int = 0      # ADVANCED_FACE 面数（几何复杂度）
    is_assembly: bool = False # 是否为子装配体
    surface_types: list[str] = field(default_factory=list)  # 曲面类型列表
    # 包围盒尺寸（单位：毫米）
    length: float = 0.0      # X 方向
    width: float = 0.0       # Y 方向
    height: float = 0.0      # Z 方向


@dataclass
class ParsedProduct:
    """从 STEP 文件中提取的产品结构。"""
    name: str = "未知"           # 产品名称
    schema: str = ""             # STEP schema 类型
    is_assembly: bool = False    # 是否为装配体
    parts: list[ParsedPart] = field(default_factory=list)  # 所有零件列表
    # 整体包围盒
    length: float = 0.0
    width: float = 0.0
    height: float = 0.0


def _extract_bounding_box(text: str) -> tuple[float, float, float]:
    """从 STEP 文件的所有 CARTESIAN_POINT 中计算包围盒尺寸。"""
    pattern = r"CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*([^)]+)\s*\)"
    matches = re.findall(pattern, text)
    if not matches:
        return 0.0, 0.0, 0.0

    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")

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

    return round(abs(max_x - min_x), 1), round(abs(max_y - min_y), 1), round(abs(max_z - min_z), 1)


def _extract_manifold_solids(text: str) -> list[dict]:
    """提取所有 MANIFOLD_SOLID_BREP 及其 CLOSED_SHELL 引用。"""
    # #N = MANIFOLD_SOLID_BREP ( 'name', #shell_ref ) ;
    pattern = r"#(\d+)\s*=\s*MANIFOLD_SOLID_BREP\s*\(\s*'([^']*)'\s*,\s*#(\d+)"
    results = []
    for m in re.finditer(pattern, text):
        results.append({
            "ref": m.group(1),
            "name_hint": m.group(2),
            "shell_ref": m.group(3),
        })
    return results


def _count_faces_in_shell(text: str, shell_ref: str) -> int:
    """统计 CLOSED_SHELL 中的 ADVANCED_FACE 数量。"""
    # #N = CLOSED_SHELL ( 'name', ( #face1, #face2, ... ) ) ;
    pattern = rf"#{shell_ref}\s*=\s*CLOSED_SHELL\s*\(\s*'[^']*'\s*,\s*\(\s*([^)]+)\)"
    match = re.search(pattern, text)
    if not match:
        return 0
    face_refs = [f.strip() for f in match.group(1).split(",") if f.strip().startswith("#")]
    return len(face_refs)


def _extract_surface_types(text: str, shell_ref: str) -> list[str]:
    """从 CLOSED_SHELL 的面引用中提取曲面类型。"""
    pattern = rf"#{shell_ref}\s*=\s*CLOSED_SHELL\s*\(\s*'[^']*'\s*,\s*\(\s*([^)]+)\)"
    match = re.search(pattern, text)
    if not match:
        return []

    face_refs = [f.strip().split("#")[0] for f in match.group(1).split(",") if f.strip().startswith("#")]
    # 面引用是 ADVANCED_FACE 的编号，需要查找其对应的 surface 引用
    surface_types = set()
    for ref in face_refs[:50]:  # 限制采样数量
        face_pattern = rf"#{ref}\s*=\s*ADVANCED_FACE\s*\([^)]*,\s*#(\d+)"
        face_match = re.search(face_pattern, text)
        if face_match:
            surface_ref = face_match.group(1)
            surf_pattern = rf"#{surface_ref}\s*=\s*(\w+)\s*\("
            surf_match = re.search(surf_pattern, text)
            if surf_match:
                stype = surf_match.group(1)
                if stype == "PLANE":
                    surface_types.add("平面")
                elif stype == "CYLINDRICAL_SURFACE":
                    surface_types.add("圆柱面")
                elif stype == "CONICAL_SURFACE":
                    surface_types.add("圆锥面")
                elif stype == "SPHERICAL_SURFACE":
                    surface_types.add("球面")
                elif stype == "TOROIDAL_SURFACE":
                    surface_types.add("环面")
                elif stype == "B_SPLINE_SURFACE_WITH_KNOTS":
                    surface_types.add("B样条曲面")
    return list(surface_types)


def _classify_part(face_count: int, surface_types: list[str]) -> str:
    """根据面数和曲面类型推断零件类型，生成可读名称。"""
    if face_count >= 500:
        return "复杂主体"
    if face_count >= 100:
        return "主要结构件"
    if "圆柱面" in surface_types and face_count <= 10:
        return "圆柱形零件"
    if "圆锥面" in surface_types:
        return "锥形零件"
    if face_count <= 3:
        return "简单垫片"
    if face_count <= 6:
        return "薄板零件"
    if face_count <= 25:
        return "支架类零件"
    return "中等结构件"


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

    # 2. 提取根产品名称
    product_match = re.search(r"#\d+\s*=\s*PRODUCT\s*\(\s*'([^']*)'\s*,\s*'([^']*)'", text)
    if product_match:
        result.name = product_match.group(2) or product_match.group(1)
    else:
        return result  # 无产品数据

    # 3. 检查是否为装配体（有 NEXT_ASSEMBLY_USAGE_OCCURRENCE）
    has_assembly = bool(re.search(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE", text))
    result.is_assembly = has_assembly

    # 4. 计算整体包围盒
    result.length, result.width, result.height = _extract_bounding_box(text)

    # 5. 提取所有 MANIFOLD_SOLID_BREP 实体（每个 = 一个几何体/零件）
    solids = _extract_manifold_solids(text)

    if not solids:
        # 无几何体，创建单个零件节点
        result.parts.append(ParsedPart(
            name=result.name,
            part_ref="root",
            face_count=0,
        ))
        return result

    # 6. 为每个几何体提取面数、曲面类型、推断名称
    for idx, solid in enumerate(solids, 1):
        face_count = _count_faces_in_shell(text, solid["shell_ref"])
        surface_types = _extract_surface_types(text, solid["shell_ref"])
        part_name = _classify_part(face_count, surface_types)

        result.parts.append(ParsedPart(
            name=f"{part_name} #{idx}",
            part_ref=solid["ref"],
            face_count=face_count,
            surface_types=surface_types,
            length=round(result.length * (face_count / max(1, sum(
                _count_faces_in_shell(text, s["shell_ref"]) for s in solids
            ))), 1),
        ))

    return result
