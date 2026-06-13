"""图片 Prompt 构造器 — 从零件元数据生成豆包 Seedream 图片生成 Prompt。

设计原则:
1. 用自然语言描述形状，不用 CAD 术语
2. 颜色直接用 hex 值
3. 给比例关系而非绝对尺寸
4. 固定风格前缀保证一致性
5. 每步骤差异化：视角 + 装配进度
"""

from __future__ import annotations

# 形状自然语言映射（替代 CAD 术语）
_SHAPE_DESCRIPTIONS = {
    "cylinder": "a cylindrical rod or tube shape",
    "sphere": "a spherical ball shape",
    "threaded": "a bolt or screw with a hexagonal head and threaded shaft",
    "plate": "a thin flat plate or sheet metal part",
    "box": "a rectangular block or box-shaped bracket",
}

# 视角 Prompt 映射
_VIEW_DESCRIPTIONS = {
    "正视": "front view, looking straight at the front face",
    "侧视": "right side view, looking from the right",
    "俯视": "top-down bird's eye view, looking from above",
    "右后视": "rear-right isometric view, 3/4 angle from behind-right",
    "左前视": "front-left isometric view, 3/4 angle from front-left",
    "右侧视": "right side perspective view",
    "俯侧视": "elevated side view, looking down from the upper-right",
    "后视": "rear view, looking from behind",
    "前视": "front perspective view, slightly elevated angle",
    "右后俯视": "high rear-right isometric view, bird's eye from behind-right",
}

# 统一风格前缀（保证所有图片风格一致）
_STYLE_PREFIX = (
    "A photorealistic technical engineering illustration of a mechanical part, "
    "clean white background, professional studio lighting, "
    "CAD-style rendering with visible edges and subtle shadows, "
    "industrial product photography style"
)

# 装配上下文模板
_ASSEMBLY_CONTEXT = {
    "first": "This is the first part being placed, shown alone on a white surface.",
    "middle": "This part is being installed onto existing assembled parts shown as "
              "transparent gray wireframe outlines in the background.",
    "last": "This is the final part being installed, the nearly-complete assembly "
            "shown as transparent gray wireframe in the background.",
}


def _detect_shape_key(surface_types: list[str], face_count: int) -> str:
    """从曲面类型推断形状 key（与 image_service 逻辑一致）。"""
    has_cylinder = "圆柱面" in surface_types
    has_sphere = "球面" in surface_types
    has_torus = "环面" in surface_types
    has_cone = "圆锥面" in surface_types

    if has_sphere and has_torus:
        return "sphere"
    if has_torus and has_cone:
        return "threaded"
    if has_cylinder and face_count <= 10:
        return "cylinder"
    if face_count <= 6 and not has_cylinder:
        return "plate"
    return "box"


def _assembly_phase(sequence: int, total_steps: int) -> str:
    """判断装配阶段。"""
    if sequence <= 1:
        return "first"
    if sequence >= total_steps:
        return "last"
    return "middle"


