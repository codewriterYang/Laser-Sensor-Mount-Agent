"""参考图渲染器 — 从 STEP 拓扑链提取每个零件的真实边线，生成精确线框参考图。

拓扑链:
  MANIFOLD_SOLID_BREP → CLOSED_SHELL → ADVANCED_FACE → FACE_OUTER_BOUND/BOUND
  → EDGE_LOOP → ORIENTED_EDGE → EDGE_CURVE → VERTEX_POINT → CARTESIAN_POINT

每个零件独立渲染，不同步骤用不同零件的参考图。
"""

from __future__ import annotations

import math
import re
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from ..logger import logger

REF_SIZE = 1024


def _project_iso(x: float, y: float, z: float, rx_deg: float = 25, ry_deg: float = -30) -> tuple[float, float]:
    rx = math.radians(rx_deg)
    ry = math.radians(ry_deg)
    x1 = x * math.cos(ry) - z * math.sin(ry)
    z1 = x * math.sin(ry) + z * math.cos(ry)
    y1 = y * math.cos(rx) - z1 * math.sin(rx)
    z2 = y * math.sin(rx) + z1 * math.cos(rx)
    return x1, y1 + z2 * 0.3


def _parse_step_topology(text: str) -> dict:
    """解析 STEP 文件的完整拓扑结构。

    返回:
    {
        "cartesian_points": {ref: (x,y,z)},
        "vertex_points": {vp_ref: cp_ref},
        "edge_curves": {ec_ref: (vp1_ref, vp2_ref)},
        "oriented_edges": {oe_ref: ec_ref},
        "edge_loops": {el_ref: [oe_ref, ...]},
        "face_bounds": {fb_ref: el_ref},
        "advanced_faces": {af_ref: [fb_ref, ...]},
        "closed_shells": {cs_ref: [af_ref, ...]},
        "manifold_solids": {msb_ref: cs_ref},
    }
    """
    data = {}

    # 1. CARTESIAN_POINT
    cp_map = {}
    for m in re.finditer(
        r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*([^)]+)\s*\)",
        text,
    ):
        try:
            coords = [float(v.strip()) for v in m.group(2).split(",")]
            if len(coords) >= 3:
                cp_map[m.group(1)] = (coords[0], coords[1], coords[2])
        except ValueError:
            continue
    data["cartesian_points"] = cp_map

    # 2. VERTEX_POINT → CARTESIAN_POINT ref
    vp_map = {}
    for m in re.finditer(r"#(\d+)\s*=\s*VERTEX_POINT\s*\(\s*['\"][^'\"]*['\"]\s*,\s*#(\d+)", text):
        vp_map[m.group(1)] = m.group(2)
    data["vertex_points"] = vp_map

    # 3. EDGE_CURVE → (VP1, VP2)
    ec_map = {}
    for m in re.finditer(
        r"#(\d+)\s*=\s*EDGE_CURVE\s*\(\s*['\"][^'\"]*['\"]\s*,\s*#(\d+)\s*,\s*#(\d+)",
        text,
    ):
        ec_map[m.group(1)] = (m.group(2), m.group(3))
    data["edge_curves"] = ec_map

    # 4. ORIENTED_EDGE → EDGE_CURVE ref
    oe_map = {}
    for m in re.finditer(
        r"#(\d+)\s*=\s*ORIENTED_EDGE\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\*\s*,\s*\*\s*,\s*#(\d+)",
        text,
    ):
        oe_map[m.group(1)] = m.group(2)
    data["oriented_edges"] = oe_map

    # 5. EDGE_LOOP → [ORIENTED_EDGE refs]
    el_map = {}
    for m in re.finditer(
        r"#(\d+)\s*=\s*EDGE_LOOP\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*([^)]+)\)",
        text,
    ):
        oe_refs = [r.strip().lstrip("#") for r in m.group(2).split(",") if r.strip().startswith("#")]
        el_map[m.group(1)] = oe_refs
    data["edge_loops"] = el_map

    # 6. FACE_OUTER_BOUND / FACE_BOUND → EDGE_LOOP ref
    fb_map = {}
    for m in re.finditer(
        r"#(\d+)\s*=\s*FACE_(?:OUTER_)?BOUND\s*\(\s*['\"][^'\"]*['\"]\s*,\s*#(\d+)",
        text,
    ):
        fb_map[m.group(1)] = m.group(2)
    data["face_bounds"] = fb_map

    # 7. ADVANCED_FACE → [FACE_BOUND refs]
    af_map = {}
    for m in re.finditer(
        r"#(\d+)\s*=\s*ADVANCED_FACE\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*([^)]+)\)",
        text,
    ):
        fb_refs = [r.strip().lstrip("#") for r in m.group(2).split(",") if r.strip().startswith("#")]
        af_map[m.group(1)] = fb_refs
    data["advanced_faces"] = af_map

    # 8. CLOSED_SHELL → [ADVANCED_FACE refs]
    cs_map = {}
    for m in re.finditer(
        r"#(\d+)\s*=\s*CLOSED_SHELL\s*\(\s*['\"][^'\"]*['\"]\s*,\s*\(\s*([^)]+)\)",
        text,
    ):
        af_refs = [r.strip().lstrip("#") for r in m.group(2).split(",") if r.strip().startswith("#")]
        cs_map[m.group(1)] = af_refs
    data["closed_shells"] = cs_map

    # 9. MANIFOLD_SOLID_BREP → CLOSED_SHELL ref
    msb_map = {}
    for m in re.finditer(
        r"#(\d+)\s*=\s*MANIFOLD_SOLID_BREP\s*\(\s*['\"][^'\"]*['\"]\s*,\s*#(\d+)",
        text,
    ):
        msb_map[m.group(1)] = m.group(2)
    data["manifold_solids"] = msb_map

    return data


