"""指导书与 PDF 路由 — 渲染、审核、导出。"""

import json as _json
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.schemas import (
    ExportPdfRequest,
    InstructionReviewRequest,
    RenderInstructionRequest,
)
from ..services.instruction_service import (
    ApprovedProcessNotFoundError as InstructionApprovedNotFoundError,
    InstructionNotFoundError,
    InstructionService,
    PDFExportFailedError,
    RenderFailedError,
)
from ..utils.error_handler import handle_service_errors
from ..utils.response import _error, _ok

router = APIRouter(prefix="/api/v1")


@router.post("/instruction/render")
@handle_service_errors({
    InstructionApprovedNotFoundError: ("APPROVED_PROCESS_NOT_FOUND", 404),
    RenderFailedError: ("RENDER_FAILED", 500),
})
async def render_instruction(request: RenderInstructionRequest, db: Session = Depends(get_db)):
    """从 ApprovedProcessGraph 渲染 AssemblyInstruction。（Contract §7.1）"""
    svc = InstructionService(db)
    instruction_id, instruction = svc.render(request.approvedProcessId, mode=request.mode)
    return _ok({"instructionId": str(instruction_id)})


@router.post("/instruction/render-stream")
async def render_instruction_stream(request: RenderInstructionRequest, db: Session = Depends(get_db)):
    """流式渲染 AssemblyInstruction，逐步返回进度。（SSE）"""
    def event_generator():
        svc = InstructionService(db)
        for event in svc.render_stream(request.approvedProcessId, mode=request.mode):
            yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"
        db.commit()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/instruction/{instruction_id}")
async def get_instruction(instruction_id: UUID, db: Session = Depends(get_db)):
    """根据 ID 获取 AssemblyInstruction。（Contract §7.2）"""
    svc = InstructionService(db)
    instruction = svc.get_instruction(instruction_id)
    if instruction is None:
        raise _error("INSTRUCTION_NOT_FOUND", f"未找到指导书: {instruction_id}", 404)

    return _ok(instruction.model_dump())


@router.post("/instruction/review")
async def review_instruction(request: InstructionReviewRequest, db: Session = Depends(get_db)):
    """指导书审核。（三阶段审核 — 第三阶段）"""
    svc = InstructionService(db)
    instruction = svc.get_instruction(request.instructionId)
    if instruction is None:
        raise _error("INSTRUCTION_NOT_FOUND", f"未找到指导书: {request.instructionId}", 404)

    if request.action == "approve":
        return _ok({"instructionId": str(request.instructionId), "status": "approved", "action": "approve"})
    elif request.action == "reject":
        return _ok({"instructionId": str(request.instructionId), "status": "rejected", "action": "reject", "reason": request.reason})
    elif request.action == "regenerate_images":
        from ..repositories.instruction_repository import InstructionRepository
        repo = InstructionRepository(db)
        ai = repo.get_by_id(request.instructionId)
        if ai is None:
            raise _error("INSTRUCTION_NOT_FOUND", f"未找到指导书: {request.instructionId}", 404)
        approved_id = UUID(ai.approved_process_id)
        try:
            new_id, new_instruction = svc.render(approved_id, mode=request.mode)
            db.commit()
            return _ok({
                "instructionId": str(new_id),
                "status": "regenerated",
                "action": "regenerate_images",
            })
        except Exception as e:
            db.rollback()
            raise _error("RENDER_FAILED", f"重新生成失败: {e}", 500)
    else:
        raise _error("INVALID_REVIEW_ACTION", f"无效审核操作: {request.action}", 422)


@router.post("/instruction/export-pdf")
@handle_service_errors({
    InstructionNotFoundError: ("INSTRUCTION_NOT_FOUND", 404),
    PDFExportFailedError: ("PDF_EXPORT_FAILED", 500),
})
async def export_pdf(request: ExportPdfRequest, db: Session = Depends(get_db)):
    """将 AssemblyInstruction 导出为 PDF。（Contract §8.1）"""
    svc = InstructionService(db)
    pdf_path = svc.export_pdf(request.instructionId)
    return _ok({"pdfPath": pdf_path})


@router.get("/instruction/{instruction_id}/download-pdf")
async def download_pdf(instruction_id: UUID, db: Session = Depends(get_db)):
    """通过浏览器下载 PDF 文件。"""
    from ..repositories.instruction_repository import InstructionRepository
    repo = InstructionRepository(db)
    ai = repo.get_by_id(instruction_id)
    if ai is None or not ai.pdf_path:
        raise _error("INSTRUCTION_NOT_FOUND", f"未找到指导书或 PDF 未生成: {instruction_id}", 404)

    pdf_path = Path(ai.pdf_path)
    if not pdf_path.exists():
        raise _error("PDF_NOT_FOUND", f"PDF 文件不存在: {pdf_path}", 404)

    return FileResponse(
        path=str(pdf_path),
        filename=f"装配指导书_{instruction_id.hex[:8]}.pdf",
        media_type="application/pdf",
    )
