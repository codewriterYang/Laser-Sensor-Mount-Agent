"""STEP 分析路由 — 上传 STEP 文件、ProductGraph 查询与审核。"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.schemas import ProductGraphReviewRequest
from ..repositories.product_graph_repository import ProductGraphRepository
from ..services.step_analysis_service import (
    StepAnalysisService,
    StepFileInvalidError,
    StepFileNotFoundError,
    StepParseFailedError,
)
from ..utils.error_handler import handle_service_errors
from ..utils.response import _error, _ok

router = APIRouter(prefix="/api/v1")


@router.post("/step/analyze")
@handle_service_errors({
    StepFileNotFoundError: ("STEP_FILE_NOT_FOUND", 404),
    StepFileInvalidError: ("STEP_FILE_INVALID", 422),
    StepParseFailedError: ("STEP_PARSE_FAILED", 500),
})
async def analyze_step(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """上传 STEP 文件并生成 ProductGraph。（Contract §4.1）"""
    svc = StepAnalysisService(db)
    step_file_id, product_graph_id, status = svc.analyze(file)
    return _ok({"stepFileId": str(step_file_id), "productGraphId": str(product_graph_id), "status": status})


@router.get("/product-graphs/{product_graph_id}")
async def get_product_graph(product_graph_id: UUID, db: Session = Depends(get_db)):
    """根据 ID 获取 ProductGraph。（Contract §4.2）"""
    repo = ProductGraphRepository(db)
    pg = repo.get_by_id(product_graph_id)
    if pg is None:
        raise _error("PRODUCT_GRAPH_NOT_FOUND", f"未找到 ProductGraph: {product_graph_id}", 404)

    import json
    graph_data = json.loads(pg.graph_json)
    return _ok(graph_data)


@router.post("/product-graphs/review")
async def review_product_graph(request: ProductGraphReviewRequest, db: Session = Depends(get_db)):
    """产品结构图审核。（三阶段审核 — 第一阶段）"""
    repo = ProductGraphRepository(db)
    pg = repo.get_by_id(request.productGraphId)
    if pg is None:
        raise _error("PRODUCT_GRAPH_NOT_FOUND", f"未找到 ProductGraph: {request.productGraphId}", 404)

    if request.action == "accept":
        repo.update_status(request.productGraphId, "approved")
        db.commit()
        return _ok({"productGraphId": str(request.productGraphId), "status": "approved", "action": "accept"})
    elif request.action == "reject":
        repo.update_status(request.productGraphId, "rejected")
        db.commit()
        return _ok({"productGraphId": str(request.productGraphId), "status": "rejected", "action": "reject"})
    else:
        raise _error("INVALID_REVIEW_ACTION", f"无效审核操作: {request.action}", 422)
