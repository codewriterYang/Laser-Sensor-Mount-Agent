"""FastAPI 应用程序 — 激光传感器支架装配 Agent。

所有路由遵循 05_CONTRACT.md 规范。
三阶段审核：产品结构审核 → 装配流程审核 → 指导书审核。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .database import create_tables, get_db
from .models.schemas import (
    ApprovedProcessGraphSchema,
    AssemblyInstructionSchema,
    DraftProcessGraphSchema,
    ExportPdfData,
    ExportPdfRequest,
    GenerateProcessData,
    GenerateProcessRequest,
    InstructionReviewRequest,
    ProductGraphReviewRequest,
    ProductGraphSchema,
    RenderInstructionData,
    RenderInstructionRequest,
    StandardResponse,
    SubmitReviewData,
    SubmitReviewRequest,
)
from .repositories.product_graph_repository import ProductGraphRepository
from .services.instruction_service import (
    ApprovedProcessNotFoundError as InstructionApprovedNotFoundError,
    InstructionNotFoundError,
    InstructionService,
    PDFExportFailedError,
    RenderFailedError,
)
from .services.process_generation_service import (
    ProcessGenerationFailedError,
    ProcessGenerationService,
    ProductGraphNotFoundError,
)
from .services.review_service import (
    InvalidReviewActionError,
    ProcessNotFoundError,
    ReviewRequiredError,
    ReviewService,
)
from .services.step_analysis_service import (
    StepAnalysisService,
    StepFileInvalidError,
    StepFileNotFoundError,
    StepParseFailedError,
)

app = FastAPI(title="激光传感器支架装配 Agent", version="0.1.0")

# 过滤 uvicorn access log 中的噪音（favicon.ico、chrome devtools 等）
import logging
class _NoiseFilter(logging.Filter):
    _IGNORE = ("/favicon.ico", "/.well-known/", "/robots.txt")
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return not any(n in msg for n in self._IGNORE)

for h in logging.getLogger("uvicorn.access").handlers:
    h.addFilter(_NoiseFilter())

# 前端静态文件
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# 导出文件（PDF 和图片）
_exports_dir = Path("exports")
_exports_dir.mkdir(exist_ok=True)
app.mount("/exports", StaticFiles(directory=str(_exports_dir)), name="exports")


@app.get("/")
async def root():
    """提供前端 SPA 页面。"""
    return FileResponse(str(_static_dir / "index.html"))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """将 HTTPException.detail 解包为直接 JSON 响应体。"""
    return JSONResponse(status_code=exc.status_code, content=exc.detail)


@app.on_event("startup")
def on_startup():
    create_tables()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ok(data: dict) -> dict:
    return {"success": True, "data": data, "timestamp": _now()}


def _error(code: str, message: str, status_code: int = 400) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"success": False, "error": {"code": code, "message": message}, "timestamp": _now()},
    )


# === STEP 分析 (Epic-1) ===


@app.post("/api/v1/step/analyze")
async def analyze_step(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """上传 STEP 文件并生成 ProductGraph。（Contract §4.1）"""
    svc = StepAnalysisService(db)
    try:
        step_file_id, product_graph_id, status = svc.analyze(file)
        db.commit()
    except StepFileNotFoundError:
        db.rollback()
        raise _error("STEP_FILE_NOT_FOUND", f"未找到文件: {file.filename}", 404)
    except StepFileInvalidError:
        db.rollback()
        raise _error("STEP_FILE_INVALID", f"无效文件类型: {file.filename}", 422)
    except StepParseFailedError:
        db.rollback()
        raise _error("STEP_PARSE_FAILED", f"解析失败: {file.filename}", 500)
    except Exception:
        db.rollback()
        raise _error("INTERNAL_SERVER_ERROR", "意外错误", 500)

    return _ok({"stepFileId": str(step_file_id), "productGraphId": str(product_graph_id), "status": status})


@app.get("/api/v1/product-graphs/{product_graph_id}")
async def get_product_graph(product_graph_id: UUID, db: Session = Depends(get_db)):
    """根据 ID 获取 ProductGraph。（Contract §4.2）"""
    repo = ProductGraphRepository(db)
    pg = repo.get_by_id(product_graph_id)
    if pg is None:
        raise _error("PRODUCT_GRAPH_NOT_FOUND", f"未找到 ProductGraph: {product_graph_id}", 404)

    graph_data = json.loads(pg.graph_json)
    return _ok(graph_data)


@app.post("/api/v1/product-graphs/review")
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


# === 工艺生成 (Epic-2) ===


@app.post("/api/v1/process/generate")
async def generate_process(request: GenerateProcessRequest, db: Session = Depends(get_db)):
    """从 ProductGraph 生成 DraftProcessGraph。（Contract §5.1）"""
    svc = ProcessGenerationService(db)
    try:
        process_id, draft = svc.generate(request.productGraphId)
        db.commit()
    except ProductGraphNotFoundError:
        db.rollback()
        raise _error("PRODUCT_GRAPH_NOT_FOUND", f"未找到 ProductGraph: {request.productGraphId}", 404)
    except ProcessGenerationFailedError as e:
        db.rollback()
        raise _error("PROCESS_GENERATION_FAILED", str(e), 500)
    except Exception:
        db.rollback()
        raise _error("INTERNAL_SERVER_ERROR", "意外错误", 500)

    return _ok({"processId": str(process_id), "status": draft.status, "steps": [s.model_dump() for s in draft.steps]})


@app.get("/api/v1/process/{process_id}")
async def get_draft_process(process_id: UUID, db: Session = Depends(get_db)):
    """根据 ID 获取 DraftProcessGraph。（Contract §5.2）"""
    svc = ProcessGenerationService(db)
    draft = svc.get_draft(process_id)
    if draft is None:
        raise _error("PROCESS_NOT_FOUND", f"未找到工艺: {process_id}", 404)

    return _ok(draft.model_dump())


# === 装配流程审核 (Epic-2 — 三阶段审核第二阶段) ===


@app.post("/api/v1/process/review")
async def submit_review(request: SubmitReviewRequest, db: Session = Depends(get_db)):
    """提交工程师审核决策。（三阶段审核 — 第二阶段）"""
    svc = ReviewService(db)
    try:
        approved_id, approved = svc.submit_review(request.processId, request.decisions)
        db.commit()
    except ProcessNotFoundError:
        db.rollback()
        raise _error("PROCESS_NOT_FOUND", f"未找到工艺: {request.processId}", 404)
    except ReviewRequiredError as e:
        db.rollback()
        raise _error("REVIEW_REQUIRED", str(e), 422)
    except InvalidReviewActionError as e:
        db.rollback()
        raise _error("INVALID_REVIEW_ACTION", str(e), 422)
    except Exception:
        db.rollback()
        raise _error("INTERNAL_SERVER_ERROR", "意外错误", 500)

    return _ok({
        "approvedProcessId": str(approved_id),
        "status": "approved",
    })


@app.get("/api/v1/approved-process/{approved_process_id}")
async def get_approved_process(approved_process_id: UUID, db: Session = Depends(get_db)):
    """根据 ID 获取 ApprovedProcessGraph。（Contract §6.2）"""
    svc = ReviewService(db)
    approved = svc.get_approved(approved_process_id)
    if approved is None:
        raise _error("APPROVED_PROCESS_NOT_FOUND", f"未找到已审核工艺: {approved_process_id}", 404)

    return _ok(approved.model_dump())


# === 指导书 (Epic-3) ===


@app.post("/api/v1/instruction/render")
async def render_instruction(request: RenderInstructionRequest, db: Session = Depends(get_db)):
    """从 ApprovedProcessGraph 渲染 AssemblyInstruction。（Contract §7.1）"""
    svc = InstructionService(db)
    try:
        instruction_id, instruction = svc.render(request.approvedProcessId, mode=request.mode)
        db.commit()
    except InstructionApprovedNotFoundError:
        db.rollback()
        raise _error("APPROVED_PROCESS_NOT_FOUND", f"未找到已审核工艺: {request.approvedProcessId}", 404)
    except RenderFailedError as e:
        db.rollback()
        raise _error("RENDER_FAILED", str(e), 500)
    except Exception:
        db.rollback()
        raise _error("INTERNAL_SERVER_ERROR", "意外错误", 500)

    return _ok({"instructionId": str(instruction_id)})


@app.post("/api/v1/instruction/render-stream")
async def render_instruction_stream(request: RenderInstructionRequest, db: Session = Depends(get_db)):
    """流式渲染 AssemblyInstruction，逐步返回进度。（SSE）"""
    import json as _json

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


@app.get("/api/v1/instruction/{instruction_id}")
async def get_instruction(instruction_id: UUID, db: Session = Depends(get_db)):
    """根据 ID 获取 AssemblyInstruction。（Contract §7.2）"""
    svc = InstructionService(db)
    instruction = svc.get_instruction(instruction_id)
    if instruction is None:
        raise _error("INSTRUCTION_NOT_FOUND", f"未找到指导书: {instruction_id}", 404)

    return _ok(instruction.model_dump())


@app.post("/api/v1/instruction/review")
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
        # 重新渲染指导书（重新生成图片）
        try:
            # 查找关联的 ApprovedProcess
            from .repositories.instruction_repository import InstructionRepository
            repo = InstructionRepository(db)
            ai = repo.get_by_id(request.instructionId)
            if ai is None:
                raise _error("INSTRUCTION_NOT_FOUND", f"未找到指导书: {request.instructionId}", 404)
            approved_id = UUID(ai.approved_process_id)
            # 重新渲染
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


# === PDF 导出 (Epic-3) ===


@app.post("/api/v1/instruction/export-pdf")
async def export_pdf(request: ExportPdfRequest, db: Session = Depends(get_db)):
    """将 AssemblyInstruction 导出为 PDF。（Contract §8.1）"""
    svc = InstructionService(db)
    try:
        pdf_path = svc.export_pdf(request.instructionId)
        db.commit()
    except InstructionNotFoundError:
        db.rollback()
        raise _error("INSTRUCTION_NOT_FOUND", f"未找到指导书: {request.instructionId}", 404)
    except PDFExportFailedError as e:
        db.rollback()
        raise _error("PDF_EXPORT_FAILED", str(e), 500)
    except Exception:
        db.rollback()
        raise _error("INTERNAL_SERVER_ERROR", "意外错误", 500)

    return _ok({"pdfPath": pdf_path})


@app.get("/api/v1/instruction/{instruction_id}/download-pdf")
async def download_pdf(instruction_id: UUID, db: Session = Depends(get_db)):
    """通过浏览器下载 PDF 文件。"""
    from .repositories.instruction_repository import InstructionRepository
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


# === BOM 库管理 ===

@app.get("/api/v1/bom/stats")
async def bom_stats():
    """获取 BOM 库统计信息。"""
    from .services.bom_library import get_bom_stats
    return _ok(get_bom_stats())


@app.get("/api/v1/bom/export")
async def bom_export():
    """导出完整 BOM 库为 JSON。"""
    from .services.bom_library import export_bom_json
    return _ok(export_bom_json())


@app.post("/api/v1/bom/import")
async def bom_import(file: UploadFile = File(...)):
    """导入 BOM 库 JSON 文件。"""
    from .services.bom_library import import_bom_json
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
        stats = import_bom_json(data)
        return _ok({"imported": stats, "filename": file.filename})
    except json.JSONDecodeError:
        raise _error("INVALID_JSON", "文件不是有效的 JSON 格式", 422)
    except Exception as e:
        raise _error("IMPORT_FAILED", f"导入失败: {e}", 500)


@app.post("/api/v1/bom/generate-from-step")
async def bom_generate_from_step(file: UploadFile = File(...)):
    """从 STEP 文件自动生成 BOM 库数据。"""
    from .services.bom_library import generate_bom_from_step, import_bom_json
    try:
        content = await file.read()
        step_text = content.decode("utf-8", errors="replace")
        bom_data = generate_bom_from_step(step_text)
        # 自动导入生成的数据
        stats = import_bom_json(bom_data)
        return _ok({
            "generated": len(bom_data.get("standard_parts", [])),
            "imported": stats,
            "bom_data": bom_data,
        })
    except Exception as e:
        raise _error("GENERATE_FAILED", f"生成失败: {e}", 500)
