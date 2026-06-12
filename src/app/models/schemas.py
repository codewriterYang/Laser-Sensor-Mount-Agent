"""Pydantic schemas matching 05_CONTRACT.md."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# --- Standard Response Wrappers ---

class StandardResponse(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ErrorResponse(BaseModel):
    success: bool = False
    error: dict[str, str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# --- STEP Analysis ---

class AnalyzeStepRequest(BaseModel):
    fileName: str


class AnalyzeStepData(BaseModel):
    stepFileId: UUID
    productGraphId: UUID
    status: str


# --- ProductGraph ---

class NodeSchema(BaseModel):
    nodeId: UUID = Field(default_factory=uuid4)
    nodeType: str  # "assembly" | "part"
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EdgeSchema(BaseModel):
    edgeId: UUID = Field(default_factory=uuid4)
    source: UUID
    target: UUID
    relation: str  # "contains" | "attached_to" | "fastened_by"


class ProductGraphSchema(BaseModel):
    graphId: UUID
    nodes: list[NodeSchema] = Field(default_factory=list)
    edges: list[EdgeSchema] = Field(default_factory=list)


# --- DraftProcessGraph ---

class StepSchema(BaseModel):
    stepId: UUID = Field(default_factory=uuid4)
    sequence: int
    title: str
    description: str
    requiredParts: list[str] = Field(default_factory=list)
    requiredTools: list[str] = Field(default_factory=list)


class DraftProcessGraphSchema(BaseModel):
    processId: UUID
    status: str = "draft"  # draft | reviewing | approved | rejected
    steps: list[StepSchema] = Field(default_factory=list)


class GenerateProcessRequest(BaseModel):
    productGraphId: UUID


class GenerateProcessData(BaseModel):
    processId: UUID
    status: str
    steps: list[StepSchema] = Field(default_factory=list)


# --- Review ---

class ReviewDecisionSchema(BaseModel):
    stepId: UUID
    action: str  # accept | modify | delete | insert
    reason: str


class SubmitReviewRequest(BaseModel):
    processId: UUID
    decisions: list[ReviewDecisionSchema]


class SubmitReviewData(BaseModel):
    approvedProcessId: UUID
    status: str


# --- ApprovedProcessGraph ---

class ApprovedProcessGraphSchema(BaseModel):
    approvedProcessId: UUID
    approvedBy: str
    approvedAt: datetime
    steps: list[StepSchema] = Field(default_factory=list)


# --- Instruction ---

class RenderInstructionRequest(BaseModel):
    approvedProcessId: UUID


class RenderInstructionData(BaseModel):
    instructionId: UUID


class SectionSchema(BaseModel):
    sectionType: str  # cover | overview | step | safety | ending
    content: str


class AssemblyInstructionSchema(BaseModel):
    instructionId: UUID
    title: str = ""
    sections: list[SectionSchema] = Field(default_factory=list)


# --- PDF Export ---

class ExportPdfRequest(BaseModel):
    instructionId: UUID


class ExportPdfData(BaseModel):
    pdfPath: str