def _extract_part_edges(
    topology: dict,
    msb_ref: str,
    max_edges: int = 3000,
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """提取单个零件的所有边线坐标。

    从 MANIFOLD_SOLID_BREP 追溯到 EDGE_CURVE 端点。
    """
    cp_map = topology["cartesian_points"]
    vp_map = topology["vertex_points"]
    ec_map = topology["edge_curves"]
    oe_map = topology["oriented_edges"]
    el_map = topology["edge_loops"]
    fb_map = topology["face_bounds"]
    af_map = topology["advanced_faces"]
    cs_map = topology["closed_shells"]
    msb_map = topology["manifold_solids"]

    # MSB → CLOSED_SHELL
    cs_ref = msb_map.get(msb_ref)
    if not cs_ref:
        return []

    # CLOSED_SHELL → ADVANCED_FACE refs
    face_refs = cs_map.get(cs_ref, [])

    # 收集所有 EDGE_CURVE 引用
    ec_refs = set()
    for af_ref in face_refs:
        # ADVANCED_FACE → FACE_BOUND refs
        bound_refs = af_map.get(af_ref, [])
        for fb_ref in bound_refs:
            # FACE_BOUND → EDGE_LOOP ref
            el_ref = fb_map.get(fb_ref)
            if not el_ref:
                continue
            # EDGE_LOOP → ORIENTED_EDGE refs
            oe_refs = el_map.get(el_ref, [])
            for oe_ref in oe_refs:
                # ORIENTED_EDGE → EDGE_CURVE ref
                ec_ref = oe_map.get(oe_ref)
                if ec_ref:
                    ec_refs.add(ec_ref)

    # 转换 EDGE_CURVE → 3D 坐标
    edges = []
    for ec_ref in ec_refs:
        if len(edges) >= max_edges:
            break
        vp1_ref, vp2_ref = ec_map.get(ec_ref, (None, None))
        if not vp1_ref or not vp2_ref:
            continue

        cp1_ref = vp_map.get(vp1_ref)
        cp2_ref = vp_map.get(vp2_ref)
        if not cp1_ref or not cp2_ref:
            continue

        p1 = cp_map.get(cp1_ref)
        p2 = cp_map.get(cp2_ref)
        if p1 and p2:
            edges.append((p1, p2))

    return edges


def _compute_global_scale_params(
    *edge_groups: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
    rx_deg: float = 25,
    ry_deg: float = -30,
) -> dict | None:
    """从多组边线中计算全局统一的缩放参数。

    返回 {"scale", "cx", "cy", "mid_x", "mid_y", "z_min", "z_range"} 或 None（无边线时）。
    """
    all_x, all_y, all_z = [], [], []
    sin_ry = math.sin(math.radians(ry_deg))
    cos_ry = math.cos(math.radians(ry_deg))

    for edges in edge_groups:
        for p1, p2 in edges:
            q1 = _project_iso(p1[0], p1[1], p1[2], rx_deg, ry_deg)
            q2 = _project_iso(p2[0], p2[1], p2[2], rx_deg, ry_deg)
            all_x.extend([q1[0], q2[0]])
            all_y.extend([q1[1], q2[1]])
            z1 = p1[0] * sin_ry + p1[2] * cos_ry
            z2 = p2[0] * sin_ry + p2[2] * cos_ry
            all_z.extend([z1, z2])

    if not all_x:
        return None

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    range_x = max_x - min_x or 1
    range_y = max_y - min_y or 1
    margin = int(REF_SIZE * 0.12)
    draw_area = REF_SIZE - 2 * margin
    scale = min(draw_area / range_x, draw_area / range_y)

    return {
        "scale": scale,
        "cx": REF_SIZE / 2,
        "cy": REF_SIZE / 2,
        "mid_x": (min_x + max_x) / 2,
        "mid_y": (min_y + max_y) / 2,
        "z_min": min(all_z),
        "z_range": (max(all_z) - min(all_z)) or 1,
    }


def _extract_face_loops(
    edges: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
    rx_deg: float = 25,
    ry_deg: float = -30,
    max_loops: int = 20,
) -> list[list[tuple[float, float]]]:
    """从边线中提取闭合面环（用于面填充）。

    构建端点邻接图，找到长度 3-8 的闭合环，投影到 2D。
    """
    if not edges:
        return []

    # 构建端点邻接图（用坐标元组作为 key）
    from collections import defaultdict
    adj = defaultdict(list)
    for p1, p2 in edges:
        k1 = (round(p1[0], 4), round(p1[1], 4), round(p1[2], 4))
        k2 = (round(p2[0], 4), round(p2[1], 4), round(p2[2], 4))
        adj[k1].append(k2)
        adj[k2].append(k1)

    # DFS 找闭合环（长度 3-8）
    loops = []
    visited_edges = set()

    for start in list(adj.keys())[:50]:  # 限制起始点数量
        stack = [(start, [start])]
        while stack and len(loops) < max_loops:
            node, path = stack.pop()
            if len(path) > 8:
                continue
            for neighbor in adj[node]:
                edge_key = (min(str(node), str(neighbor)), max(str(node), str(neighbor)))
                if edge_key in visited_edges:
                    continue
                if neighbor == start and len(path) >= 3:
                    # 找到闭合环
                    loop_2d = []
                    for pt in path:
                        q = _project_iso(pt[0], pt[1], pt[2], rx_deg, ry_deg)
                        loop_2d.append(q)
                    loops.append(loop_2d)
                    visited_edges.add(edge_key)
                    break
                if neighbor not in path:
                    stack.append((neighbor, path + [neighbor]))

    return loops


def _render_edges_to_image(
    edges: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
    rx_deg: float = 25,
    ry_deg: float = -30,
    line_color: str = "#808080",
    line_width: int = 2,
    bg_color: str = "white",
    scale_params: dict | None = None,
    fill_faces: bool = False,
) -> bytes:
    """将 3D 边线列表渲染为 1024×1024 PNG（带深度感知线宽）。

    fill_faces: 是否对闭合面环填充半透明颜色（增加体积感）。
    """
    if not edges:
        img = Image.new("RGB", (REF_SIZE, REF_SIZE), bg_color)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # 投影 + 记录深度
    projected = []
    sin_ry = math.sin(math.radians(ry_deg))
    cos_ry = math.cos(math.radians(ry_deg))
    for p1, p2 in edges:
        q1 = _project_iso(p1[0], p1[1], p1[2], rx_deg, ry_deg)
        q2 = _project_iso(p2[0], p2[1], p2[2], rx_deg, ry_deg)
        z1 = p1[0] * sin_ry + p1[2] * cos_ry
        z2 = p2[0] * sin_ry + p2[2] * cos_ry
        avg_z = (z1 + z2) / 2
        projected.append((q1, q2, avg_z))

    # 使用预计算或自行计算缩放参数
    if scale_params is not None:
        scale = scale_params["scale"]
        cx = scale_params["cx"]
        cy = scale_params["cy"]
        mid_x = scale_params["mid_x"]
        mid_y = scale_params["mid_y"]
        z_min = scale_params["z_min"]
        z_range = scale_params["z_range"]
    else:
        all_x = [q1[0] for q1, _, _ in projected] + [q2[0] for _, q2, _ in projected]
        all_y = [q1[1] for q1, _, _ in projected] + [q2[1] for _, q2, _ in projected]
        all_z = [z for _, _, z in projected]
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        range_x = max_x - min_x or 1
        range_y = max_y - min_y or 1
        margin = int(REF_SIZE * 0.12)
        draw_area = REF_SIZE - 2 * margin
        scale = min(draw_area / range_x, draw_area / range_y)
        cx, cy = REF_SIZE / 2, REF_SIZE / 2
        mid_x, mid_y = (min_x + max_x) / 2, (min_y + max_y) / 2
        z_min = min(all_z)
        z_range = (max(all_z) - min(all_z)) or 1

    # 绘制
    img = Image.new("RGB", (REF_SIZE, REF_SIZE), bg_color)
    draw = ImageDraw.Draw(img)

    # 按深度排序，远的先画
    projected.sort(key=lambda e: e[2])

    for q1, q2, z in projected:
        x1 = cx + (q1[0] - mid_x) * scale
        y1 = cy + (q1[1] - mid_y) * scale
        x2 = cx + (q2[0] - mid_x) * scale
        y2 = cy + (q2[1] - mid_y) * scale

        depth_ratio = (z - z_min) / z_range
        lw = max(1, int(1 + depth_ratio * 2))
        # 将 line_color 与深度亮度混合
        base_hex = line_color.lstrip("#")
        br = int(base_hex[0:2], 16)
        bg = int(base_hex[2:4], 16)
        bb = int(base_hex[4:6], 16)
        brightness = 0.5 + depth_ratio * 0.5  # 0.5~1.0
        r = min(255, int(br * brightness))
        g = min(255, int(bg * brightness))
        b = min(255, int(bb * brightness))
        color = f"#{r:02x}{g:02x}{b:02x}"

        draw.line([(x1, y1), (x2, y2)], fill=color, width=lw)

    # 面填充：对闭合环填充半透明颜色
    if fill_faces:
        loops = _extract_face_loops(edges, rx_deg, ry_deg)
        base_hex = line_color.lstrip("#")
        br = int(base_hex[0:2], 16)
        bg = int(base_hex[2:4], 16)
        bb = int(base_hex[4:6], 16)
        fill_color = f"#{min(255, br+40):02x}{min(255, bg+40):02x}{min(255, bb+40):02x}"
        for loop in loops:
            if len(loop) >= 3:
                projected_pts = []
                for pt in loop:
                    x = cx + (pt[0] - mid_x) * scale
                    y = cy + (pt[1] - mid_y) * scale
                    projected_pts.append((x, y))
                draw.polygon(projected_pts, fill=fill_color, outline=None)

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _render_multi_view(
    edges: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
) -> bytes:
    """渲染多视角参考图（正视 + 侧视 + 俯视 + 等轴测，2×2 网格）。

    多视角消除单视角歧义，让 AI 更准确理解 3D 形状。
    """
    if not edges:
        img = Image.new("RGB", (REF_SIZE, REF_SIZE), "white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # 4 个视角
    views = [
        ("Front", 0, 0),       # 正视
        ("Right", 0, -90),     # 右视
        ("Top", 90, 0),        # 俯视
        ("Iso", 25, -30),      # 等轴测
    ]

    cell_size = REF_SIZE // 2
    canvas = Image.new("RGB", (REF_SIZE, REF_SIZE), "white")
    draw = ImageDraw.Draw(canvas)

    for idx, (label, rx, ry) in enumerate(views):
        row, col = idx // 2, idx % 2
        # 渲染单视角
        view_img_bytes = _render_edges_to_image(edges, rx_deg=rx, ry_deg=ry)
        view_img = Image.open(BytesIO(view_img_bytes)).resize(
            (cell_size, cell_size), Image.LANCZOS,
        )
        canvas.paste(view_img, (col * cell_size, row * cell_size))

        # 视角标签
        draw.rectangle(
            [col * cell_size, row * cell_size, col * cell_size + 80, row * cell_size + 24],
            fill="#334155",
        )
        draw.text(
            (col * cell_size + 8, row * cell_size + 4),
            label, fill="white",
        )

    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


# === 公开 API ===

# 零件索引 → MANIFOLD_SOLID_BREP ref 的缓存
_msb_cache: dict[str, dict[int, str]] = {}


def get_part_msb_refs(text: str) -> dict[int, str]:
    """获取零件索引 → MSB ref 的映射（按 MSB 出现顺序排列）。

    返回 {0: "16716", 1: "44954", ...}
    """
    import hashlib
    # 用文件长度 + 首尾各 5000 字符做指纹，避免 hash() 随机化和截断碰撞
    fingerprint = f"{len(text)}:{text[:5000]}:{text[-5000:]}"
    text_hash = hashlib.md5(fingerprint.encode()).hexdigest()
    if text_hash in _msb_cache:
        return _msb_cache[text_hash]

    topology = _parse_step_topology(text)
    msb_map = topology["manifold_solids"]
    result = {i: ref for i, ref in enumerate(msb_map.keys())}
    _msb_cache[text_hash] = result
    return result


def render_part_wireframe(
    text: str,
    part_index: int,
    rx_deg: float = 25,
    ry_deg: float = -30,
    color: str | None = None,
) -> bytes:
    """为指定零件生成精确线框参考图。

    Args:
        text: STEP 文件全文
        part_index: 零件索引（0-based，对应 MANIFOLD_SOLID_BREP 顺序）
        rx_deg: X 轴旋转角度
        ry_deg: Y 轴旋转角度
        color: 边线颜色（hex 字符串），None 时使用默认灰色

    Returns:
        PNG 图片字节数据
    """
    topology = _parse_step_topology(text)
    msb_map = topology["manifold_solids"]
    msb_refs = list(msb_map.keys())

    if part_index >= len(msb_refs):
        logger.warning(f"零件索引 {part_index} 超出范围（共 {len(msb_refs)} 个零件）")
        return _render_edges_to_image([], rx_deg, ry_deg)

    msb_ref = msb_refs[part_index]
    edges = _extract_part_edges(topology, msb_ref)

    logger.info(f"零件 {part_index} (MSB #{msb_ref}): 提取到 {len(edges)} 条边线")
    line_color = color if color else "#808080"
    return _render_edges_to_image(edges, rx_deg, ry_deg, line_color=line_color)


def render_assembly_wireframe(
    text: str,
    rx_deg: float = 25,
    ry_deg: float = -30,
) -> bytes:
    """为整个装配体生成线框参考图。"""
    topology = _parse_step_topology(text)
    all_edges = []

    for msb_ref in topology["manifold_solids"]:
        edges = _extract_part_edges(topology, msb_ref, max_edges=500)
        all_edges.extend(edges)

    logger.info(f"装配体: 提取到 {len(all_edges)} 条边线")
    return _render_edges_to_image(all_edges, rx_deg, ry_deg)


def get_part_bounding_box(
    text: str,
    part_index: int,
) -> tuple[float, float, float]:
    """计算单个零件的精确包围盒尺寸（mm）。

    遍历零件所有顶点坐标，计算 X/Y/Z 方向的范围。
    比 step_parser 中按面数比例估算的方法更准确。

    Args:
        text: STEP 文件全文
        part_index: 零件索引（0-based）

    Returns:
        (length, width, height) 单位 mm，失败返回 (0, 0, 0)
    """
    topology = _parse_step_topology(text)
    msb_map = topology["manifold_solids"]
    msb_refs = list(msb_map.keys())

    if part_index >= len(msb_refs):
        return 0.0, 0.0, 0.0

    msb_ref = msb_refs[part_index]
    edges = _extract_part_edges(topology, msb_ref)

    if not edges:
        return 0.0, 0.0, 0.0

    # 收集所有顶点
    all_x, all_y, all_z = [], [], []
    for p1, p2 in edges:
        all_x.extend([p1[0], p2[0]])
        all_y.extend([p1[1], p2[1]])
        all_z.extend([p1[2], p2[2]])

    if not all_x:
        return 0.0, 0.0, 0.0

    length = round(max(all_x) - min(all_x), 1)
    width = round(max(all_y) - min(all_y), 1)
    height = round(max(all_z) - min(all_z), 1)

    return length, width, height


def render_part_multi_view(
    text: str,
    part_index: int,
) -> bytes:
    """为指定零件生成多视角参考图（2×2 网格：正视+右视+俯视+等轴测）。

    比单视角参考图提供更完整的 3D 信息，帮助 AI 更准确地理解零件形状。

    Args:
        text: STEP 文件全文
        part_index: 零件索引（0-based）

    Returns:
        1024×1024 PNG 图片字节数据
    """
    topology = _parse_step_topology(text)
    msb_map = topology["manifold_solids"]
    msb_refs = list(msb_map.keys())

    if part_index >= len(msb_refs):
        logger.warning(f"零件索引 {part_index} 超出范围（共 {len(msb_refs)} 个零件）")
        return _render_multi_view([])

    msb_ref = msb_refs[part_index]
    edges = _extract_part_edges(topology, msb_ref)

    logger.info(f"零件 {part_index} 多视角: 提取到 {len(edges)} 条边线")
    return _render_multi_view(edges)


def _compute_camera_angles(
    current_edges: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
    all_edges: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
) -> tuple[float, float]:
    """根据零件位置计算最佳观察角度。

    从零件安装方向看向装配体，让每步的视角都从零件插入方向看过去。
    """
    if not current_edges:
        return 25.0, -30.0

    # 当前零件中心
    n = len(current_edges) * 2
    cx = sum(p[0] for e in current_edges for p in e) / n
    cy = sum(p[1] for e in current_edges for p in e) / n
    cz = sum(p[2] for e in current_edges for p in e) / n

    # 装配体中心
    if all_edges:
        m = len(all_edges) * 2
        ax = sum(p[0] for e in all_edges for p in e) / m
        ay = sum(p[1] for e in all_edges for p in e) / m
        az = sum(p[2] for e in all_edges for p in e) / m
    else:
        ax, ay, az = 0.0, 0.0, 0.0

    # 方向：从零件中心指向外侧（安装方向的反方向）
    dx, dy, dz = cx - ax, cy - ay, cz - az
    dist = math.sqrt(dx*dx + dy*dy + dz*dz)
    if dist < 0.01:
        return 25.0, -30.0

    dx /= dist
    dy /= dist
    dz /= dist

    # 水平旋转角（绕 Y 轴）：从 Z 轴正方向顺时针
    ry_deg = -math.degrees(math.atan2(dx, dz))
    # 俯仰角：保持一定俯视
    horiz = math.sqrt(dx*dx + dz*dz)
    rx_deg = math.degrees(math.atan2(dz, horiz)) * 0.5 + 20

    # 限制 ry 在 [-90, 90] 范围内，防止极端角度导致模型偏移出画布
    ry_deg = max(-90.0, min(90.0, ry_deg))
    rx_deg = max(-10.0, min(60.0, rx_deg))

    return rx_deg, ry_deg


def _render_progressive_assembly(
    prev_edges: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
    current_edges: list[tuple[tuple[float, float, float], tuple[float, float, float]]],
    sequence: int,
    total_steps: int,
    is_final: bool = False,
    rx_deg: float = 25.0,
    ry_deg: float = -30.0,
    edge_groups: list[tuple[list, str]] | None = None,
    scale_params: dict | None = None,
) -> bytes:
    """渲染渐进式装配参考图（超采样抗锯齿 + 深度明暗）。

    edge_groups: 可选的分组边线列表 [(edges, color_hex), ...]。
                 提供时按组渲染，支持 per-part 颜色。
    scale_params: 可选的全局缩放参数（由 _compute_global_scale_params 生成）。
    """
    hi = REF_SIZE * 2  # 超采样 2x
    SS = 2

    # 确定要渲染的边线
    if edge_groups:
        all_edges = []
        for g_edges, _ in edge_groups:
            all_edges.extend(g_edges)
    else:
        all_edges = prev_edges + current_edges

    if not all_edges:
        img = Image.new("RGB", (REF_SIZE, REF_SIZE), "#f0f4f8")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    sin_ry = math.sin(math.radians(ry_deg))
    cos_ry = math.cos(math.radians(ry_deg))

    # 计算缩放参数（优先使用预计算的全局参数）
    if scale_params is not None:
        g_scale = scale_params["scale"] * (hi / REF_SIZE)
        cx, cy = hi / 2, hi / 2
        mid_x = scale_params["mid_x"]
        mid_y = scale_params["mid_y"]
        z_min = scale_params["z_min"]
        z_range = scale_params["z_range"]
    else:
        projected_all = []
        all_x, all_y, all_z = [], [], []
        for p1, p2 in all_edges:
            q1 = _project_iso(p1[0], p1[1], p1[2], rx_deg, ry_deg)
            q2 = _project_iso(p2[0], p2[1], p2[2], rx_deg, ry_deg)
            z1 = p1[0] * sin_ry + p1[2] * cos_ry
            z2 = p2[0] * sin_ry + p2[2] * cos_ry
            avg_z = (z1 + z2) / 2
            projected_all.append((q1, q2, avg_z))
            all_x.extend([q1[0], q2[0]])
            all_y.extend([q1[1], q2[1]])
            all_z.append(avg_z)

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
        range_x = max_x - min_x or 1
        range_y = max_y - min_y or 1
        margin = int(hi * 0.08)
        draw_area = hi - 2 * margin
        g_scale = min(draw_area / range_x, draw_area / range_y)
        cx, cy = hi / 2, hi / 2
        mid_x, mid_y = (min_x + max_x) / 2, (min_y + max_y) / 2
        z_min = min(all_z)
        z_range = (max(all_z) - min(all_z)) or 1

    # 高分辨率画布
    img = Image.new("RGB", (hi, hi), "#f0f4f8")
    draw = ImageDraw.Draw(img)

    # 背景网格
    grid_color = "#e2e8f0"
    for gx in range(0, hi, 80):
        draw.line([(gx, 0), (gx, hi)], fill=grid_color, width=1)
    for gy in range(0, hi, 80):
        draw.line([(0, gy), (hi, gy)], fill=grid_color, width=1)

    def _tx(q):
        return (cx + (q[0] - mid_x) * g_scale, cy + (q[1] - mid_y) * g_scale)

    if edge_groups:
        # 按组渲染，每组有自己的颜色
        for g_edges, g_color in edge_groups:
            if not g_edges:
                continue
            g_projected = []
            for p1, p2 in g_edges:
                q1 = _project_iso(p1[0], p1[1], p1[2], rx_deg, ry_deg)
                q2 = _project_iso(p2[0], p2[1], p2[2], rx_deg, ry_deg)
                z1 = p1[0] * sin_ry + p1[2] * cos_ry
                z2 = p2[0] * sin_ry + p2[2] * cos_ry
                avg_z = (z1 + z2) / 2
                g_projected.append((q1, q2, avg_z))

            # 解析基础颜色
            hex_c = g_color.lstrip("#")
            base_r = int(hex_c[0:2], 16)
            base_g = int(hex_c[2:4], 16)
            base_b = int(hex_c[4:6], 16)

            g_projected.sort(key=lambda e: e[2])
            for q1, q2, z in g_projected:
                x1, y1 = _tx(q1)
                x2, y2 = _tx(q2)
                # 跳过超出画布范围的边线
                if max(x1, x2) < -100 or min(x1, x2) > hi + 100:
                    continue
                if max(y1, y2) < -100 or min(y1, y2) > hi + 100:
                    continue
                d = max(0.0, min(1.0, (z - z_min) / z_range)) if z_range > 0 else 0.5
                r = max(0, min(255, int(base_r * (0.6 + d * 0.4))))
                g = max(0, min(255, int(base_g * (0.6 + d * 0.4))))
                b = max(0, min(255, int(base_b * (0.6 + d * 0.4))))
                lw = int((1.5 + d * 2) * SS)
                draw.line([(x1, y1), (x2, y2)], fill=f"#{r:02x}{g:02x}{b:02x}", width=lw)
    else:
        # 兼容旧接口：prev=灰色, current=橙色
        prev_count = len(prev_edges)

        def _color_lw(z, is_current):
            d = (z - z_min) / z_range
            if is_current:
                r = int(220 + d * 35)
                g = int(100 + d * 40)
                b = int(20 + d * 20)
                lw = int((2 + d * 3) * SS)
                return f"#{min(r,255):02x}{min(g,255):02x}{min(b,255):02x}", lw
            else:
                v = int(140 + d * 60)
                lw = int((1 + d * 1.5) * SS)
                return f"#{v:02x}{v:02x}{v:02x}", lw

        projected = []
        for p1, p2 in all_edges:
            q1 = _project_iso(p1[0], p1[1], p1[2], rx_deg, ry_deg)
            q2 = _project_iso(p2[0], p2[1], p2[2], rx_deg, ry_deg)
            z1 = p1[0] * sin_ry + p1[2] * cos_ry
            z2 = p2[0] * sin_ry + p2[2] * cos_ry
            avg_z = (z1 + z2) / 2
            projected.append((q1, q2, avg_z))

        indexed = list(enumerate(projected))
        indexed.sort(key=lambda x: x[1][2])

        for idx, (q1, q2, z) in indexed:
            x1, y1 = _tx(q1)
            x2, y2 = _tx(q2)
            is_current = idx >= prev_count
            color, lw = _color_lw(z, is_current)
            draw.line([(x1, y1), (x2, y2)], fill=color, width=lw)

    # 缩回标准尺寸
    img = img.resize((REF_SIZE, REF_SIZE), Image.LANCZOS)
    draw = ImageDraw.Draw(img)

    # 标题栏
    bar_h = 42
    if is_final:
        draw.rectangle([0, 0, REF_SIZE, bar_h], fill="#065f46")
        draw.text((16, 10), f"Step {sequence}/{total_steps}  —  Complete Assembly", fill="white")
    else:
        draw.rectangle([0, 0, REF_SIZE, bar_h], fill="#1e3a5f")
        draw.text(
            (16, 10),
            f"Step {sequence}/{total_steps}  —  Install highlighted part",
            fill="white",
        )

    # 底部信息栏
    bot_h = 36
    draw.rectangle([0, REF_SIZE - bot_h, REF_SIZE, REF_SIZE], fill="#1e293b")
    if edge_groups:
        total_edges = sum(len(g[0]) for g in edge_groups)
        info = f"Edges: {total_edges} total, {len(edge_groups)} parts"
    else:
        info = f"Edges: {len(current_edges)} current + {len(prev_edges)} assembled"
    draw.text((16, REF_SIZE - bot_h + 10), info, fill="#94a3b8")

    # 图例
    if not is_final:
        lx, ly = 16, bar_h + 12
        draw.rectangle([lx, ly, lx + 160, ly + 48], fill="#ffffff", outline="#cbd5e1")
        draw.rectangle([lx + 8, ly + 8, lx + 24, ly + 20], fill="#e07020")
        draw.text((lx + 30, ly + 7), "Current part", fill="#1e293b")
        draw.rectangle([lx + 8, ly + 28, lx + 24, ly + 40], fill="#b0b0b0")
        draw.text((lx + 30, ly + 27), "Assembled", fill="#64748b")

    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_progressive_assembly(
    text: str,
    current_part_index: int,
    total_steps: int,
    part_colors: dict[int, str] | None = None,
) -> bytes:
    """为装配步骤生成渐进式参考图（全局坐标系 + per-part 颜色）。

    - 已装配零件：灰色（或 STEP 中的真实颜色）
    - 当前零件：橙色高亮（或 STEP 中的真实颜色）
    - 最后一步：完整装配体全彩

    Args:
        text: STEP 文件全文
        current_part_index: 当前装配的零件索引（0-based）
        total_steps: 总步骤数
        part_colors: 可选的零件颜色映射 {part_index: "#rrggbb"}

    Returns:
        1024×1024 PNG 图片字节数据
    """
    topology = _parse_step_topology(text)
    msb_map = topology["manifold_solids"]
    msb_refs = list(msb_map.keys())
    total_parts = len(msb_refs)

    if total_parts == 0:
        return _render_progressive_assembly([], [], current_part_index + 1, total_steps)

    actual_index = current_part_index % total_parts
    is_final = (current_part_index == total_steps - 1)

    # 提取所有零件的边线（用于计算全局包围盒）
    all_part_edges = []
    for msb_ref in msb_refs:
        edges = _extract_part_edges(topology, msb_ref, max_edges=2000)
        all_part_edges.append(edges)

    # 计算默认颜色
    default_colors = ["#b0b0b0", "#909090", "#a0a0a0", "#c0c0c0", "#808080",
                      "#989898", "#a8a8a8", "#b8b8b8", "#888888", "#c8c8c8"]

    if is_final:
        # 最后一步：所有零件用各自颜色
        edge_groups = []
        for idx, edges in enumerate(all_part_edges):
            if edges:
                color = (part_colors or {}).get(idx, default_colors[idx % len(default_colors)])
                edge_groups.append((edges, color))

        # 计算全局缩放
        global_scale = _compute_global_scale_params(*[e for e, _ in edge_groups], rx_deg=25.0, ry_deg=-30.0)
        logger.info(f"最终步骤: 完整装配体, {len(edge_groups)} 个零件")
        return _render_progressive_assembly(
            [], [], current_part_index + 1, total_steps, is_final=True,
            rx_deg=25.0, ry_deg=-30.0,
            edge_groups=edge_groups, scale_params=global_scale,
        )

    # 渐进式：已装配灰色 + 当前橙色
    current_edges = all_part_edges[actual_index]
    edge_groups = []
    for i in range(actual_index):
        if all_part_edges[i]:
            edge_groups.append((all_part_edges[i], "#b0b0b0"))

    current_color = (part_colors or {}).get(actual_index, "#e07020")
    if all_part_edges[actual_index]:
        edge_groups.append((all_part_edges[actual_index], current_color))

    # 固定等轴测视角（25°, -30°）
    rx, ry = 25.0, -30.0

    # 缩放基于当前步骤可见零件（确保它们占画布主体）
    visible_edges = [e for e, _ in edge_groups]
    if visible_edges:
        global_scale = _compute_global_scale_params(*visible_edges, rx_deg=rx, ry_deg=ry)
    else:
        global_scale = None

    logger.info(
        f"渐进装配 步骤{current_part_index + 1}: "
        f"已装配{actual_index}个零件, "
        f"当前零件{actual_index}({len(current_edges)}边), "
        f"视角固定(25,-30)"
    )
    return _render_progressive_assembly(
        [], [], current_part_index + 1, total_steps,
        rx_deg=rx, ry_deg=ry,
        edge_groups=edge_groups, scale_params=global_scale,
    )