def build_step_image_prompt(
    part_name: str,
    face_count: int,
    surface_types: list[str],
    color_hex: str | None,
    length: float,
    width: float,
    height: float,
    sequence: int,
    total_steps: int,
    step_title: str,
    view_label: str = "左前视",
    # BOM 匹配增强参数（可选）
    bom_visual: str = "",
    bom_material: str = "",
    bom_finish: str = "",
    cylindrical_features: str = "",
    edge_profile: str = "",
) -> str:
    """为一个装配步骤构造图片生成 Prompt。

    Args:
        part_name: 零件分类名（如"带孔支架"）
        face_count: 面数
        surface_types: 曲面类型列表
        color_hex: hex 颜色（如 "#b11919"），None 表示用默认
        length/width/height: 尺寸（mm）
        sequence: 步骤序号
        total_steps: 总步骤数
        step_title: 步骤标题
        view_label: 视角标签

    Returns:
        完整的 Prompt 字符串
    """
    parts = [_STYLE_PREFIX]

    # 1. 形状描述（优先使用 BOM 匹配的精确描述）
    if bom_visual:
        parts.append(f"The part is {bom_visual}.")
    else:
        shape_key = _detect_shape_key(surface_types, face_count)
        shape_desc = _SHAPE_DESCRIPTIONS.get(shape_key, "a mechanical part")
        parts.append(f"The part is {shape_desc}.")

    # 2. 尺寸比例描述（不给绝对值，给比例关系）
    if length > 0 and width > 0 and height > 0:
        max_dim = max(length, width, height)
        l_ratio = length / max_dim
        w_ratio = width / max_dim
        h_ratio = height / max_dim

        if l_ratio > 2.5:
            parts.append("The part is elongated and narrow, much longer than it is wide.")
        elif h_ratio > 2.0:
            parts.append("The part is tall and vertical, much taller than it is wide.")
        elif w_ratio < 0.3:
            parts.append("The part is very thin and flat.")
        elif abs(l_ratio - 1.0) < 0.2 and abs(w_ratio - 1.0) < 0.2:
            parts.append("The part is roughly cubic, similar size in all dimensions.")
        else:
            parts.append(
                f"The part has proportions roughly {length/width:.1f}:1 "
                f"length to width, {height/width:.1f}:1 height to width."
            )

    # 3. 曲面特征描述（优先使用 BOM 匹配的精确特征）
    if cylindrical_features:
        parts.append(f"Cylindrical features: {cylindrical_features}.")
    else:
        feature_hints = []
        if "圆柱面" in surface_types:
            feature_hints.append("cylindrical features such as holes or rounded edges")
        if "球面" in surface_types:
            feature_hints.append("spherical curved surfaces")
        if "环面" in surface_types:
            feature_hints.append("toroidal ring-shaped features")
        if "圆锥面" in surface_types:
            feature_hints.append("conical tapered surfaces")
        if "B样条曲面" in surface_types:
            feature_hints.append("smooth freeform curved surfaces")
        if "平面" in surface_types:
            feature_hints.append("flat planar faces")

        if feature_hints:
            parts.append(f"Notable geometric features include: {', '.join(feature_hints)}.")

    # 3.5 边线轮廓描述
    if edge_profile:
        parts.append(f"Edge profile: {edge_profile}.")

    # 4. 颜色和材质描述（优先使用 BOM 匹配的材质信息）
    if bom_material and bom_finish:
        color_str = _normalize_color(color_hex)
        mat_en = _translate_material(bom_material)
        finish_en = _translate_finish(bom_finish)
        if color_str and color_str != "#ffffff":
            color_name = _hex_to_color_name(color_hex)
            parts.append(f"Material: {mat_en}. Surface finish: {finish_en}. Color: {color_name}.")
        else:
            parts.append(f"Material: {mat_en}. Surface finish: {finish_en}.")
    else:
        color_str = _normalize_color(color_hex)
        if color_str and color_str != "#ffffff":
            color_name = _hex_to_color_name(color_hex)
            parts.append(f"The part color is {color_name} ({color_str}).")
        else:
            parts.append("The part is metallic silver-gray color.")

    # 5. 视角
    view_desc = _VIEW_DESCRIPTIONS.get(view_label, f"isometric view from {view_label}")
    parts.append(f"Camera angle: {view_desc}.")

    # 6. 装配上下文
    phase = _assembly_phase(sequence, total_steps)
    assembly_desc = _ASSEMBLY_CONTEXT.get(phase, "")
    if assembly_desc:
        parts.append(assembly_desc)

    # 7. 尺寸标注
    if length > 0 and width > 0 and height > 0:
        parts.append(
            f"Visible dimension annotations showing "
            f"{length:.1f} x {width:.1f} x {height:.1f} mm."
        )

    # 8. 步骤信息（作为水印而非 Prompt 内容）
    parts.append(f"Step {sequence} of {total_steps}: {step_title}.")

    return " ".join(parts)


