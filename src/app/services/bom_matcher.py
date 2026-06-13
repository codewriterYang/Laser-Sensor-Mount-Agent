"""BOM 匹配器 — 从 STEP 几何特征匹配到 BOM 库中的零件类型。

匹配逻辑：
1. 提取几何特征签名（面数、曲面类型、圆柱半径、边线类型、包围盒比例）
2. 与 BOM 标准件/模板的 geometry_signature 逐一匹配
3. 返回最佳匹配的零件信息（含材料、视觉描述、典型尺寸）
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from .bom_library import get_material, get_standard_parts, get_part_templates
from ..logger import logger


@dataclass
class GeometricFeatures:
    """从 STEP 文件提取的几何特征签名。"""
    face_count: int = 0
    surface_types: list[str] = field(default_factory=list)
    # 圆柱特征
    cylindrical_radii: list[float] = field(default_factory=list)  # 所有圆柱面半径
    has_cylinder: bool = False
    has_sphere: bool = False
    has_torus: bool = False
    has_cone: bool = False
    has_plane: bool = False
    # 边线类型统计
    edge_line_count: int = 0      # 直线边数
    edge_circle_count: int = 0    # 圆弧边数
    edge_spline_count: int = 0    # 样条曲线边数
    # 包围盒
    bbox_length: float = 0.0
    bbox_width: float = 0.0
    bbox_height: float = 0.0
    # 比例类型
    aspect_ratio_type: str = "unknown"  # elongated/flat/compact/cubic


@dataclass
class BomMatchResult:
    """BOM 匹配结果。"""
    match_type: str = "unknown"       # standard_part / template / material_only / none
    match_id: str = ""                # 匹配的 BOM 条目 ID
    name_cn: str = ""                 # 中文名
    name_en: str = ""                 # 英文名
    material_id: str = ""             # 材料 ID
    material_name: str = ""           # 材料中文名
    color_hex: str = ""               # 颜色 hex
    color_name: str = ""              # 颜色英文名
    finish: str = ""                  # 表面处理
    visual_description: str = ""      # 详细视觉描述（直接用于 Prompt）
    confidence: float = 0.0           # 匹配置信度 0.0~1.0
    # 增强的几何描述
    cylindrical_features: str = ""    # "3x Ø4mm holes, 1x Ø12mm bore"
    edge_profile: str = ""            # "mostly straight edges" / "rounded profile"


def extract_geometric_features(
    text: str,
    shell_ref: str,
    bbox_length: float = 0.0,
    bbox_width: float = 0.0,
    bbox_height: float = 0.0,
) -> GeometricFeatures:
    """从 STEP 文件为单个零件提取几何特征签名。

    Args:
        text: STEP 文件全文
        shell_ref: CLOSED_SHELL 的实体引用号
        bbox_length/width/height: 已知的包围盒尺寸（如果有的话）

    Returns:
        GeometricFeatures 数据结构
    """
    features = GeometricFeatures()

    # 1. 获取面引用列表
    shell_pattern = rf"#{shell_ref}\s*=\s*CLOSED_SHELL\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*([^)]+)\)"
    shell_match = re.search(shell_pattern, text)
    if not shell_match:
        return features

    face_refs = [f.strip().lstrip("#") for f in shell_match.group(1).split(",") if f.strip().startswith("#")]
    features.face_count = len(face_refs)

    # 2. 解析每个面的曲面类型，同时提取圆柱半径
    surface_type_counts: dict[str, int] = {}
    for ref in face_refs:
        face_pattern = rf"#{ref}\s*=\s*ADVANCED_FACE\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\([^)]*\)\s*,\s*#(\d+)"
        face_match = re.search(face_pattern, text)
        if not face_match:
            continue

        surface_ref = face_match.group(1)
        surf_pattern = rf"#{surface_ref}\s*=\s*(\w+)\s*\("
        surf_match = re.search(surf_pattern, text)
        if not surf_match:
            continue

        stype = surf_match.group(1)
        surface_type_counts[stype] = surface_type_counts.get(stype, 0) + 1

        # 提取圆柱半径
        if stype == "CYLINDRICAL_SURFACE":
            radius = _extract_cylinder_radius(text, surface_ref)
            if radius and radius > 0.01:  # 过滤掉半径极小的噪声
                features.cylindrical_radii.append(round(radius, 2))

        # 提取环面半径（圆角）
        if stype == "TOROIDAL_SURFACE":
            pass  # 未来可用于圆角检测

    # 3. 映射曲面类型
    _SURFACE_MAP = {
        "PLANE": "平面",
        "CYLINDRICAL_SURFACE": "圆柱面",
        "CONICAL_SURFACE": "圆锥面",
        "SPHERICAL_SURFACE": "球面",
        "TOROIDAL_SURFACE": "环面",
        "B_SPLINE_SURFACE_WITH_KNOTS": "B样条曲面",
    }
    features.surface_types = [_SURFACE_MAP.get(k, k) for k in surface_type_counts.keys() if k in _SURFACE_MAP]

    features.has_cylinder = "CYLINDRICAL_SURFACE" in surface_type_counts
    features.has_sphere = "SPHERICAL_SURFACE" in surface_type_counts
    features.has_torus = "TOROIDAL_SURFACE" in surface_type_counts
    features.has_cone = "CONICAL_SURFACE" in surface_type_counts
    features.has_plane = "PLANE" in surface_type_counts

    # 4. 统计边线类型
    _count_edge_types(text, shell_ref, features)

    # 5. 包围盒比例分类
    features.bbox_length = bbox_length
    features.bbox_width = bbox_width
    features.bbox_height = bbox_height
    features.aspect_ratio_type = _classify_aspect_ratio(bbox_length, bbox_width, bbox_height)

    return features


def _extract_cylinder_radius(text: str, surface_ref: str) -> float | None:
    """从 CYLINDRICAL_SURFACE 实体提取半径。

    CYLINDRICAL_SURFACE('name', AXIS2_PLACEMENT_3D(...), radius)
    需要跳过 AXIS2_PLACEMENT_3D 的嵌套括号找到最后一个浮点数参数。
    """
    # 匹配 CYLINDRICAL_SURFACE 实体，找到半径（最后一个参数）
    pattern = rf"#{surface_ref}\s*=\s*CYLINDRICAL_SURFACE\s*\(\s*['\"][^'\"]*['\"]\s*,\s*#(\d+)\s*,\s*([\d.]+)"
    match = re.search(pattern, text)
    if match:
        try:
            return float(match.group(2))
        except ValueError:
            pass
    return None


def _count_edge_types(text: str, shell_ref: str, features: GeometricFeatures) -> None:
    """统计零件中直线/圆弧/样条边的数量。

    通过 EDGE_CURVE 引用的曲线实体类型来判断。
    """
    # 获取所有 EDGE_CURVE 的曲线引用
    # EDGE_CURVE('name', VERTEX_1, VERTEX_2, CURVE_REF, .T.)
    edge_curve_pattern = r"#(\d+)\s*=\s*EDGE_CURVE\s*\(\s*['\"][^'\"]*['\"]\s*,\s*#\d+\s*,\s*#\d+\s*,\s*#(\d+)"
    edge_curves = {}
    for m in re.finditer(edge_curve_pattern, text):
        edge_curves[m.group(1)] = m.group(2)

    # 获取零件的面引用，进而获取边引用
    shell_pattern = rf"#{shell_ref}\s*=\s*CLOSED_SHELL\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*([^)]+)\)"
    shell_match = re.search(shell_pattern, text)
    if not shell_match:
        return

    face_refs = [f.strip().lstrip("#") for f in shell_match.group(1).split(",") if f.strip().startswith("#")]

    # 收集零件的所有边引用
    edge_refs = set()
    for face_ref in face_refs:
        face_pattern = rf"#{face_ref}\s*=\s*ADVANCED_FACE\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*([^)]+)\)"
        face_match = re.search(face_pattern, text)
        if not face_match:
            continue
        bound_refs = [b.strip().lstrip("#") for b in face_match.group(1).split(",") if b.strip().startswith("#")]
        for bound_ref in bound_refs:
            bound_pattern = rf"#{bound_ref}\s*=\s*FACE_(?:OUTER_)?BOUND\s*\(\s*['\"][^'\"]*['\"]\s*,\s*#(\d+)"
            bound_match = re.search(bound_pattern, text)
            if not bound_match:
                continue
            el_ref = bound_match.group(1)
            el_pattern = rf"#{el_ref}\s*=\s*EDGE_LOOP\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*([^)]+)\)"
            el_match = re.search(el_pattern, text)
            if not el_match:
                continue
            oe_refs = [o.strip().lstrip("#") for o in el_match.group(1).split(",") if o.strip().startswith("#")]
            for oe_ref in oe_refs:
                oe_pattern = rf"#{oe_ref}\s*=\s*ORIENTED_EDGE\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\*\s*,\s*\*\s*,\s*#(\d+)"
                oe_match = re.search(oe_pattern, text)
                if oe_match:
                    edge_refs.add(oe_match.group(1))

    # 统计边的曲线类型
    for ec_ref in edge_refs:
        curve_ref = edge_curves.get(ec_ref)
        if not curve_ref:
            continue
        curve_pattern = rf"#{curve_ref}\s*=\s*(\w+)\s*\("
        curve_match = re.search(curve_pattern, text)
        if not curve_match:
            continue
        curve_type = curve_match.group(1)
        if curve_type == "LINE":
            features.edge_line_count += 1
        elif curve_type in ("CIRCLE", "ELLIPSE"):
            features.edge_circle_count += 1
        elif "SPLINE" in curve_type:
            features.edge_spline_count += 1


def _classify_aspect_ratio(length: float, width: float, height: float) -> str:
    """根据包围盒比例分类。"""
    if length == 0 or width == 0 or height == 0:
        return "unknown"

    dims = sorted([length, width, height])
    min_d, mid_d, max_d = dims[0], dims[1], dims[2]

    if max_d / min_d > 4:
        return "elongated"
    if max_d / min_d < 1.5 and mid_d / min_d < 1.5:
        return "compact"
    if max_d / min_d < 1.5:
        return "cubic"
    if min_d / max_d < 0.15:
        return "flat"
    return "normal"


def match_part(features: GeometricFeatures) -> BomMatchResult:
    """将几何特征签名与 BOM 库匹配，返回最佳匹配。

    匹配优先级：标准件 > 零件模板 > 仅材料推断
    """
    result = BomMatchResult()

    # 1. 尝试匹配标准件
    best_std = _match_against_list(features, get_standard_parts())
    if best_std and best_std[1] >= 0.6:
        item = best_std[0]
        result.match_type = "standard_part"
        result.match_id = item["id"]
        result.name_cn = item["name_cn"]
        result.name_en = item["name_en"]
        result.confidence = best_std[1]
        result.visual_description = item["visual"]
        mat = get_material(item.get("material", ""))
        if mat:
            result.material_id = item["material"]
            result.material_name = mat["name_cn"]
            result.color_hex = mat["color_hex"]
            result.color_name = mat["color_name"]
            result.finish = mat["finish"]
        return result

    # 2. 尝试匹配零件模板
    best_tpl = _match_against_list(features, get_part_templates())
    if best_tpl and best_tpl[1] >= 0.5:
        item = best_tpl[0]
        result.match_type = "template"
        result.match_id = item["id"]
        result.name_cn = item["name_cn"]
        result.name_en = item["name_en"]
        result.confidence = best_tpl[1]
        result.visual_description = item["visual"]
        mat = get_material(item.get("material", ""))
        if mat:
            result.material_id = item["material"]
            result.material_name = mat["name_cn"]
            result.color_hex = mat["color_hex"]
            result.color_name = mat["color_name"]
            result.finish = mat["finish"]
        return result

    # 3. 仅根据几何特征推断材料
    result.match_type = "material_only"
    result.confidence = 0.3
    mat_id = _infer_material(features)
    result.material_id = mat_id  # 始终保留推断值
    mat = get_material(mat_id)
    if mat:
        result.material_name = mat["name_cn"]
        result.color_hex = mat["color_hex"]
        result.color_name = mat["color_name"]
        result.finish = mat["finish"]

    # 4. 生成圆柱特征描述
    result.cylindrical_features = _describe_cylindrical_features(features)
    result.edge_profile = _describe_edge_profile(features)

    return result


def _match_against_list(
    features: GeometricFeatures,
    candidates: list[dict],
) -> tuple[dict, float] | None:
    """将特征与候选列表匹配，返回 (最佳匹配, 置信度)。"""
    best_item = None
    best_score = 0.0

    for item in candidates:
        sig = item.get("geometry_signature", {})
        score = _compute_match_score(features, sig)
        if score > best_score:
            best_score = score
            best_item = item

    return (best_item, best_score) if best_item else None


def _compute_match_score(features: GeometricFeatures, signature: dict) -> float:
    """计算几何特征与签名的匹配分数。"""
    score = 0.0
    total_weight = 0.0

    # 面数范围匹配（权重 0.2）
    fc_range = signature.get("face_count_range")
    if fc_range:
        total_weight += 0.2
        if fc_range[0] <= features.face_count <= fc_range[1]:
            score += 0.2
        elif features.face_count < fc_range[0]:
            # 面数偏少，部分得分
            ratio = features.face_count / fc_range[0]
            score += 0.2 * ratio * 0.5

    # 曲面类型匹配（权重各 0.1）
    for stype, attr in [
        ("cylinder", "has_cylinder"),
        ("sphere", "has_sphere"),
        ("torus", "has_torus"),
        ("cone", "has_cone"),
        ("plane", "has_plane"),
    ]:
        key = f"has_{stype}"
        if key in signature:
            total_weight += 0.1
            expected = signature[key]
            actual = getattr(features, attr, False)
            if expected == actual:
                score += 0.1

    # 比例匹配（权重 0.2）
    expected_ratio = signature.get("aspect_ratio")
    if expected_ratio:
        total_weight += 0.2
        if expected_ratio == features.aspect_ratio_type:
            score += 0.2
        elif _ratio_compatible(expected_ratio, features.aspect_ratio_type):
            score += 0.1

    return score / total_weight if total_weight > 0 else 0.0


def _ratio_compatible(expected: str, actual: str) -> bool:
    """检查两种比例类型是否兼容。"""
    compatible_groups = [
        {"elongated", "normal"},
        {"flat", "flat-circular"},
        {"compact", "cubic"},
    ]
    for group in compatible_groups:
        if expected in group and actual in group:
            return True
    return False


def _infer_material(features: GeometricFeatures) -> str:
    """根据几何特征推断最可能的材料。"""
    # 有大量曲面 → 可能是铸件或塑料件
    spline_count = features.surface_types.count("B样条曲面")
    if spline_count > 5:
        return "abs_plastic"

    # 有球面或环面 → 可能是轴承/紧固件 → 钢
    if features.has_sphere or features.has_torus:
        return "steel_q235"

    # 面数少、有圆柱 → 可能是简单机加件 → 铝
    if features.face_count <= 20 and features.has_cylinder:
        return "aluminum_6061"

    # 默认碳钢
    return "steel_q235"


def _describe_cylindrical_features(features: GeometricFeatures) -> str:
    """将圆柱半径列表转为自然语言描述。"""
    radii = features.cylindrical_radii
    if not radii:
        return ""

    # 按大小分组
    small = [r for r in radii if r < 3]      # Ø<6mm 小孔
    medium = [r for r in radii if 3 <= r < 8] # Ø6-16mm 中孔
    large = [r for r in radii if r >= 8]      # Ø≥16mm 大孔

    parts = []
    if small:
        avg = sum(small) / len(small)
        parts.append(f"{len(small)}x small holes (Ø{avg*2:.0f}mm)")
    if medium:
        avg = sum(medium) / len(medium)
        parts.append(f"{len(medium)}x medium holes (Ø{avg*2:.0f}mm)")
    if large:
        avg = sum(large) / len(large)
        parts.append(f"{len(large)}x large bores (Ø{avg*2:.0f}mm)")

    return ", ".join(parts) if parts else ""


def _describe_edge_profile(features: GeometricFeatures) -> str:
    """描述边线类型分布。"""
    total = features.edge_line_count + features.edge_circle_count + features.edge_spline_count
    if total == 0:
        return ""

    straight_pct = features.edge_line_count / total
    circle_pct = features.edge_circle_count / total

    if straight_pct > 0.8:
        return "mostly straight sharp edges, prismatic CNC-machined appearance"
    if circle_pct > 0.4:
        return "many rounded curved edges, cast or molded appearance"
    if features.edge_spline_count > total * 0.3:
        return "smooth organic curved profiles, sculpted surface"
    return "mix of straight and curved edges"
