"""FastAPI application — Laser Sensor Mount Assembly Agent.

All routes follow 05_CONTRACT.md.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
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
from .services.step_analysis_service import (
    StepAnalysisService,
    StepFileInvalidError,
    StepFileNotFoundError,
    StepParseFailedError,
)

app = FastAPI(title="Laser Sensor Mount Assembly Agent", version="0.1.0")


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


# === Process Generation (Epic-2 — not implemented yet) ===


@app.post("/api/v1/process/generate")
async def generate_process(request: GenerateProcessRequest):
    """Generate DraftProcessGraph from ProductGraph. (Contract §5.1)"""
    raise HTTPException(status_code=501, detail="Not implemented")


@app.get("/api/v1/process/{process_id}")
async def get_draft_process(process_id: UUID):
    """Get a DraftProcessGraph by ID. (Contract §5.2)"""
    raise HTTPException(status_code=501, detail="Not implemented")


# === Review (Epic-2 — not implemented yet) ===


@app.post("/api/v1/process/review")
async def submit_review(request: SubmitReviewRequest):
    """Submit engineer review decisions. (Contract §6.1)"""
    raise HTTPException(status_code=501, detail="Not implemented")


@app.get("/api/v1/approved-process/{approved_process_id}")
async def get_approved_process(approved_process_id: UUID):
    """Get an ApprovedProcessGraph by ID. (Contract §6.2)"""
    raise HTTPException(status_code=501, detail="Not implemented")


# === Instruction (Epic-3 — not implemented yet) ===


@app.post("/api/v1/instruction/render")
async def render_instruction(request: RenderInstructionRequest):
    """Render an AssemblyInstruction from ApprovedProcessGraph. (Contract §7.1)"""
    raise HTTPException(status_code=501, detail="Not implemented")


@app.get("/api/v1/instruction/{instruction_id}")
async def get_instruction(instruction_id: UUID):
    """Get an AssemblyInstruction by ID. (Contract §7.2)"""
    raise HTTPException(status_code=501, detail="Not implemented")


# === PDF Export (Epic-3 — not implemented yet) ===


@app.post("/api/v1/instruction/export-pdf")
async def export_pdf(request: ExportPdfRequest):
    """Export AssemblyInstruction as PDF. (Contract §8.1)"""
    raise HTTPException(status_code=501, detail="Not implemented")
