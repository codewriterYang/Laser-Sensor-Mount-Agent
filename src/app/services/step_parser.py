"""Lightweight ISO 10303-21 entity parser for MVP.

Extracts product structure from STEP AP214 files without full geometry parsing.
Handles both single-part and assembly files.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class StepEntity:
    """Parsed STEP entity: {id: int, type: str, attributes: str}."""
    id: int
    type: str
    attributes: str


@dataclass
class ParsedProduct:
    """Extracted product structure from a STEP file."""
    name: str = "Unknown"
    schema: str = ""
    body_count: int = 0
    is_assembly: bool = False
    sub_components: list[str] = field(default_factory=list)


def parse_step_file(file_path: str | Path) -> ParsedProduct:
    """Parse a STEP file and extract product structure.

    Reads ISO 10303-21 format (STEP AP203/AP214).
    Handles files up to ~200K entities.

    Returns a ParsedProduct with name, body count, and component info.
    """
    path = Path(file_path)
    content = path.read_text(encoding="utf-8", errors="replace")

    result = ParsedProduct()

    # Extract schema
    schema_match = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", content)
    if schema_match:
        result.schema = schema_match.group(1)

    # Find PRODUCT entity — this is the root product name
    # Format: #NNN = PRODUCT ( 'id', 'name', 'description', ( #context ) ) ;
    product_match = re.search(r"#\d+\s*=\s*PRODUCT\s*\(\s*'([^']*)'\s*,\s*'([^']*)'", content)
    if product_match:
        result.name = product_match.group(2) or product_match.group(1)

    # Count MANIFOLD_SOLID_BREP entities — each represents a physical body
    result.body_count = len(re.findall(r"=\s*MANIFOLD_SOLID_BREP\s*\(", content))

    # Check for NEXT_ASSEMBLY_USAGE_OCCURRENCE — indicates assembly structure
    assembly_count = len(re.findall(r"=\s*NEXT_ASSEMBLY_USAGE_OCCURRENCE\s*\(", content))
    result.is_assembly = assembly_count > 0

    # Extract sub-component names if assembly
    if result.is_assembly:
        # Find all PRODUCT_DEFINITION_FORMATION entities that reference different PRODUCTs
        # For now, enumerate body groups as named parts
        for i in range(result.body_count):
            result.sub_components.append(f"Component_{i+1}")

    return result


def parse_step_bytes(content: bytes) -> ParsedProduct:
    """Parse STEP content from bytes (for UploadFile)."""
    text = content.decode("utf-8", errors="replace")
    result = ParsedProduct()

    schema_match = re.search(r"FILE_SCHEMA\s*\(\s*\(\s*'([^']+)'", text)
    if schema_match:
        result.schema = schema_match.group(1)

    product_match = re.search(r"#\d+\s*=\s*PRODUCT\s*\(\s*'([^']*)'\s*,\s*'([^']*)'", text)
    if product_match:
        result.name = product_match.group(2) or product_match.group(1)

    result.body_count = len(re.findall(r"=\s*MANIFOLD_SOLID_BREP\s*\(", text))
    assembly_count = len(re.findall(r"=\s*NEXT_ASSEMBLY_USAGE_OCCURRENCE\s*\(", text))
    result.is_assembly = assembly_count > 0

    # For single-part files: create one part per body, or just one part
    if result.body_count == 0:
        result.body_count = 1  # At least one implicit body

    for i in range(result.body_count):
        label = f"Body_{i+1}" if result.body_count > 1 else result.name
        result.sub_components.append(label)

    return result
