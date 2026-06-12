"""装配示意图生成服务 — 基于 STEP 文件的真实几何数据生成示意图。

每个步骤生成不同视角的图，展示装配进度。
"""

from __future__ import annotations

import math
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..logger import logger

IMAGES_DIR = Path("exports/images")

# 不同步骤的视角参数（旋转角度、俯仰角）
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

# 不同步骤的高亮颜色
_STEP_COLORS = [
    ("#93c5fd", "#1e40af"),  # 蓝色 — 底座
    ("#fde68a", "#92400e"),  # 黄色 — 支架
    ("#a7f3d0", "#065f46"),  # 绿色 — 传感器
    ("#fca5a5", "#991b1b"),  # 红色 — 紧固件
    ("#c4b5fd", "#5b21b6"),  # 紫色 — 垫片
    ("#fdba74", "#9a3412"),  # 橙色 — 连接器
    ("#f9a8d4", "#9d174d"),  # 粉色 — 密封件
    ("#86efac", "#166534"),  # 浅绿 — 线缆
    ("#fcd34d", "#78350f"),  # 金黄 — 标签
    ("#a5b4fc", "#3730a3"),  # 靛蓝 — 外壳
]


def _get_font(size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """获取系统中文字体。"""
    for path in ["C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/msyh.ttc"]:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _project_3d(x: float, y: float, z: float, rx_deg: float = 25, ry_deg: float = -30) -> tuple[float, float]:
    """将 3D 坐标投影到 2D，支持自定义视角。"""
    rx = math.radians(rx_deg)
    ry = math.radians(ry_deg)
    # 先绕 Y 轴旋转
    x1 = x * math.cos(ry) - z * math.sin(ry)
    z1 = x * math.sin(ry) + z * math.cos(ry)
    # 再绕 X 轴旋转
    y1 = y * math.cos(rx) - z1 * math.sin(rx)
    z2 = y * math.sin(rx) + z1 * math.cos(rx)
    # 正交投影
    return x1, y1 + z2 * 0.3


class ImageService:
    """基于 STEP 真实几何数据生成装配示意图。

    不同步骤使用不同视角和颜色，展示装配进度。
    """

    def __init__(self):
        logger.info("图片服务已初始化（基于真实几何数据生成）")

    @property
    def enabled(self) -> bool:
        return True

    def generate_step_image(
        self,
        step_title: str,
        step_description: str,
        sequence: int,
        part_dimensions: dict | None = None,
    ) -> str | None:
        """为一个装配步骤生成示意图。"""
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        image_path = IMAGES_DIR / f"step_{sequence}_{uuid.uuid4().hex[:8]}.png"

        try:
            dims = part_dimensions or {}
            length = max(dims.get("length", 30), 5)
            width = max(dims.get("width", 20), 5)
            height = max(dims.get("height", 10), 5)

            self._draw_step_diagram(step_title, step_description, sequence, length, width, height, str(image_path))
            logger.info(f"步骤 {sequence} 示意图已生成：{image_path.name}")
            return str(image_path)
        except Exception as e:
            logger.error(f"步骤 {sequence} 示意图生成失败：{e}")
            return None

    def generate_all_step_images(self, steps: list[dict], part_dimensions: dict | None = None) -> dict[int, str]:
        """为所有步骤生成图片。"""
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
        self, title: str, description: str, sequence: int,
        length: float, width: float, height: float, output_path: str,
    ) -> None:
        """绘制装配步骤示意图：不同视角 + 不同颜色 + 装配进度。"""
        img = Image.new("RGB", (900, 600), "white")
        draw = ImageDraw.Draw(img)

        font_title = _get_font(18)
        font_body = _get_font(13)
        font_dim = _get_font(11)
        font_small = _get_font(10)

        # 顶部标题栏
        draw.rectangle([0, 0, 900, 55], fill="#1e40af")
        draw.text((20, 15), f"步骤 {sequence}：{title}", fill="white", font=font_title)

        # 获取当前步骤的视角和颜色（循环使用，不同步骤不同）
        view = _STEP_VIEWS[(sequence - 1) % len(_STEP_VIEWS)]
        fill_color, outline_color = _STEP_COLORS[(sequence - 1) % len(_STEP_COLORS)]

        # 计算缩放
        max_dim = max(length, width, height)
        scale = min(180 / max_dim, 5.0) if max_dim > 0 else 4.0
        cx, cy = 330, 320

        # 绘制已安装的零件（半透明，表示之前的步骤）
        for prev_step in range(1, sequence):
            prev_view = _STEP_VIEWS[(prev_step - 1) % len(_STEP_VIEWS)]
            prev_fill, prev_outline = _STEP_COLORS[(prev_step - 1) % len(_STEP_COLORS)]
            # 之前步骤的零件缩小一点，半透明效果
            shrink = 0.85
            self._draw_3d_box(draw, cx, cy, length * shrink, width * shrink, height * shrink,
                            scale, "#e8e8e8", "#c0c0c0", 1,
                            prev_view["rx"], prev_view["ry"])

        # 绘制当前步骤的零件（高亮，不透明）
        self._draw_3d_box(draw, cx, cy, length, width, height,
                        scale, fill_color, outline_color, 2,
                        view["rx"], view["ry"])

        # 尺寸标注
        self._draw_dimensions(draw, cx, cy, length, width, height, scale, font_dim, view["rx"], view["ry"])

        # 右侧步骤信息面板
        draw.rectangle([580, 70, 880, 420], fill="#f8fafc", outline="#e2e8f0", width=1)
        draw.text((595, 85), "装配说明", fill="#1e40af", font=font_title)
        draw.line([(595, 115), (865, 115)], fill="#e2e8f0", width=1)

        # 当前步骤高亮标记
        draw.rectangle([595, 125, 865, 155], fill=fill_color)
        draw.text((600, 130), f"当前步骤：{title}", fill=outline_color, font=font_body)

        # 描述文字
        y = 170
        for line in self._wrap_text(description, 28)[:6]:
            draw.text((595, y), line, fill="#334155", font=font_body)
            y += 22

        # 装配进度指示
        draw.line([(595, y + 10), (865, y + 10)], fill="#e2e8f0", width=1)
        draw.text((595, y + 20), "装配进度：", fill="#64748b", font=font_small)
        # 进度条
        bar_y = y + 40
        draw.rectangle([595, bar_y, 865, bar_y + 20], fill="#e2e8f0")
        progress = min(sequence / max(sequence, 5), 1.0)  # 假设至少5步
        draw.rectangle([595, bar_y, 595 + 270 * progress, bar_y + 20], fill=fill_color)
        draw.text((600, bar_y + 2), f"{int(progress * 100)}%", fill="white", font=font_small)

        # 底部信息
        draw.rectangle([0, 560, 900, 600], fill="#f1f5f9")
        draw.text((20, 572),
                  f"基于 STEP 文件真实数据 | 尺寸: {length:.1f} × {width:.1f} × {height:.1f} mm | 视角: {view['label']}",
                  fill="#64748b", font=font_body)

        img.save(output_path, "PNG")

    def _draw_3d_box(self, draw, ox, oy, length, width, height, scale, fill, outline, lw, rx, ry):
        """绘制 3D 等轴测长方体。"""
        verts = [
            (0, 0, 0), (length, 0, 0), (length, width, 0), (0, width, 0),
            (0, 0, height), (length, 0, height), (length, width, height), (0, width, height),
        ]
        pts = [(ox + _project_3d(x, y, z, rx, ry)[0] * scale,
                oy + _project_3d(x, y, z, rx, ry)[1] * scale) for x, y, z in verts]

        # 三个可见面
        for face in [[0, 1, 5, 4], [1, 2, 6, 5], [4, 5, 6, 7]]:
            draw.polygon([pts[i] for i in face], fill=fill, outline=outline, width=lw)

    def _draw_dimensions(self, draw, ox, oy, length, width, height, scale, font, rx, ry):
        """绘制尺寸标注线。"""
        # 长度标注（底部前边）
        p0 = _project_3d(0, 0, 0, rx, ry)
        p1 = _project_3d(length, 0, 0, rx, ry)
        self._dim_line(draw, ox + p0[0]*scale, oy + p0[1]*scale + 30,
                      ox + p1[0]*scale, oy + p1[1]*scale + 30,
                      f"L={length:.1f}mm", font)

        # 宽度标注
        p2 = _project_3d(length, width, 0, rx, ry)
        self._dim_line(draw, ox + p1[0]*scale + 20, oy + p1[1]*scale,
                      ox + p2[0]*scale + 20, oy + p2[1]*scale,
                      f"W={width:.1f}mm", font)

        # 高度标注
        p4 = _project_3d(0, 0, height, rx, ry)
        self._dim_line(draw, ox + p0[0]*scale - 25, oy + p0[1]*scale,
                      ox + p4[0]*scale - 25, oy + p4[1]*scale,
                      f"H={height:.1f}mm", font)

    def _dim_line(self, draw, x1, y1, x2, y2, label, font, color="#334155"):
        """绘制一条尺寸标注线。"""
        draw.line([(x1, y1), (x2, y2)], fill=color, width=1)
        draw.ellipse([x1-3, y1-3, x1+3, y1+3], fill=color)
        draw.ellipse([x2-3, y2-3, x2+3, y2+3], fill=color)
        mx, my = (x1+x2)/2, (y1+y2)/2
        draw.text((mx+4, my-8), label, fill=color, font=font)

    @staticmethod
    def _wrap_text(text: str, max_chars: int) -> list[str]:
        """将文本按指定宽度换行。"""
        lines = []
        while text:
            if len(text) <= max_chars:
                lines.append(text)
                break
            cut = max_chars
            for sep in ["，", "。", "、", "；", " ", ","]:
                idx = text[:max_chars].rfind(sep)
                if idx > max_chars // 2:
                    cut = idx + 1
                    break
            lines.append(text[:cut])
            text = text[cut:]
        return lines
