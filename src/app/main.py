"""FastAPI application — Laser Sensor Mount Assembly Agent.

All routes follow 05_CONTRACT.md.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
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

app = FastAPI(title="Laser Sensor Mount Assembly Agent", version="0.1.0")

# Static files for frontend
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/")
async def root():
    """Serve the frontend SPA."""
    return FileResponse(str(_static_dir / "index.html"))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Unwrap HTTPException.detail into direct JSON response body."""
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


# === STEP Analysis (Epic-1) ===


@app.post("/api/v1/step/analyze")
async def analyze_step(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a STEP file and generate a ProductGraph. (Contract §4.1)"""
    svc = StepAnalysisService(db)
    try:
        step_file_id, product_graph_id, status = svc.analyze(file)
        db.commit()
    except StepFileNotFoundError:
        db.rollback()
        raise _error("STEP_FILE_NOT_FOUND", f"File not found: {file.filename}", 404)
    except StepFileInvalidError:
        db.rollback()
        raise _error("STEP_FILE_INVALID", f"Invalid file type: {file.filename}", 422)
    except StepParseFailedError:
        db.rollback()
        raise _error("STEP_PARSE_FAILED", f"Failed to parse: {file.filename}", 500)
    except Exception:
        db.rollback()
        raise _error("INTERNAL_SERVER_ERROR", "Unexpected error", 500)

    return _ok({"stepFileId": str(step_file_id), "productGraphId": str(product_graph_id), "status": status})


@app.get("/api/v1/product-graphs/{product_graph_id}")
async def get_product_graph(product_graph_id: UUID, db: Session = Depends(get_db)):
    """Get a ProductGraph by ID. (Contract §4.2)"""
    repo = ProductGraphRepository(db)
    pg = repo.get_by_id(product_graph_id)
    if pg is None:
        raise _error("PRODUCT_GRAPH_NOT_FOUND", f"ProductGraph not found: {product_graph_id}", 404)

    graph_data = json.loads(pg.graph_json)
    return _ok(graph_data)


# === Process Generation (Epic-2) ===


@app.post("/api/v1/process/generate")
async def generate_process(request: GenerateProcessRequest, db: Session = Depends(get_db)):
    """Generate DraftProcessGraph from ProductGraph. (Contract §5.1)"""
    svc = ProcessGenerationService(db)
    try:
        process_id, draft = svc.generate(request.productGraphId)
        db.commit()
    except ProductGraphNotFoundError:
        db.rollback()
        raise _error("PRODUCT_GRAPH_NOT_FOUND", f"ProductGraph not found: {request.productGraphId}", 404)
    except ProcessGenerationFailedError as e:
        db.rollback()
        raise _error("PROCESS_GENERATION_FAILED", str(e), 500)
    except Exception:
        db.rollback()
        raise _error("INTERNAL_SERVER_ERROR", "Unexpected error", 500)

    return _ok({"processId": str(process_id), "status": draft.status, "steps": [s.model_dump() for s in draft.steps]})


@app.get("/api/v1/process/{process_id}")
async def get_draft_process(process_id: UUID, db: Session = Depends(get_db)):
    """Get a DraftProcessGraph by ID. (Contract §5.2)"""
    svc = ProcessGenerationService(db)
    draft = svc.get_draft(process_id)
    if draft is None:
        raise _error("PROCESS_NOT_FOUND", f"Process not found: {process_id}", 404)

    return _ok(draft.model_dump())


# === Review (Epic-2) ===


@app.post("/api/v1/process/review")
async def submit_review(request: SubmitReviewRequest, db: Session = Depends(get_db)):
    """Submit engineer review decisions. (Contract §6.1)"""
    svc = ReviewService(db)
    try:
        approved_id, approved = svc.submit_review(request.processId, request.decisions)
        db.commit()
    except ProcessNotFoundError:
        db.rollback()
        raise _error("PROCESS_NOT_FOUND", f"Process not found: {request.processId}", 404)
    except ReviewRequiredError as e:
        db.rollback()
        raise _error("REVIEW_REQUIRED", str(e), 422)
    except InvalidReviewActionError as e:
        db.rollback()
        raise _error("INVALID_REVIEW_ACTION", str(e), 422)
    except Exception:
        db.rollback()
        raise _error("INTERNAL_SERVER_ERROR", "Unexpected error", 500)

    return _ok({
        "approvedProcessId": str(approved_id),
        "status": "approved",
    })


@app.get("/api/v1/approved-process/{approved_process_id}")
async def get_approved_process(approved_process_id: UUID, db: Session = Depends(get_db)):
    """Get an ApprovedProcessGraph by ID. (Contract §6.2)"""
    svc = ReviewService(db)
    approved = svc.get_approved(approved_process_id)
    if approved is None:
        raise _error("APPROVED_PROCESS_NOT_FOUND", f"ApprovedProcess not found: {approved_process_id}", 404)

    return _ok(approved.model_dump())


# === Instruction (Epic-3) ===


@app.post("/api/v1/instruction/render")
async def render_instruction(request: RenderInstructionRequest, db: Session = Depends(get_db)):
    """Render an AssemblyInstruction from ApprovedProcessGraph. (Contract §7.1)"""
    svc = InstructionService(db)
    try:
        instruction_id, instruction = svc.render(request.approvedProcessId)
        db.commit()
    except InstructionApprovedNotFoundError:
        db.rollback()
        raise _error("APPROVED_PROCESS_NOT_FOUND", f"ApprovedProcess not found: {request.approvedProcessId}", 404)
    except RenderFailedError as e:
        db.rollback()
        raise _error("RENDER_FAILED", str(e), 500)
    except Exception:
        db.rollback()
        raise _error("INTERNAL_SERVER_ERROR", "Unexpected error", 500)

    return _ok({"instructionId": str(instruction_id)})


@app.get("/api/v1/instruction/{instruction_id}")
async def get_instruction(instruction_id: UUID, db: Session = Depends(get_db)):
    """Get an AssemblyInstruction by ID. (Contract §7.2)"""
    svc = InstructionService(db)
    instruction = svc.get_instruction(instruction_id)
    if instruction is None:
        raise _error("INSTRUCTION_NOT_FOUND", f"Instruction not found: {instruction_id}", 404)

    return _ok(instruction.model_dump())


# === PDF Export (Epic-3) ===


@app.post("/api/v1/instruction/export-pdf")
async def export_pdf(request: ExportPdfRequest, db: Session = Depends(get_db)):
    """Export AssemblyInstruction as PDF. (Contract §8.1)"""
    svc = InstructionService(db)
    try:
        pdf_path = svc.export_pdf(request.instructionId)
        db.commit()
    except InstructionNotFoundError:
        db.rollback()
        raise _error("INSTRUCTION_NOT_FOUND", f"Instruction not found: {request.instructionId}", 404)
    except PDFExportFailedError as e:
        db.rollback()
        raise _error("PDF_EXPORT_FAILED", str(e), 500)
    except Exception:
        db.rollback()
        raise _error("INTERNAL_SERVER_ERROR", "Unexpected error", 500)

    return _ok({"pdfPath": pdf_path})
