"""BOM 匹配器单元测试。"""

import json
from pathlib import Path

from src.app.services.bom_library import (
    get_material, get_standard_parts, get_part_templates,
    get_all_materials, get_bom_stats, import_bom_json, clear_bom,
    generate_bom_from_step,
)
from src.app.services.bom_matcher import (
    GeometricFeatures,
    match_part,
    _classify_aspect_ratio,
    _describe_cylindrical_features,
    _describe_edge_profile,
)


class TestBomLibraryEmpty:
    """BOM 库空状态测试（初始无数据）。"""

    def test_initially_empty(self):
        """清空后 BOM 库应为 0。"""
        clear_bom()
        stats = get_bom_stats()
        assert stats["materials"] == 0
        assert stats["standard_parts"] == 0
        assert stats["part_templates"] == 0

    def test_get_material_empty(self):
        """空库中查找材料应返回 None。"""
        clear_bom()
        assert get_material("aluminum_6061") is None

    def test_get_standard_parts_empty(self):
        """空库中标准件应为空列表。"""
        clear_bom()
        assert get_standard_parts() == []


class TestBomLibraryImport:
    """BOM 库导入测试。"""

    def test_import_materials(self):
        """导入材料应正确保存。"""
        clear_bom()
        data = {"materials": {"test_mat": {"name_cn": "测试材料", "color_hex": "#ff0000"}}}
        stats = import_bom_json(data)
        assert stats["materials"] == 1
        assert get_material("test_mat") is not None
        assert get_material("test_mat")["name_cn"] == "测试材料"

    def test_import_standard_parts(self):
        """导入标准件应正确保存。"""
        clear_bom()
        data = {"standard_parts": [{"id": "test_part", "name_cn": "测试零件"}]}
        stats = import_bom_json(data)
        assert stats["standard_parts"] == 1
        parts = get_standard_parts()
        assert len(parts) == 1
        assert parts[0]["id"] == "test_part"

    def test_import_dedup(self):
        """重复导入应按 id 去重。"""
        clear_bom()
        data = {"standard_parts": [{"id": "dup_part", "name_cn": "重复零件"}]}
        import_bom_json(data)
        import_bom_json(data)  # 重复导入
        parts = get_standard_parts()
        assert len(parts) == 1

    def teardown_method(self):
        """测试后清空。"""
        clear_bom()


class TestGeometricFeatures:
    """几何特征测试。"""

    def test_classify_aspect_ratio_elongated(self):
        assert _classify_aspect_ratio(100, 20, 20) == "elongated"

    def test_classify_aspect_ratio_compact(self):
        assert _classify_aspect_ratio(30, 28, 25) == "compact"

    def test_classify_aspect_ratio_unknown(self):
        assert _classify_aspect_ratio(0, 0, 0) == "unknown"


class TestCylindricalFeatures:
    """圆柱特征描述测试。"""

    def test_no_features(self):
        features = GeometricFeatures()
        assert _describe_cylindrical_features(features) == ""

    def test_small_holes(self):
        features = GeometricFeatures(cylindrical_radii=[1.5, 2.0, 1.8])
        desc = _describe_cylindrical_features(features)
        assert "3x small holes" in desc

    def test_mixed_sizes(self):
        features = GeometricFeatures(cylindrical_radii=[1.0, 2.0, 5.0, 10.0])
        desc = _describe_cylindrical_features(features)
        assert "small holes" in desc
        assert "large bores" in desc


class TestEdgeProfile:
    """边线轮廓描述测试。"""

    def test_no_edges(self):
        features = GeometricFeatures()
        assert _describe_edge_profile(features) == ""

    def test_mostly_straight(self):
        features = GeometricFeatures(edge_line_count=90, edge_circle_count=5, edge_spline_count=5)
        desc = _describe_edge_profile(features)
        assert "straight" in desc.lower()


class TestMatchPart:
    """零件匹配测试（BOM 为空时应返回 material_only）。"""

    def test_empty_bom_returns_material_only(self):
        """BOM 为空时应返回 material_only 类型。"""
        clear_bom()
        features = GeometricFeatures(
            face_count=4, has_cylinder=True, has_plane=True,
            cylindrical_radii=[6.0], aspect_ratio_type="flat",
        )
        result = match_part(features)
        assert result.match_type == "material_only"
        assert result.material_id != ""

    def test_with_imported_bom_matches(self):
        """导入 BOM 后应能匹配到标准件。"""
        clear_bom()
        import_bom_json({"standard_parts": [{
            "id": "test_washer",
            "name_cn": "测试垫圈",
            "name_en": "Test washer",
            "geometry_signature": {
                "face_count_range": [3, 6],
                "has_cylinder": True,
                "has_torus": False,
                "has_cone": False,
                "aspect_ratio": "flat",
            },
            "visual": "a thin flat washer",
            "material": "steel_q235",
        }]})

        features = GeometricFeatures(
            face_count=4, has_cylinder=True, has_plane=True,
            cylindrical_radii=[6.0], aspect_ratio_type="flat",
        )
        result = match_part(features)
        assert result.match_type == "standard_part"
        assert result.match_id == "test_washer"

    def teardown_method(self):
        """测试后清空 BOM 数据，避免污染其他测试。"""
        clear_bom()
