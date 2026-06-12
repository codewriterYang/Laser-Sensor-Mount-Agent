"""装配示意图生成服务 — 基于 STEP 文件的真实几何数据生成示意图。

不依赖外部 AI API，使用 Pillow 根据实际零件尺寸绘制等轴测图。
数据来源：STEP 文件解析器提取的包围盒尺寸（长×宽×高）。
"""

from __future__ import annotations

import math
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..logger import logger

IMAGES_DIR = Path("exports/images")


def _get_font(size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """获取系统中文字体，找不到时用默认字体。"""
    font_paths = [
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _project_3d(x: float, y: float, z: float) -> tuple[float, float]:
    """将 3D 坐标投影为 2D 等轴测视图。"""
    # 等轴测投影：X 轴 30° 向右下，Y 轴 30° 向左下，Z 轴垂直向上
    screen_x = (x - y) * math.cos(math.radians(30))
    screen_y = (x + y) * math.sin(math.radians(30)) - z
    return screen_x, screen_y


def _draw_3d_box(
    draw: ImageDraw.ImageDraw,
    ox: float, oy: float,
    length: float, width: float, height: float,
    scale: float,
    fill_color: str,
    outline_color: str,
    line_width: int = 2,
) -> None:
    """在指定位置绘制一个 3D 等轴测长方体。"""
    # 8 个顶点（以左下前角为原点）
    vertices_3d = [
        (0, 0, 0),          # 0: 左下前
        (length, 0, 0),     # 1: 右下前
        (length, width, 0), # 2: 右后前
        (0, width, 0),      # 3: 左后前
        (0, 0, height),     # 4: 左下后
        (length, 0, height),# 5: 右下后
        (length, width, height), # 6: 右后上
        (0, width, height), # 7: 左后上
    ]

    # 投影到 2D
    pts_2d = []
    for x, y, z in vertices_3d:
        sx, sy = _project_3d(x, y, z)
        pts_2d.append((ox + sx * scale, oy + sy * scale))

    # 三个可见面（前、右、顶）
    front = [pts_2d[0], pts_2d[1], pts_2d[5], pts_2d[4]]
    right = [pts_2d[1], pts_2d[2], pts_2d[6], pts_2d[5]]
    top   = [pts_2d[4], pts_2d[5], pts_2d[6], pts_2d[7]]

    draw.polygon(front, fill=fill_color, outline=outline_color, width=line_width)
    draw.polygon(right, fill=fill_color, outline=outline_color, width=line_width)
    draw.polygon(top, fill=fill_color, outline=outline_color, width=line_width)


def _draw_dimension_line(
    draw: ImageDraw.ImageDraw,
    x1: float, y1: float, x2: float, y2: float,
    label: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    color: str = "#334155",
) -> None:
    """绘制尺寸标注线。"""
    draw.line([(x1, y1), (x2, y2)], fill=color, width=1)
    # 两端小箭头
    draw.ellipse([x1 - 3, y1 - 3, x1 + 3, y1 + 3], fill=color)
    draw.ellipse([x2 - 3, y2 - 3, x2 + 3, y2 + 3], fill=color)
    # 标签
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    draw.text((mx + 4, my - 8), label, fill=color, font=font)


class ImageService:
    """基于 STEP 真实几何数据生成装配示意图。

    使用零件的实际包围盒尺寸（长/宽/高）绘制等轴测图。
    不依赖外部 AI API，保证图片与实际零件一致。
    """

    def __init__(self):
        """初始化图片服务。"""
        logger.info("图片服务已初始化（基于真实几何数据生成）")

    @property
    def enabled(self) -> bool:
        """图片服务始终可用（不依赖外部 API）。"""
        return True

    def generate_step_image(
        self,
        step_title: str,
        step_description: str,
        sequence: int,
        part_dimensions: dict | None = None,
    ) -> str | None:
        """为一个装配步骤生成示意图。

        参数：
            step_title: 步骤标题
            step_description: 步骤描述
            sequence: 步骤序号
            part_dimensions: 零件尺寸 {"length": float, "width": float, "height": float}

        返回图片文件路径，失败返回 None。
        """
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        image_path = IMAGES_DIR / f"step_{sequence}_{uuid.uuid4().hex[:8]}.png"

        try:
            # 使用真实尺寸，无数据时用默认比例
            dims = part_dimensions or {}
            length = dims.get("length", 30)
            width = dims.get("width", 20)
            height = dims.get("height", 10)

            # 确保尺寸不为零
            if length <= 0:
                length = 30
            if width <= 0:
                width = 20
            if height <= 0:
                height = 10

            self._draw_step_diagram(
                step_title, step_description, sequence,
                length, width, height,
                str(image_path),
            )
            logger.info(f"步骤 {sequence} 示意图已生成：{image_path.name}")
            return str(image_path)

        except Exception as e:
            logger.error(f"步骤 {sequence} 示意图生成失败：{e}")
            return None

    def generate_all_step_images(
        self,
        steps: list[dict],
        part_dimensions: dict | None = None,
    ) -> dict[int, str]:
        """为所有步骤生成图片。返回 {sequence: image_path}。"""
        results = {}
        for step in steps:
            seq = step.get("sequence", 0)
            title = step.get("title", "")
            desc = step.get("description", "")
            path = self.generate_step_image(title, desc, seq, part_dimensions)
            if path:
                results[seq] = path
        return results

    def _draw_step_diagram(
        self,
        title: str,
        description: str,
        sequence: int,
        length: float,
        width: float,
        height: float,
        output_path: str,
    ) -> None:
        """绘制装配步骤示意图：3D 等轴测图 + 步骤信息。"""
        img = Image.new("RGB", (900, 600), "white")
        draw = ImageDraw.Draw(img)

        font_title = _get_font(18)
        font_body = _get_font(13)
        font_dim = _get_font(11)

        # 顶部标题栏
        draw.rectangle([0, 0, 900, 55], fill="#1e40af")
        draw.text((20, 15), f"步骤 {sequence}：{title}", fill="white", font=font_title)

        # 计算合适的缩放比例，让零件在绘图区域中合适显示
        max_dim = max(length, width, height)
        scale = min(200 / max_dim, 6.0) if max_dim > 0 else 4.0

        # 3D 绘图区域中心
        cx, cy = 350, 310

        # 绘制阴影层
        _draw_3d_box(draw, cx + 4, cy + 4, length, width, height, scale,
                     fill_color="#e2e8f0", outline_color="#cbd5e1", line_width=1)

        # 绘制主零件（蓝色）
        _draw_3d_box(draw, cx, cy, length, width, height, scale,
                     fill_color="#bfdbfe", outline_color="#1e40af", line_width=2)

        # 尺寸标注线
        # 长度（底部前边）
        p0 = _project_3d(0, 0, 0)
        p1 = _project_3d(length, 0, 0)
        _draw_dimension_line(draw,
            cx + p0[0] * scale, cy + p0[1] * scale + 30,
            cx + p1[0] * scale, cy + p1[1] * scale + 30,
            f"L={length:.1f}mm", font_dim)

        # 宽度（底部右边）
        p2 = _project_3d(length, width, 0)
        _draw_dimension_line(draw,
            cx + p1[0] * scale + 20, cy + p1[1] * scale,
            cx + p2[0] * scale + 20, cy + p2[1] * scale,
            f"W={width:.1f}mm", font_dim)

        # 高度（左侧垂直）
        p4 = _project_3d(0, 0, height)
        _draw_dimension_line(draw,
            cx + p0[0] * scale - 25, cy + p0[1] * scale,
            cx + p4[0] * scale - 25, cy + p4[1] * scale,
            f"H={height:.1f}mm", font_dim)

        # 右侧步骤描述区
        draw.rectangle([580, 70, 880, 380], fill="#f8fafc", outline="#e2e8f0", width=1)
        draw.text((595, 85), "装配说明", fill="#1e40af", font=font_title)
        draw.line([(595, 115), (865, 115)], fill="#e2e8f0", width=1)

        # 描述文字换行
        desc_lines = self._wrap_text(description, 28)
        y = 125
        for line in desc_lines[:8]:
            draw.text((595, y), line, fill="#334155", font=font_body)
            y += 22

        # 底部信息栏
        draw.rectangle([0, 560, 900, 600], fill="#f1f5f9")
        draw.text((20, 572), f"基于 STEP 文件真实数据 | 长×宽×高: {length:.1f} × {width:.1f} × {height:.1f} mm",
                   fill="#64748b", font=font_body)

        img.save(output_path, "PNG")

    @staticmethod
    def _wrap_text(text: str, max_chars: int) -> list[str]:
        """将文本按指定宽度换行。"""
        lines = []
        while text:
            if len(text) <= max_chars:
                lines.append(text)
                break
            # 找到合适的断行点
            cut = max_chars
            for sep in ["，", "。", "、", "；", " ", ","]:
                idx = text[:max_chars].rfind(sep)
                if idx > max_chars // 2:
                    cut = idx + 1
                    break
            lines.append(text[:cut])
            text = text[cut:]
        return lines
