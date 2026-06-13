"""BOM 零件库 — 完全基于 JSON 文件，无硬编码数据。

初始状态：0 材料 / 0 标准件 / 0 模板
数据来源：从 STEP 文件自动生成 或 用户导入 JSON
"""

from __future__ import annotations

import json
from pathlib import Path

from ..logger import logger

# BOM 数据存储目录
BOM_DIR = Path("data/bom")
BOM_MATERIALS_FILE = BOM_DIR / "materials.json"
BOM_STANDARD_PARTS_FILE = BOM_DIR / "standard_parts.json"
BOM_PART_TEMPLATES_FILE = BOM_DIR / "part_templates.json"


def _load_json(path: Path, default):
    """通用 JSON 文件加载。"""
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"加载 {path.name} 失败：{e}")
    return default


def _save_json(path: Path, data) -> None:
    """通用 JSON 文件保存。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ─── 公开 API（仅返回自定义/导入的数据）───

def get_material(material_id: str) -> dict | None:
    """获取材料信息。"""
    return _load_json(BOM_MATERIALS_FILE, {}).get(material_id)


def get_all_materials() -> dict[str, dict]:
    """获取所有材料。"""
    return _load_json(BOM_MATERIALS_FILE, {})


def get_standard_parts() -> list[dict]:
    """获取所有标准件。"""
    return _load_json(BOM_STANDARD_PARTS_FILE, [])


def get_part_templates() -> list[dict]:
    """获取所有零件模板。"""
    return _load_json(BOM_PART_TEMPLATES_FILE, [])


def get_bom_stats() -> dict:
    """获取 BOM 库统计信息。"""
    return {
        "materials": len(get_all_materials()),
        "standard_parts": len(get_standard_parts()),
        "part_templates": len(get_part_templates()),
        "has_data": BOM_MATERIALS_FILE.exists() or BOM_STANDARD_PARTS_FILE.exists() or BOM_PART_TEMPLATES_FILE.exists(),
    }


# ─── 导入导出 ───

def import_bom_json(json_data: dict) -> dict:
    """导入 BOM 数据（合并到 JSON 文件，按 id 去重）。"""
    stats = {"materials": 0, "standard_parts": 0, "part_templates": 0}

    if "materials" in json_data:
        existing = _load_json(BOM_MATERIALS_FILE, {})
        existing.update(json_data["materials"])
        _save_json(BOM_MATERIALS_FILE, existing)
        stats["materials"] = len(json_data["materials"])

    if "standard_parts" in json_data:
        existing = _load_json(BOM_STANDARD_PARTS_FILE, [])
        existing_ids = {p.get("id") for p in existing}
        for part in json_data["standard_parts"]:
            if part.get("id") not in existing_ids:
                existing.append(part)
                existing_ids.add(part.get("id"))
        _save_json(BOM_STANDARD_PARTS_FILE, existing)
        stats["standard_parts"] = len(json_data["standard_parts"])

    if "part_templates" in json_data:
        existing = _load_json(BOM_PART_TEMPLATES_FILE, [])
        existing_ids = {t.get("id") for t in existing}
        for tpl in json_data["part_templates"]:
            if tpl.get("id") not in existing_ids:
                existing.append(tpl)
                existing_ids.add(tpl.get("id"))
        _save_json(BOM_PART_TEMPLATES_FILE, existing)
        stats["part_templates"] = len(json_data["part_templates"])

    logger.info(f"BOM 导入完成：{stats}")
    return stats


def export_bom_json() -> dict:
    """导出当前所有 BOM 数据为 JSON。"""
    return {
        "materials": get_all_materials(),
        "standard_parts": get_standard_parts(),
        "part_templates": get_part_templates(),
    }


def clear_bom() -> None:
    """清空所有 BOM 数据。"""
    for f in [BOM_MATERIALS_FILE, BOM_STANDARD_PARTS_FILE, BOM_PART_TEMPLATES_FILE]:
        if f.exists():
            f.unlink()
    logger.info("BOM 数据已清空")


# ─── 从 STEP 文件自动生成 ───

def generate_bom_from_step(step_text: str) -> dict:
    """从 STEP 文件自动生成 BOM 库数据。

    分析每个零件的几何特征，匹配到已知类型，生成 BOM 条目并保存到 JSON 文件。
    """
    from .reference_renderer import _parse_step_topology, _extract_part_edges, get_part_bounding_box
    from .bom_matcher import extract_geometric_features, match_part
    import re

    topology = _parse_step_topology(step_text)
    msb_refs = list(topology["manifold_solids"].keys())

    if not msb_refs:
        return {"materials": {}, "standard_parts": [], "part_templates": []}

    generated_parts = []

    for idx, msb_ref in enumerate(msb_refs):
        # 计算包围盒
        bbox_l, bbox_w, bbox_h = get_part_bounding_box(step_text, idx)

        # 提取几何特征
        msb_pattern = rf"#{msb_ref}\s*=\s*MANIFOLD_SOLID_BREP\s*\(\s*['\"][^'\"]*['\"]\s*,\s*#(\d+)"
        msb_match = re.search(msb_pattern, step_text)
        shell_ref = msb_match.group(1) if msb_match else ""

        features = None
        match_result = None
        if shell_ref:
            features = extract_geometric_features(
                step_text, shell_ref,
                bbox_length=bbox_l, bbox_width=bbox_w, bbox_height=bbox_h,
            )
            match_result = match_part(features)

        part_id = f"step_part_{idx}"
        part_entry = {
            "id": part_id,
            "name_cn": match_result.name_cn if match_result and match_result.name_cn else f"零件 {idx + 1}",
            "name_en": match_result.name_en if match_result and match_result.name_en else f"Part {idx + 1}",
            "geometry_signature": {
                "face_count_range": [
                    max(0, (features.face_count if features else 0) - 5),
                    (features.face_count if features else 0) + 5,
                ],
                "has_cylinder": features.has_cylinder if features else False,
                "has_sphere": features.has_sphere if features else False,
                "has_torus": features.has_torus if features else False,
                "has_cone": features.has_cone if features else False,
                "has_plane": features.has_plane if features else False,
                "aspect_ratio": features.aspect_ratio_type if features else "unknown",
            },
            "visual": match_result.visual_description if match_result else f"Part {idx + 1} from assembly",
            "material": match_result.material_id if match_result else "steel_q235",
            "typical_size_mm": [bbox_l, bbox_w, bbox_h],
            "auto_generated": True,
        }
        generated_parts.append(part_entry)

    # 保存到 JSON 文件
    result = {
        "materials": {},
        "standard_parts": generated_parts,
        "part_templates": [],
    }
    import_bom_json(result)
    logger.info(f"从 STEP 生成 {len(generated_parts)} 个零件条目")
    return result