def build_thumbnail_prompt(
    part_name: str,
    surface_types: list[str],
    color_hex: str | None,
    face_count: int,
) -> str:
    """为零件缩略图构造简短 Prompt（用于 ProductGraph 节点预览）。"""
    shape_key = _detect_shape_key(surface_types, face_count)
    shape_desc = _SHAPE_DESCRIPTIONS.get(shape_key, "a mechanical part")

    prompt = (
        f"{_STYLE_PREFIX} "
        f"The part is {shape_desc}. "
    )

    if color_hex and _normalize_color(color_hex) != "#ffffff":
        color_name = _hex_to_color_name(color_hex)
        prompt += f"Color: {color_name}. "

    prompt += "Isometric view, centered, no annotations."
    return prompt


# 中文材质名 → 英文 Prompt 用语
_MATERIAL_MAP = {
    "铝合金": "aluminum alloy", "铝": "aluminum", "钢": "steel",
    "不锈钢": "stainless steel", "铜": "copper", "黄铜": "brass",
    "塑料": "plastic", "尼龙": "nylon", "碳纤维": "carbon fiber",
    "玻璃": "glass", "橡胶": "rubber", "钛合金": "titanium alloy",
    "铸铁": "cast iron", "锌合金": "zinc alloy",
}
_FINISH_MAP = {
    "阳极氧化": "anodized", "喷砂": "sandblasted", "电镀": "electroplated",
    "抛光": "polished", "拉丝": "brushed", "喷涂": "powder coated",
    "氧化": "oxidized", "镀铬": "chrome plated", "镀锌": "galvanized",
    "发黑": "blackened", "钝化": "passivated",
}


def _translate_material(cn: str) -> str:
    """中文材质名翻译为英文。"""
    return _MATERIAL_MAP.get(cn, cn)


def _translate_finish(cn: str) -> str:
    """中文表面处理翻译为英文。"""
    return _FINISH_MAP.get(cn, cn)


def _normalize_color(color_value) -> str | None:
    """将颜色值统一转为 hex 字符串。

    支持: "#rrggbb", (R,G,B) 0.0~1.0, (R,G,B) 0~255, None
    """
    if not color_value:
        return None
    if isinstance(color_value, str):
        return color_value
    if isinstance(color_value, (tuple, list)) and len(color_value) >= 3:
        r, g, b = color_value[0], color_value[1], color_value[2]
        if isinstance(r, float) and r <= 1.0:
            r, g, b = int(r * 255), int(g * 255), int(b * 255)
        return f"#{int(r):02x}{int(g):02x}{int(b):02x}"
    return None


def _hex_to_color_name(color_value) -> str:
    """将颜色值映射到自然语言名称。

    支持: "#rrggbb" 字符串, (R,G,B) 元组 (0.0~1.0), (R,G,B) 元组 (0~255)
    """
    # 统一转为 (R, G, B) 0~255
    if isinstance(color_value, tuple) and len(color_value) >= 3:
        r, g, b = color_value[0], color_value[1], color_value[2]
        if isinstance(r, float) and r <= 1.0:
            r, g, b = int(r * 255), int(g * 255), int(b * 255)
    elif isinstance(color_value, str):
        hex_color = color_value.lstrip("#").lower()
        try:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        except (ValueError, IndexError):
            return "gray"
    else:
        return "gray"

    # 简单的 RGB → 颜色名映射
    if r > 200 and g < 80 and b < 80:
        return "red"
    if r < 80 and g > 150 and b < 80:
        return "green"
    if r < 80 and g < 80 and b > 200:
        return "blue"
    if r > 200 and g > 200 and b < 80:
        return "yellow"
    if r > 200 and g > 130 and b < 80:
        return "orange"
    if r > 150 and g < 80 and b > 150:
        return "purple"
    if r > 200 and g > 200 and b > 200:
        return "white"
    if r < 60 and g < 60 and b < 60:
        return "black"
    if r > 100 and g > 100 and b > 100 and abs(r - g) < 30 and abs(g - b) < 30:
        return "gray"
    if r > 150 and g < 100 and b < 100:
        return "dark red"
    if r > 100 and g > 150 and b > 100:
        return "light green"
    return f"custom color RGB({r},{g},{b})"
