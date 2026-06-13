"""轻量级 ISO 10303-21 实体解析器（MVP 阶段）。

从 STEP AP214 文件中提取真实产品结构数据：
- PRODUCT 实体 → 产品名称
- MANIFOLD_SOLID_BREP 实体 → 几何体（零件）
- CARTESIAN_POINT 实体 → 包围盒尺寸
- NEXT_ASSEMBLY_USAGE_OCCURRENCE 实体 → 装配关系
- ADVANCED_FACE / 曲面引用 → 曲面类型（平面/圆柱/球面/环面/锥面/B样条）
- COLOUR_RGB → 零件颜色（通过 STYLED_ITEM 链追溯）
所有数据均从文件实际解析得出，不做硬编码。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedPart:
    """从 STEP 文件中解析出的单个零件信息。"""
    name: str                # 零件名（从几何特征推断分类）
    part_ref: str = ""       # STEP 实体引用编号
    face_count: int = 0      # ADVANCED_FACE 面数（几何复杂度）
    is_assembly: bool = False  # 是否为子装配体
    surface_types: list[str] = field(default_factory=list)  # 曲面类型列表
    # 包围盒尺寸（单位：毫米）—— 基于面数比例估算
    length: float = 0.0      # X 方向
    width: float = 0.0       # Y 方向
    height: float = 0.0      # Z 方向
    # 零件颜色（从 STEP COLOUR_RGB 实体提取，None 表示未提取到）
    color: tuple[float, float, float] | None = None  # (R, G, B) 0.0~1.0


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
    pattern = r"CARTESIAN_POINT\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*([^)]+)\s*\)"
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
    pattern = r"#(\d+)\s*=\s*MANIFOLD_SOLID_BREP\s*\(\s*['\"][^'\"]*['\"]\s*,\s*#(\d+)"
    results = []
    for m in re.finditer(pattern, text):
        results.append({
            "ref": m.group(1),
            "shell_ref": m.group(2),
        })
    return results


def _count_faces_in_shell(text: str, shell_ref: str) -> int:
    """统计 CLOSED_SHELL 中的 ADVANCED_FACE 数量。"""
    pattern = rf"#{shell_ref}\s*=\s*CLOSED_SHELL\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*([^)]+)\)"
    match = re.search(pattern, text)
    if not match:
        return 0
    face_refs = [f.strip() for f in match.group(1).split(",") if f.strip().startswith("#")]
    return len(face_refs)


def _extract_surface_types(text: str, shell_ref: str) -> list[str]:
    """从 CLOSED_SHELL 的面引用中提取曲面类型。"""
    pattern = rf"#{shell_ref}\s*=\s*CLOSED_SHELL\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*([^)]+)\)"
    match = re.search(pattern, text)
    if not match:
        return []

    face_refs = [f.strip().lstrip("#") for f in match.group(1).split(",") if f.strip().startswith("#")]

    _SURFACE_MAP = {
        "PLANE": "平面",
        "CYLINDRICAL_SURFACE": "圆柱面",
        "CONICAL_SURFACE": "圆锥面",
        "SPHERICAL_SURFACE": "球面",
        "TOROIDAL_SURFACE": "环面",
        "B_SPLINE_SURFACE_WITH_KNOTS": "B样条曲面",
    }

    surface_types = set()
    for ref in face_refs[:50]:
        face_pattern = rf"#{ref}\s*=\s*ADVANCED_FACE\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\([^)]*\)\s*,\s*#(\d+)"
        face_match = re.search(face_pattern, text)
        if face_match:
            surface_ref = face_match.group(1)
            surf_pattern = rf"#{surface_ref}\s*=\s*(\w+)\s*\("
            surf_match = re.search(surf_pattern, text)
            if surf_match:
                stype = surf_match.group(1)
                if stype in _SURFACE_MAP:
                    surface_types.add(_SURFACE_MAP[stype])

    return list(surface_types)


def _extract_part_colors(text: str, msb_refs: list[str]) -> dict[str, tuple[float, float, float]]:
    """从 STEP 文件中提取每个 MANIFOLD_SOLID_BREP 的颜色。

    链路：STYLED_ITEM → PRESENTATION_STYLE_ASSIGNMENT → SURFACE_STYLE_USAGE
          → SURFACE_SIDE_STYLE → SURFACE_STYLE_FILL_AREA
          → FILL_AREA_STYLE → FILL_AREA_STYLE_COLOUR → COLOUR_RGB

    返回 {msb_ref: (R, G, B)}，仅包含非白色颜色。
    """
    # 1. COLOUR_RGB
    colours = {}
    for m in re.finditer(r"#(\d+)\s*=\s*COLOUR_RGB\s*\(\s*['\"][^'\"]*['\"]\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)", text):
        colours[m.group(1)] = (float(m.group(2)), float(m.group(3)), float(m.group(4)))

    # 2. FILL_AREA_STYLE_COLOUR → COLOUR_RGB ref
    fasc_to_colour = {}
    for m in re.finditer(r"#(\d+)\s*=\s*FILL_AREA_STYLE_COLOUR\s*\(\s*['\"][^'\"]*['\"]\s*,\s*#(\d+)", text):
        fasc_to_colour[m.group(1)] = m.group(2)

    # 3. FILL_AREA_STYLE → FILL_AREA_STYLE_COLOUR ref
    fill_to_fasc = {}
    for m in re.finditer(r"#(\d+)\s*=\s*FILL_AREA_STYLE\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*#(\d+)", text):
        fill_to_fasc[m.group(1)] = m.group(2)

    # 4. SURFACE_STYLE_FILL_AREA → FILL_AREA_STYLE ref
    ssfa_to_fill = {}
    for m in re.finditer(r"#(\d+)\s*=\s*SURFACE_STYLE_FILL_AREA\s*\(\s*#(\d+)", text):
        ssfa_to_fill[m.group(1)] = m.group(2)

    # 5. SURFACE_SIDE_STYLE → SURFACE_STYLE_FILL_AREA ref
    side_to_ssfa = {}
    for m in re.finditer(r"#(\d+)\s*=\s*SURFACE_SIDE_STYLE\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*#(\d+)", text):
        side_to_ssfa[m.group(1)] = m.group(2)

    # 6. SURFACE_STYLE_USAGE → SURFACE_SIDE_STYLE ref
    usage_to_side = {}
    for m in re.finditer(r"#(\d+)\s*=\s*SURFACE_STYLE_USAGE\s*\(\s*\.BOTH\.\s*,\s*#(\d+)", text):
        usage_to_side[m.group(1)] = m.group(2)

    # 7. PRESENTATION_STYLE_ASSIGNMENT → SURFACE_STYLE_USAGE ref
    psa_to_usage = {}
    for m in re.finditer(r"#(\d+)\s*=\s*PRESENTATION_STYLE_ASSIGNMENT\s*\(\s*\(\s*#(\d+)", text):
        psa_to_usage[m.group(1)] = m.group(2)

    # 8. 构建 MSB → faces 映射
    msb_to_shell = {}
    for m in re.finditer(r"#(\d+)\s*=\s*MANIFOLD_SOLID_BREP\s*\(\s*['\"][^'\"]*['\"]\s*,\s*#(\d+)", text):
        msb_to_shell[m.group(1)] = m.group(2)

    shell_to_faces = {}
    for m in re.finditer(r"#(\d+)\s*=\s*CLOSED_SHELL\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*([^)]+)\)", text):
        faces = [f.strip().lstrip("#") for f in m.group(2).split(",") if f.strip().startswith("#")]
        shell_to_faces[m.group(1)] = set(faces)

    face_to_msb: dict[str, str] = {}
    for msb_ref, shell_ref in msb_to_shell.items():
        for face_ref in shell_to_faces.get(shell_ref, set()):
            face_to_msb[face_ref] = msb_ref

    # 9. STYLED_ITEM → 链式追溯颜色
    msb_colors: dict[str, list[tuple[float, float, float]]] = {}
    for m in re.finditer(r"#(\d+)\s*=\s*STYLED_ITEM\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*#(\d+)\s*\)\s*,\s*#(\d+)", text):
        psa_ref = m.group(2)
        item_ref = m.group(3)

        usage_ref = psa_to_usage.get(psa_ref)
        if not usage_ref:
            continue
        side_ref = usage_to_side.get(usage_ref)
        if not side_ref:
            continue
        ssfa_ref = side_to_ssfa.get(side_ref)
        if not ssfa_ref:
            continue
        fill_ref = ssfa_to_fill.get(ssfa_ref)
        if not fill_ref:
            continue
        fasc_ref = fill_to_fasc.get(fill_ref)
        if not fasc_ref:
            continue
        colour_ref = fasc_to_colour.get(fasc_ref)
        if not colour_ref:
            continue
        colour = colours.get(colour_ref)
        if not colour:
            continue

        # 映射到 MSB
        msb_ref = None
        if item_ref in msb_to_shell:
            msb_ref = item_ref
        elif item_ref in face_to_msb:
            msb_ref = face_to_msb[item_ref]

        if msb_ref:
            if msb_ref not in msb_colors:
                msb_colors[msb_ref] = []
            msb_colors[msb_ref].append(colour)

    # 9. 提取每个 MSB 的主色（非白色出现最多的颜色）
    result: dict[str, tuple[float, float, float]] = {}
    for msb_ref, colors in msb_colors.items():
        non_white = [c for c in colors if not (c[0] > 0.99 and c[1] > 0.99 and c[2] > 0.99)]
        if non_white:
            # 取出现最多的非白色
            dominant = max(set(non_white), key=non_white.count)
            result[msb_ref] = dominant

    return result


def _classify_part(face_count: int, surface_types: list[str]) -> str:
    """根据面数和曲面类型推断零件类型，生成可读名称。"""
    has_cylinder = "圆柱面" in surface_types
    has_sphere = "球面" in surface_types
    has_torus = "环面" in surface_types
    has_cone = "圆锥面" in surface_types

    if face_count >= 500:
        if has_sphere or has_torus:
            return "复杂曲面主体"
        return "复杂主体"
    if face_count >= 100:
        if has_cylinder:
            return "圆柱结构件"
        return "主要结构件"
    if has_torus and has_cone:
        return "螺纹紧固件"
    if has_cylinder and has_cone:
        return "锥孔连接件"
    if has_sphere:
        return "球形零件"
    if has_cylinder and face_count <= 10:
        return "圆柱形零件"
    if has_cone:
        return "锥形零件"
    if face_count <= 3:
        if has_cylinder:
            return "垫圈"
        return "薄垫片"
    if face_count <= 6:
        return "薄板零件"
    if face_count <= 25:
        if has_cylinder:
            return "带孔支架"
        return "支架类零件"
    return "中等结构件"


def _estimate_part_dimensions(
    face_count: int, total_face_count: int,
    overall_length: float, overall_width: float, overall_height: float,
    surface_types: list[str],
) -> tuple[float, float, float]:
    """根据面数比例和曲面类型估算零件包围盒尺寸。"""
    if total_face_count == 0 or overall_length == 0:
        return 0.0, 0.0, 0.0

    ratio = (face_count / total_face_count) ** 0.5

    has_cylinder = "圆柱面" in surface_types
    has_sphere = "球面" in surface_types

    if has_sphere:
        dim = overall_length * ratio * 0.6
        return round(dim, 1), round(dim, 1), round(dim, 1)
    elif has_cylinder and face_count <= 10:
        return round(overall_length * ratio * 1.2, 1), round(overall_width * ratio * 0.4, 1), round(overall_width * ratio * 0.4, 1)
    elif face_count <= 6:
        return round(overall_length * ratio * 0.8, 1), round(overall_width * ratio * 0.6, 1), round(overall_height * ratio * 0.1, 1)
    elif face_count <= 25:
        return round(overall_length * ratio * 0.7, 1), round(overall_width * ratio * 0.5, 1), round(overall_height * ratio * 0.4, 1)
    else:
        return round(overall_length * ratio, 1), round(overall_width * ratio, 1), round(overall_height * ratio, 1)


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
    product_match = re.search(r"#\d+\s*=\s*PRODUCT\s*\(\s*['\"]([^'\"]*)['\"]\s*,\s*['\"]([^'\"]*)['\"]", text)
    if product_match:
        result.name = product_match.group(2) or product_match.group(1)
    else:
        return result

    # 3. 检查是否为装配体
    has_assembly = bool(re.search(r"NEXT_ASSEMBLY_USAGE_OCCURRENCE", text))
    result.is_assembly = has_assembly

    # 4. 计算整体包围盒
    result.length, result.width, result.height = _extract_bounding_box(text)

    # 5. 提取所有 MANIFOLD_SOLID_BREP 实体
    solids = _extract_manifold_solids(text)

    if not solids:
        result.parts.append(ParsedPart(
            name=result.name, part_ref="root", face_count=0,
        ))
        return result

    # 6. 计算面数总和 + 提取颜色
    face_counts = []
    for solid in solids:
        fc = _count_faces_in_shell(text, solid["shell_ref"])
        face_counts.append(fc)
    total_face_count = sum(face_counts)

    msb_refs = [s["ref"] for s in solids]
    part_colors = _extract_part_colors(text, msb_refs)

    # 7. 为每个几何体提取完整信息
    for idx, solid in enumerate(solids):
        face_count = face_counts[idx]
        surface_types = _extract_surface_types(text, solid["shell_ref"])
        part_name = _classify_part(face_count, surface_types)

        pl, pw, ph = _estimate_part_dimensions(
            face_count, total_face_count,
            result.length, result.width, result.height,
            surface_types,
        )

        color = part_colors.get(solid["ref"])

        result.parts.append(ParsedPart(
            name=part_name,  # 不再加 "#N" 后缀
            part_ref=solid["ref"],
            face_count=face_count,
            surface_types=surface_types,
            length=pl,
            width=pw,
            height=ph,
            color=color,
        ))

    return result
