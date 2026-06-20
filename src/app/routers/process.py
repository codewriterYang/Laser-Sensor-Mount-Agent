"""工艺生成与审核路由 — DraftProcessGraph 生成、查询、审核。"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.schemas import GenerateProcessRequest, SubmitReviewRequest
from ..services.process_generation_service import (
    ProcessGenerationFailedError,
    ProcessGenerationService,
    ProductGraphNotFoundError,
)
from ..services.review_service import (
    InvalidReviewActionError,
    ProcessNotFoundError,
    ReviewRequiredError,
    ReviewService,
)
from ..utils.error_handler import handle_service_errors
from ..utils.response import _error, _ok

router = APIRouter(prefix="/api/v1")


@router.post("/process/generate")
@handle_service_errors({
    ProductGraphNotFoundError: ("PRODUCT_GRAPH_NOT_FOUND", 404),
    ProcessGenerationFailedError: ("PROCESS_GENERATION_FAILED", 500),
})
async def generate_process(request: GenerateProcessRequest, db: Session = Depends(get_db)):
    """从 ProductGraph 生成 DraftProcessGraph。（Contract §5.1）"""
    svc = ProcessGenerationService(db)
    process_id, draft = svc.generate(request.productGraphId)
    return _ok({"processId": str(process_id), "status": draft.status, "steps": [s.model_dump() for s in draft.steps]})


@router.get("/process/{process_id}")
async def get_draft_process(process_id: UUID, db: Session = Depends(get_db)):
    """根据 ID 获取 DraftProcessGraph。（Contract §5.2）"""
    svc = ProcessGenerationService(db)
    draft = svc.get_draft(process_id)
    if draft is None:
        raise _error("PROCESS_NOT_FOUND", f"未找到工艺: {process_id}", 404)

    return _ok(draft.model_dump())


@router.post("/process/review")
@handle_service_errors({
    ProcessNotFoundError: ("PROCESS_NOT_FOUND", 404),
    ReviewRequiredError: ("REVIEW_REQUIRED", 422),
    InvalidReviewActionError: ("INVALID_REVIEW_ACTION", 422),
})
async def submit_review(request: SubmitReviewRequest, db: Session = Depends(get_db)):
    """提交工程师审核决策。（三阶段审核 — 第二阶段）"""
    svc = ReviewService(db)
    approved_id, approved = svc.submit_review(request.processId, request.decisions)
    return _ok({
        "approvedProcessId": str(approved_id),
        "status": "approved",
    })


@router.get("/approved-process/{approved_process_id}")
async def get_approved_process(approved_process_id: UUID, db: Session = Depends(get_db)):
    """根据 ID 获取 ApprovedProcessGraph。（Contract §6.2）"""
    svc = ReviewService(db)
    approved = svc.get_approved(approved_process_id)
    if approved is None:
        raise _error("APPROVED_PROCESS_NOT_FOUND", f"未找到已审核工艺: {approved_process_id}", 404)

    return _ok(approved.model_dump())
