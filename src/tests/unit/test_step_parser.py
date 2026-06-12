"""Unit tests for StepParser — real ISO 10303-21 parsing."""

from __future__ import annotations

from src.app.services.step_parser import parse_step_bytes


# Minimal valid STEP file content (AP214 single part)
MINIMAL_STEP = b"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION (( 'STEP AP214' ), '1' );
FILE_NAME ('test_part.STEP', '2025-01-01', ( '' ), ( '' ), 'SolidWorks', '', '' );
FILE_SCHEMA (( 'AUTOMOTIVE_DESIGN' ));
ENDSEC;
DATA;
#1 = PRODUCT ( 'test_id', 'TestPart', '', ( #100 ) ) ;
#2 = CARTESIAN_POINT ( 'NONE', ( 0.0, 0.0, 0.0 ) ) ;
#3 = MANIFOLD_SOLID_BREP ( 'NONE', #200 ) ;
#100 = PRODUCT_CONTEXT ( 'NONE', #999, 'mechanical' ) ;
#200 = CLOSED_SHELL ( 'NONE', ( #300 ) ) ;
#300 = ADVANCED_FACE ( 'NONE', ( #400 ), #500, .T. ) ;
#400 = FACE_OUTER_BOUND ( 'NONE', #600, .T. ) ;
#500 = PLANE ( 'NONE', #700 ) ;
#600 = EDGE_LOOP ( 'NONE', ( #800 ) ) ;
#700 = AXIS2_PLACEMENT_3D ( 'NONE', #2, #900, #1000 ) ;
#800 = ORIENTED_EDGE ( 'NONE', *, *, #1100, .T. ) ;
#900 = DIRECTION ( 'NONE', ( 0.0, 0.0, 1.0 ) ) ;
#1000 = DIRECTION ( 'NONE', ( 1.0, 0.0, 0.0 ) ) ;
#1100 = EDGE_CURVE ( 'NONE', #1200, #1300, #1400, .T. ) ;
#1200 = VERTEX_POINT ( 'NONE', #2 ) ;
#1300 = VERTEX_POINT ( 'NONE', #2 ) ;
#1400 = LINE ( 'NONE', #2, #1500 ) ;
#1500 = VECTOR ( 'NONE', #900, 1.0 ) ;
#999 = APPLICATION_CONTEXT ( 'mechanical design' ) ;
ENDSEC;
END-ISO-10303-21;"""


class TestStepParser:
    """Tests for lightweight STEP product structure extraction."""

    def test_parse_product_name(self):
        result = parse_step_bytes(MINIMAL_STEP)
        assert result.name == "TestPart"

    def test_parse_schema(self):
        result = parse_step_bytes(MINIMAL_STEP)
        assert result.schema == "AUTOMOTIVE_DESIGN"

    def test_parse_body_count(self):
        result = parse_step_bytes(MINIMAL_STEP)
        assert len(result.parts) == 1
        assert result.parts[0].body_count == 1

    def test_parse_is_not_assembly(self):
        result = parse_step_bytes(MINIMAL_STEP)
        assert result.is_assembly is False

    def test_parse_returns_default_for_empty(self):
        result = parse_step_bytes(b"garbage")
        assert result.name == "未知"
        assert len(result.parts) == 0  # No parts when no product found

    def test_parse_handles_assembly_with_next_assembly_usage(self):
        """NEXT_ASSEMBLY_USAGE_OCCURRENCE indicates an assembly file."""
        assembly_step = b"""ISO-10303-21;
HEADER;
FILE_DESCRIPTION (( 'STEP AP214' ), '1' );
FILE_NAME ('assembly.STEP', '', ( '' ), ( '' ), '', '', '' );
FILE_SCHEMA (( 'AUTOMOTIVE_DESIGN' ));
ENDSEC;
DATA;
#1 = PRODUCT ( 'assy', 'TestAssembly', '', ( #10 ) ) ;
#2 = NEXT_ASSEMBLY_USAGE_OCCURRENCE ( 'NAUO1', '', '', #3, #4, $ ) ;
#3 = PRODUCT_DEFINITION ( '', '', #5, #6 ) ;
#4 = PRODUCT ( 'part1', 'Part1', '', ( #10 ) ) ;
#5 = PRODUCT_DEFINITION_FORMATION_WITH_SPECIFIED_SOURCE ( '', '', #4, .NOT_KNOWN. ) ;
#6 = PRODUCT_DEFINITION_CONTEXT ( '', #7, '' ) ;
#7 = APPLICATION_CONTEXT ( '' ) ;
#10 = PRODUCT_CONTEXT ( '', #7, '' ) ;
ENDSEC;
END-ISO-10303-21;"""
        result = parse_step_bytes(assembly_step)
        assert result.name == "TestAssembly"
        assert result.is_assembly is True

    def test_parse_unknown_returns_default(self):
        result = parse_step_bytes(b"ISO-10303-21;\nDATA;\nENDSEC;\nEND-ISO-10303-21;")
        assert result.name == "未知"
