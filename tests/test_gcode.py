"""Phase 6 tests: G-code parsing, validation and normalization."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.gcode.gcode_normalizer import normalize_gcode, validated_copy_path
from app.gcode.gcode_parser import parse_gcode
from app.gcode.gcode_validator import validate_gcode
from config.default_settings import AppSettings
from config.machine_profiles import MachineProfile

SAMPLE_GCODE = """(FlatCAM-style fixture - parser test only)
G21
G90
G0 X0 Y0 Z2
M3 S1000
G1 X10 Y5 F120
G1 Z-0.1 F100
G1 X20 Y5 F120
G0 Z2
M5
M30
"""


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_parser_tracks_absolute_millimetre_moves():
    parsed = parse_gcode(SAMPLE_GCODE, "fixture.nc")
    assert parsed.units == "mm"
    assert parsed.line_count == 11
    kinds = [move.kind for move in parsed.moves]
    assert "rapid" in kinds and "cut" in kinds and "plunge" in kinds
    assert parsed.bounds == (0.0, 0.0, 20.0, 5.0)
    assert parsed.moves[0].end == (0.0, 0.0, 2.0)


def test_validator_flags_inch_units_and_excessive_feed():
    bad = "G20\nG90\nG1 X10 Y10 F5000\nM30\n"
    report = validate_gcode(parse_gcode(bad), AppSettings(), MachineProfile(name="test"))
    assert not report.safe
    assert any("inch units" in issue.message.lower() for issue in report.errors)


def test_validator_flags_unsupported_commands_and_missing_end():
    bad = "G21\nG81 X10 Y10 Z-1 F100\nM30\n"
    report = validate_gcode(parse_gcode(bad), AppSettings(), MachineProfile(name="test"))
    assert any("G81" in issue.message for issue in report.errors)
    no_end = validate_gcode(parse_gcode("G21\nG1 X1 F100\n"), AppSettings(), MachineProfile(name="test"))
    assert any("end command" in issue.message for issue in no_end.errors)


def test_validator_accepts_safe_fixture():
    report = validate_gcode(parse_gcode(SAMPLE_GCODE), AppSettings(), MachineProfile(name="test"))
    assert report.safe, [issue.message for issue in report.errors]
    assert report.estimated_time_s > 0
    assert any("UNVERIFIED" in issue.message for issue in report.warnings)


def test_normalizer_adds_safe_header_and_footer():
    normalized = normalize_gcode("G1 X1 Y1 F100\n")
    assert normalized.startswith("(SmartDrill Pro validated copy")
    assert "G21" in normalized and "G90" in normalized
    assert normalized.strip().endswith("M30")
    assert validated_copy_path("job.nc") == "job.validated.nc"
    assert validated_copy_path("job.gcode") == "job.validated.nc"


def test_normalizer_rejects_inch_units_and_truncates_early_end():
    with pytest.raises(ValueError, match="inch units"):
        normalize_gcode("G20\nG1 X1 F100\nM30\n")
    normalized = normalize_gcode("G1 X1 F100\nM30\nG1 X2 F100\n")
    assert normalized.count("M30") == 1
    assert "X2" not in normalized


def test_preview_renders_real_parsed_moves(qapp):
    from app.ui.widgets.gcode_preview import GcodePreviewView

    parsed = parse_gcode(SAMPLE_GCODE)
    view = GcodePreviewView()
    view.set_gcode(parsed)
    assert len(view.scene.items()) == len(parsed.moves)
