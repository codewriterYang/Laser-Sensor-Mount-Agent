"""装配示意图生成服务 — Seedream img2img + Pillow 参考图 + 降级。

优先级:
  1. Pillow 生成参考图 → Seedream img2img 增强（相似度 50-70%）
  2. 豆包 Seedream text2img（纯文本生成，相似度 40-60%）
  3. Pillow 模板绘制（降级方案，相似度 ~5%）

核心思路：用 Pillow 模板图作为参考图输入 Seedream img2img。
每步骤的 Pillow 图已包含正确的形状/颜色/视角/尺寸标注，
Seedream 负责将其增强为照片级真实渲染。
"""

from __future__ import annotations

import base64
import math
import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..config import is_image_configured
from ..logger import logger

IMAGES_DIR = Path("exports/images")

# 图片尺寸
IMG_W, IMG_H = 1200, 800

# 不同步骤的视角参数
_STEP_VIEWS = [
    {"rx": 25, "ry": -30, "label": "正视"},
    {"rx": 20, "ry": 20, "label": "侧视"},
    {"rx": 35, "ry": -15, "label": "俯视"},
    {"rx": 15, "ry": 45, "label": "右后视"},
    {"rx": 30, "ry": -45, "label": "左前视"},
    {"rx": 25, "ry": 10, "label": "右侧视"},
    {"rx": 40, "ry": -20, "label": "俯侧视"},
    {"rx": 20, "ry": 35, "label": "后视"},
    {"rx": 30, "ry": -10, "label": "前视"},
    {"rx": 25, "ry": 50, "label": "右后俯视"},
]

# 默认高亮颜色
_STEP_COLORS = [
    ("#93c5fd", "#1e40af"),
    ("#fde68a", "#92400e"),
    ("#a7f3d0", "#065f46"),
    ("#fca5a5", "#991b1b"),
    ("#c4b5fd", "#5b21b6"),
    ("#fdba74", "#9a3412"),
    ("#f9a8d4", "#9d174d"),
    ("#86efac", "#166534"),
    ("#fcd34d", "#78350f"),
    ("#a5b4fc", "#3730a3"),
]


