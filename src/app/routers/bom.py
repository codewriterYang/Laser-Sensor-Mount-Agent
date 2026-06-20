"""BOM 库管理路由 — 统计、导出、导入、从 STEP 生成。"""

import json

from fastapi import APIRouter, File, UploadFile

from ..utils.response import _error, _ok

router = APIRouter(prefix="/api/v1")


@router.get("/bom/stats")
async def bom_stats():
    """获取 BOM 库统计信息。"""
    from ..services.bom_library import get_bom_stats
    return _ok(get_bom_stats())


@router.get("/bom/export")
async def bom_export():
    """导出完整 BOM 库为 JSON。"""
    from ..services.bom_library import export_bom_json
    return _ok(export_bom_json())


@router.post("/bom/import")
async def bom_import(file: UploadFile = File(...)):
    """导入 BOM 库 JSON 文件。"""
    from ..services.bom_library import import_bom_json
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
        stats = import_bom_json(data)
        return _ok({"imported": stats, "filename": file.filename})
    except json.JSONDecodeError:
        raise _error("INVALID_JSON", "文件不是有效的 JSON 格式", 422)
    except Exception as e:
        raise _error("IMPORT_FAILED", f"导入失败: {e}", 500)


@router.post("/bom/generate-from-step")
async def bom_generate_from_step(file: UploadFile = File(...)):
    """从 STEP 文件自动生成 BOM 库数据。"""
    from ..services.bom_library import generate_bom_from_step, import_bom_json
    try:
        content = await file.read()
        step_text = content.decode("utf-8", errors="replace")
        bom_data = generate_bom_from_step(step_text)
        stats = import_bom_json(bom_data)
        return _ok({
            "generated": len(bom_data.get("standard_parts", [])),
            "imported": stats,
            "bom_data": bom_data,
        })
    except Exception as e:
        raise _error("GENERATE_FAILED", f"生成失败: {e}", 500)