def _get_font(size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in ["C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/msyh.ttc"]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _project_3d(x: float, y: float, z: float, rx_deg: float = 25, ry_deg: float = -30) -> tuple[float, float]:
    rx = math.radians(rx_deg)
    ry = math.radians(ry_deg)
    x1 = x * math.cos(ry) - z * math.sin(ry)
    z1 = x * math.sin(ry) + z * math.cos(ry)
    y1 = y * math.cos(rx) - z1 * math.sin(rx)
    z2 = y * math.sin(rx) + z1 * math.cos(rx)
    return x1, y1 + z2 * 0.3


def _step_color_to_hex(color_value) -> tuple[str, str]:
    if isinstance(color_value, str):
        hex_color = color_value.lstrip("#")
        if len(hex_color) == 6:
            try:
                r = int(hex_color[0:2], 16) / 255.0
                g = int(hex_color[2:4], 16) / 255.0
                b = int(hex_color[4:6], 16) / 255.0
            except ValueError:
                return "#808080", "#606060"
        else:
            return "#808080", "#606060"
    elif isinstance(color_value, (tuple, list)) and len(color_value) >= 3:
        r, g, b = color_value[0], color_value[1], color_value[2]
    else:
        return "#808080", "#606060"
    fill = f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
    outline = f"#{max(0, int(r*180)):02x}{max(0, int(g*180)):02x}{max(0, int(b*180)):02x}"
    return fill, outline


def _detect_shape_type(surface_types: list[str], face_count: int) -> str:
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


def _pil_to_png_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class ImageService:
    """装配示意图生成服务。

    流程: STEP 真实边线参考图 → Seedream img2img → 真实渲染图
    降级: Pillow 参考图 → img2img → Pillow 直接输出
    """

    def __init__(self):
        self._doubao_client = None
        if is_image_configured():
            try:
                from .doubao_image_client import DoubaoImageClient
                self._doubao_client = DoubaoImageClient()
                logger.info("图片服务已初始化（Seedream img2img 模式）")
            except Exception as e:
                logger.warning(f"豆包客户端初始化失败，使用 Pillow 降级：{e}")
        else:
            logger.info("图片服务已初始化（Pillow 模板模式）")

    @property
    def enabled(self) -> bool:
        return True

    @property
    def uses_ai(self) -> bool:
        return self._doubao_client is not None

    def generate_step_image(
        self,
        step_title: str,
        step_description: str,
        sequence: int,
        total_steps: int = 7,
        part_dimensions: dict | None = None,
        part_info: dict | None = None,
        step_text: str | None = None,
        mode: str = "comparison",  # "reference_only" | "text_and_image" | "comparison"
    ) -> str | None:
        """为一个装配步骤生成示意图。

        mode:
          - "reference_only": 仅 STEP 参考图
          - "ai_enhanced": 仅 AI 生成图
          - "comparison": 左右对比图（默认）
        """
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        image_path = IMAGES_DIR / f"step_{sequence}_{uuid.uuid4().hex[:8]}.png"

        try:
            dims = part_dimensions or {}
            length = max(dims.get("length", 30), 5)
            width = max(dims.get("width", 20), 5)
            height = max(dims.get("height", 10), 5)
            view = _STEP_VIEWS[(sequence - 1) % len(_STEP_VIEWS)]

            # Step 1: 生成参考图（左侧）
            ref_img = None
            part_index = 0
            part_count = 0
            if step_text:
                try:
                    from .reference_renderer import render_progressive_assembly, get_part_msb_refs, get_part_bounding_box, _parse_step_topology
                    msb_refs = get_part_msb_refs(step_text)
                    part_count = len(msb_refs)
                    part_index = (sequence - 1) % max(part_count, 1)

                    # 直接从 STEP 文件提取颜色（不依赖 part_info 匹配）
                    step_colors = {}
                    try:
                        from .step_parser import _extract_part_colors
                        _topo = _parse_step_topology(step_text)
                        _msb_map = _topo["manifold_solids"]
                        _msb_list = list(_msb_map.keys())
                        _colors = _extract_part_colors(step_text, _msb_list)
                        for idx, msb_ref in enumerate(_msb_list):
                            if msb_ref in _colors:
                                c = _colors[msb_ref]
                                r, g, b = int(c[0]*255), int(c[1]*255), int(c[2]*255)
                                step_colors[idx] = f"#{r:02x}{g:02x}{b:02x}"
                    except Exception as e:
                        logger.debug(f"STEP 颜色提取失败：{e}")

                    # 渐进式装配参考图：全局坐标 + per-part 颜色 + 动态视角
                    ref_img = render_progressive_assembly(
                        step_text, sequence - 1, total_steps,
                        part_colors=step_colors or None,
                    )
                    logger.info(f"步骤 {sequence} 渐进装配参考图已生成（{len(ref_img) // 1024} KB）")

                    # 使用精确包围盒替代估算值
                    bbox_l, bbox_w, bbox_h = get_part_bounding_box(step_text, part_index)
                    if bbox_l > 0 and bbox_w > 0 and bbox_h > 0:
                        length, width, height = bbox_l, bbox_w, bbox_h
                        logger.info(f"步骤 {sequence} 精确包围盒: {length}×{width}×{height} mm")
                except Exception as e:
                    logger.warning(f"步骤 {sequence} STEP 参考图失败：{e}")

            if not ref_img:
                ref_img = self._render_pillow_reference(
                    step_title, sequence, total_steps,
                    length, width, height, view, part_info,
                )

            # Step 1.5: BOM 匹配（增强 Prompt 精度）
            bom_data = {}
            if step_text and part_count > 0:
                try:
                    from .bom_matcher import extract_geometric_features, match_part
                    from .reference_renderer import get_part_msb_refs
                    msb_refs = get_part_msb_refs(step_text)
                    msb_ref = msb_refs.get(part_index, "")
                    if msb_ref:
                        # 获取零件的 CLOSED_SHELL ref
                        import re
                        msb_pattern = rf"#{msb_ref}\s*=\s*MANIFOLD_SOLID_BREP\s*\(\s*['\"][^'\"]*['\"]\s*,\s*#(\d+)"
                        msb_match = re.search(msb_pattern, step_text)
                        if msb_match:
                            shell_ref = msb_match.group(1)
                            features = extract_geometric_features(
                                step_text, shell_ref,
                                bbox_length=length, bbox_width=width, bbox_height=height,
                            )
                            match_result = match_part(features)
                            bom_data = {
                                "bom_visual": match_result.visual_description,
                                "bom_material": match_result.material_name,
                                "bom_finish": match_result.finish,
                                "cylindrical_features": match_result.cylindrical_features,
                                "edge_profile": match_result.edge_profile,
                                "match_type": match_result.match_type,
                                "match_id": match_result.match_id,
                                "name_cn": match_result.name_cn,
                                "confidence": match_result.confidence,
                            }
                            if match_result.match_type != "none":
                                logger.info(
                                    f"步骤 {sequence} BOM 匹配: {match_result.match_type}={match_result.name_cn}"
                                    f"（置信度 {match_result.confidence:.0%}）"
                                )
                except Exception as e:
                    logger.warning(f"步骤 {sequence} BOM 匹配失败：{e}")

            # Step 2: 根据模式决定是否生成 AI 图片
            ai_img = None
            if mode in ("comparison", "text_and_image") and self._doubao_client:
                try:
                    ai_img = self._generate_ai_bytes(
                        ref_img, step_title, step_description,
                        sequence, total_steps, view, part_info,
                        bom_data=bom_data,
                        use_llm=(mode == "text_and_image"),  # 仅文本加生图模式用 LLM
                    )
                except Exception as e:
                    logger.warning(f"步骤 {sequence} AI 生图失败：{e}")

            # Step 3: 根据模式输出最终图片
            if mode == "reference_only":
                # 模式: 仅参考图 — 只有线框参考图
                Path(str(image_path)).write_bytes(ref_img)
                logger.info(f"步骤 {sequence} 参考图已生成：{image_path.name}")
            elif mode == "comparison" and ai_img:
                # 模式: 对比图 — 参考图 + AI 生图并排
                composite = self._make_side_by_side(
                    ref_img, ai_img, sequence, step_title, part_info,
                )
                Path(str(image_path)).write_bytes(composite)
                logger.info(f"步骤 {sequence} 对比图已生成：{image_path.name}")
            elif mode == "text_and_image" and ai_img:
                # 模式: 文本加生图 — DeepSeek Prompt + AI 生图
                Path(str(image_path)).write_bytes(ai_img)
                logger.info(f"步骤 {sequence} AI 生成图已生成：{image_path.name}")
            else:
                # AI 不可用或失败时降级到参考图
                Path(str(image_path)).write_bytes(ref_img)
                logger.info(f"步骤 {sequence} 参考图已生成（AI 降级）：{image_path.name}")

            return str(image_path)

        except Exception as e:
            logger.error(f"步骤 {sequence} 示意图生成失败：{e}")
            return None

    def _generate_ai_bytes(
        self, ref_png: bytes, step_title: str, step_description: str,
        sequence: int, total_steps: int, view: dict, part_info: dict | None,
        bom_data: dict | None = None, use_llm: bool = False,
    ) -> bytes:
        """调用 Seedream img2img，返回图片字节。

        use_llm: True 时优先用 DeepSeek 生成 Prompt，False 时用规则模板。
        """
        info = part_info or {}
        bom = bom_data or {}

        # 仅 text_and_image 模式使用 LLM 生成 Prompt，其他模式用规则模板
        prompt = None
        if use_llm:
            try:
                from .llm_service import LLMService
                llm = LLMService()
                prompt = llm.generate_image_prompt(
                    part_name=info.get("name", ""),
                    face_count=info.get("faceCount", 0),
                    surface_types=info.get("surfaceTypes", []),
                    color_hex=info.get("color"),
                    length=info.get("length", 0),
                    width=info.get("width", 0),
                    height=info.get("height", 0),
                    sequence=sequence,
                    total_steps=total_steps,
                    step_title=step_title,
                )
            except Exception:
                pass

        # LLM 失败或不使用 LLM 时，使用规则模板
        if not prompt:
            from .prompt_builder import build_step_image_prompt
            prompt = build_step_image_prompt(
                part_name=info.get("name", ""),
                face_count=info.get("faceCount", 0),
                surface_types=info.get("surfaceTypes", []),
                color_hex=info.get("color"),
                length=info.get("length", 0),
                width=info.get("width", 0),
                height=info.get("height", 0),
                sequence=sequence,
                total_steps=total_steps,
                step_title=step_title,
                view_label=view["label"],
                bom_visual=bom.get("bom_visual", ""),
                bom_material=bom.get("bom_material", ""),
                bom_finish=bom.get("bom_finish", ""),
                cylindrical_features=bom.get("cylindrical_features", ""),
                edge_profile=bom.get("edge_profile", ""),
            )
        return self._doubao_client.generate_with_reference(
            prompt=prompt, reference_image=ref_png,
            strength=0.72, size="1920x1920",
        )

    def _make_side_by_side(
        self, ref_bytes: bytes, ai_bytes: bytes | None,
        sequence: int, title: str, part_info: dict | None,
    ) -> bytes:
        """生成左右对比图：左侧参考图，右侧 AI 渲染图。"""
        # 单侧尺寸
        side_w, side_h = 1200, 800
        gap = 20
        label_h = 50
        total_w = side_w * 2 + gap
        total_h = side_h + label_h

        canvas = Image.new("RGB", (total_w, total_h), "white")
        draw = ImageDraw.Draw(canvas)
        font_label = _get_font(18)
        font_title = _get_font(14)

        # 左侧：参考图
        ref_img = Image.open(BytesIO(ref_bytes)).resize((side_w, side_h), Image.LANCZOS)
        canvas.paste(ref_img, (0, label_h))
        draw.rectangle([0, 0, side_w, label_h], fill="#1e40af")
        draw.text((20, 14), f"步骤 {sequence}：STEP 参考图", fill="white", font=font_label)

        # 右侧：AI 渲染图
        if ai_bytes:
            ai_img = Image.open(BytesIO(ai_bytes)).resize((side_w, side_h), Image.LANCZOS)
            canvas.paste(ai_img, (side_w + gap, label_h))
            draw.rectangle([side_w + gap, 0, total_w, label_h], fill="#065f46")
            draw.text((side_w + gap + 20, 14), f"步骤 {sequence}：AI 渲染图", fill="white", font=font_label)
        else:
            draw.rectangle([side_w + gap, label_h, total_w, total_h], fill="#f1f5f9")
            draw.rectangle([side_w + gap, 0, total_w, label_h], fill="#9ca3af")
            draw.text((side_w + gap + 20, 14), f"步骤 {sequence}：AI 生成失败", fill="white", font=font_label)
            font_big = _get_font(20)
            draw.text((side_w + gap + side_w // 2 - 60, total_h // 2), "未生成", fill="#9ca3af", font=font_big)

        # 底部信息
        part_name = part_info.get("name", "") if part_info else ""
        info_text = f"{title}"
        if part_name:
            info_text += f" | 零件：{part_name}"
        draw.text((20, total_h - 25), info_text, fill="#64748b", font=font_title)

        buf = BytesIO()
        canvas.save(buf, format="PNG")
        return buf.getvalue()

    def _render_pillow_reference(
        self, title: str, sequence: int, total_steps: int,
        length: float, width: float, height: float,
        view: dict, part_info: dict | None,
    ) -> bytes:
        """用 Pillow 生成参考图（1024×1024，包含形状/颜色/视角信息）。"""
        ref_size = 1024
        img = Image.new("RGB", (ref_size, ref_size), "white")
        draw = ImageDraw.Draw(img)

        # 获取颜色
        default_fill, default_outline = _STEP_COLORS[(sequence - 1) % len(_STEP_COLORS)]
        fill_color, outline_color = default_fill, default_outline
        if part_info and part_info.get("color"):
            fill_color, outline_color = _step_color_to_hex(part_info["color"])

        # 虚拟尺寸（填满画面）
        v_length, v_width, v_height = 80, 60, 40
        scale = 5.0
        cx, cy = ref_size // 2, ref_size // 2 + 50

        # 已安装零件（灰色淡化）
        for prev_step in range(1, sequence):
            self._draw_3d_box(draw, cx, cy, v_length * 0.7, v_width * 0.7, v_height * 0.7,
                            scale, "#e8e8e8", "#c0c0c0", 1, view["rx"], view["ry"])

        # 当前零件（彩色高亮）
        shape_type = "box"
        surface_types = []
        if part_info:
            surface_types = part_info.get("surfaceTypes", [])
            shape_type = _detect_shape_type(surface_types, part_info.get("faceCount", 0))

        if shape_type == "cylinder":
            self._draw_cylinder(draw, cx, cy, v_length, v_width, v_height,
                              scale, fill_color, outline_color, 3, view["rx"], view["ry"])
        elif shape_type == "sphere":
            self._draw_sphere(draw, cx, cy, v_length, v_width, v_height,
                            scale, fill_color, outline_color, 3, view["rx"], view["ry"])
        elif shape_type == "threaded":
            self._draw_threaded(draw, cx, cy, v_length, v_width, v_height,
                              scale, fill_color, outline_color, 3, view["rx"], view["ry"])
        elif shape_type == "plate":
            self._draw_plate(draw, cx, cy, v_length, v_width, v_height,
                           scale, fill_color, outline_color, 3, view["rx"], view["ry"])
        else:
            self._draw_3d_box(draw, cx, cy, v_length, v_width, v_height,
                            scale, fill_color, outline_color, 3, view["rx"], view["ry"])

        # 尺寸标注
        font_dim = _get_font(14)
        self._draw_dimensions(draw, cx, cy, v_length, v_width, v_height, scale, font_dim,
                              view["rx"], view["ry"], actual_dims=(length, width, height))

        return _pil_to_png_bytes(img)

    def generate_all_step_images(
        self, steps: list[dict], part_dimensions: dict | None = None,
        per_step_info: dict | None = None,
        step_text: str | None = None,
        mode: str = "comparison",
    ) -> dict[int, str]:
        per_step_info = per_step_info or {}
        results = {}
        total_steps = len(steps)
        for i, step in enumerate(steps):
            seq = i + 1  # 用循环索引作为步骤编号（非 step.sequence）
            title = step.get("title", "")
            desc = step.get("description", "")
            info = per_step_info.get(seq)
            step_dims = None
            if info:
                step_dims = {
                    "length": info.get("length", 0),
                    "width": info.get("width", 0),
                    "height": info.get("height", 0),
                }
            path = self.generate_step_image(
                title, desc, seq,
                total_steps=total_steps,
                part_dimensions=step_dims or part_dimensions,
                part_info=info,
                step_text=step_text,
                mode=mode,
            )
            if path:
                results[seq] = path
        return results

    @staticmethod
    def _resize_to_target(image_path: str) -> None:
        try:
            img = Image.open(image_path)
            ratio = max(IMG_W / img.width, IMG_H / img.height)
            new_w = int(img.width * ratio)
            new_h = int(img.height * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            left = (new_w - IMG_W) // 2
            top = (new_h - IMG_H) // 2
            img = img.crop((left, top, left + IMG_W, top + IMG_H))
            img.save(image_path, "PNG")
        except Exception as e:
            logger.warning(f"图片缩放失败：{e}")

    # === 3D 形状绘制方法 ===

    def _draw_3d_box(self, draw, ox, oy, length, width, height, scale, fill, outline, lw, rx, ry):
        verts = [
            (0, 0, 0), (length, 0, 0), (length, width, 0), (0, width, 0),
            (0, 0, height), (length, 0, height), (length, width, height), (0, width, height),
        ]
        pts = [(ox + _project_3d(x, y, z, rx, ry)[0] * scale,
                oy + _project_3d(x, y, z, rx, ry)[1] * scale) for x, y, z in verts]
        faces = [
            ([0, 1, 5, 4], fill),
            ([1, 2, 6, 5], _lighten(fill, 0.85)),
            ([4, 5, 6, 7], _lighten(fill, 0.7)),
        ]
        for indices, fcolor in faces:
            draw.polygon([pts[i] for i in indices], fill=fcolor, outline=outline, width=lw)

    def _draw_cylinder(self, draw, ox, oy, length, width, height, scale, fill, outline, lw, rx, ry):
        r = min(width, height) / 2
        half_l = length / 2
        n_pts = 24
        top_pts, bot_pts = [], []
        for i in range(n_pts):
            angle = 2 * math.pi * i / n_pts
            cx_off = half_l
            cy_off = r * math.cos(angle)
            cz_top = r * math.sin(angle) + height / 2
            cz_bot = r * math.sin(angle) - height / 2
            top_pts.append((ox + _project_3d(cx_off, cy_off, cz_top, rx, ry)[0] * scale,
                          oy + _project_3d(cx_off, cy_off, cz_top, rx, ry)[1] * scale))
            bot_pts.append((ox + _project_3d(cx_off, cy_off, cz_bot, rx, ry)[0] * scale,
                          oy + _project_3d(cx_off, cy_off, cz_bot, rx, ry)[1] * scale))
        draw.polygon(bot_pts, fill=_lighten(fill, 0.7), outline=outline, width=lw)
        draw.polygon(top_pts + bot_pts[::-1], fill=fill, outline=outline, width=lw)
        draw.polygon(top_pts, fill=_lighten(fill, 0.85), outline=outline, width=lw)

    def _draw_sphere(self, draw, ox, oy, length, width, height, scale, fill, outline, lw, rx, ry):
        r = min(length, width, height) / 2
        n_pts = 32
        equator = []
        for i in range(n_pts):
            angle = 2 * math.pi * i / n_pts
            px, py = r * math.cos(angle), r * math.sin(angle)
            equator.append((ox + _project_3d(px, py, r, rx, ry)[0] * scale,
                          oy + _project_3d(px, py, r, rx, ry)[1] * scale))
        upper, lower = [], []
        for i in range(n_pts):
            angle = 2 * math.pi * i / n_pts
            px = r * math.cos(angle)
            pz_pos = r * math.sin(angle)
            pz_neg = -r * math.sin(angle)
            upper.append((ox + _project_3d(px, 0, pz_pos + r, rx, ry)[0] * scale,
                        oy + _project_3d(px, 0, pz_pos + r, rx, ry)[1] * scale))
            lower.append((ox + _project_3d(px, 0, pz_neg + r, rx, ry)[0] * scale,
                        oy + _project_3d(px, 0, pz_neg + r, rx, ry)[1] * scale))
        draw.polygon(equator + upper[::-1], fill=_lighten(fill, 0.7), outline=outline, width=lw)
        draw.polygon(equator + lower[::-1], fill=fill, outline=outline, width=lw)
        hx, hy = ox + _project_3d(-r * 0.2, -r * 0.2, r * 1.5, rx, ry)[0] * scale, \
                  oy + _project_3d(-r * 0.2, -r * 0.2, r * 1.5, rx, ry)[1] * scale
        hl = r * 0.15 * scale
        draw.ellipse([hx - hl, hy - hl, hx + hl, hy + hl], fill=_lighten(fill, 1.3))

    def _draw_threaded(self, draw, ox, oy, length, width, height, scale, fill, outline, lw, rx, ry):
        r = min(width, height) / 2
        head_r = r * 1.5
        head_h = height * 0.2
        n_pts = 12
        head_pts_top, head_pts_bot = [], []
        for i in range(n_pts):
            angle = 2 * math.pi * i / n_pts
            cy_off = head_r * math.cos(angle)
            cz_top = head_r * math.sin(angle) + height - head_h
            cz_bot = head_r * math.sin(angle) + height
            head_pts_top.append((ox + _project_3d(0, cy_off, cz_top, rx, ry)[0] * scale,
                               oy + _project_3d(0, cy_off, cz_top, rx, ry)[1] * scale))
            head_pts_bot.append((ox + _project_3d(0, cy_off, cz_bot, rx, ry)[0] * scale,
                               oy + _project_3d(0, cy_off, cz_bot, rx, ry)[1] * scale))
        shaft_pts, shaft_bot = [], []
        for i in range(n_pts):
            angle = 2 * math.pi * i / n_pts
            cy_off = r * math.cos(angle)
            cz_shaft = r * math.sin(angle) + height - head_h
            cz_bot = r * math.sin(angle)
            shaft_pts.append((ox + _project_3d(length, cy_off, cz_shaft, rx, ry)[0] * scale,
                            oy + _project_3d(length, cy_off, cz_shaft, rx, ry)[1] * scale))
            shaft_bot.append((ox + _project_3d(length, cy_off, cz_bot, rx, ry)[0] * scale,
                            oy + _project_3d(length, cy_off, cz_bot, rx, ry)[1] * scale))
        draw.polygon(shaft_bot, fill=_lighten(fill, 0.7), outline=outline, width=lw)
        for i in range(n_pts - 1):
            draw.polygon([shaft_bot[i], shaft_bot[i+1], shaft_pts[i+1], shaft_pts[i]], fill=fill, outline=outline, width=1)
        for j in range(3, len(shaft_bot) - 1, 4):
            for i in range(n_pts - 1):
                draw.line([shaft_bot[j], shaft_bot[j+1]], fill=_lighten(fill, 0.5), width=1)
        draw.polygon(head_pts_top, fill=_lighten(fill, 0.85), outline=outline, width=lw)
        draw.polygon(head_pts_bot, fill=_lighten(fill, 0.9), outline=outline, width=lw)

    def _draw_plate(self, draw, ox, oy, length, width, height, scale, fill, outline, lw, rx, ry):
        plate_h = max(height, 2)
        verts = [
            (0, 0, 0), (length, 0, 0), (length, width, 0), (0, width, 0),
            (0, 0, plate_h), (length, 0, plate_h), (length, width, plate_h), (0, width, plate_h),
        ]
        pts = [(ox + _project_3d(x, y, z, rx, ry)[0] * scale,
                oy + _project_3d(x, y, z, rx, ry)[1] * scale) for x, y, z in verts]
        faces = [
            ([0, 1, 5, 4], fill),
            ([1, 2, 6, 5], _lighten(fill, 0.85)),
            ([4, 5, 6, 7], _lighten(fill, 0.7)),
        ]
        for indices, fcolor in faces:
            draw.polygon([pts[i] for i in indices], fill=fcolor, outline=outline, width=lw)

    def _draw_dimensions(self, draw, ox, oy, length, width, height, scale, font, rx, ry,
                         actual_dims: tuple[float, float, float] | None = None):
        al, aw, ah = actual_dims if actual_dims else (length, width, height)
        p0 = _project_3d(0, 0, 0, rx, ry)
        p1 = _project_3d(length, 0, 0, rx, ry)
        self._dim_line(draw, ox + p0[0]*scale, oy + p0[1]*scale + 35,
                      ox + p1[0]*scale, oy + p1[1]*scale + 35,
                      f"L={al:.1f}mm", font)
        p2 = _project_3d(length, width, 0, rx, ry)
        self._dim_line(draw, ox + p1[0]*scale + 25, oy + p1[1]*scale,
                      ox + p2[0]*scale + 25, oy + p2[1]*scale,
                      f"W={aw:.1f}mm", font)
        p4 = _project_3d(0, 0, height, rx, ry)
        self._dim_line(draw, ox + p0[0]*scale - 30, oy + p0[1]*scale,
                      ox + p4[0]*scale - 30, oy + p4[1]*scale,
                      f"H={ah:.1f}mm", font)

    def _dim_line(self, draw, x1, y1, x2, y2, label, font, color="#334155"):
        draw.line([(x1, y1), (x2, y2)], fill=color, width=1)
        draw.ellipse([x1-3, y1-3, x1+3, y1+3], fill=color)
        draw.ellipse([x2-3, y2-3, x2+3, y2+3], fill=color)
        mx, my = (x1+x2)/2, (y1+y2)/2
        draw.text((mx+4, my-8), label, fill=color, font=font)


def _lighten(hex_color: str, factor: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    if factor > 1:
        r = min(255, int(r + (255 - r) * (factor - 1)))
        g = min(255, int(g + (255 - g) * (factor - 1)))
        b = min(255, int(b + (255 - b) * (factor - 1)))
    else:
        r = max(0, int(r * factor))
        g = max(0, int(g * factor))
        b = max(0, int(b * factor))
    return f"#{r:02x}{g:02x}{b:02x}"
