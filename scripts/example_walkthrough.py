"""Run the full example workflow without touching any machine hardware.

This uses the real importer, the real FlatCAM worker and the real validator.
It only prints results; it never connects to or streams G-code to a controller.
"""

from __future__ import annotations

from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.application import Application
from app.gcode.gcode_normalizer import normalize_gcode, validated_copy_path
from app.gcode.gcode_parser import parse_gcode
from app.gcode.gcode_validator import validate_gcode

SAMPLE_ZIP = ROOT / "resources" / "sample_projects" / "simple_board" / "simple_board_gbr.zip"
DEMO_DIR = ROOT / "data" / "example_walkthrough"


def main() -> int:
    if not SAMPLE_ZIP.is_file():
        print(f"Missing example ZIP: {SAMPLE_ZIP}")
        return 1

    if DEMO_DIR.exists():
        shutil.rmtree(DEMO_DIR)
    DEMO_DIR.mkdir(parents=True)

    core = Application(data_dir=DEMO_DIR, simulation=True)
    core.initialize()
    project, project_dir = core.projects.create_project("Example Board")

    print("=" * 68)
    print("STEP 1 - Import KiCad manufacturing files")
    print("=" * 68)
    print(f"Input: {SAMPLE_ZIP.name}")
    outcome = core.importer.import_paths([SAMPLE_ZIP])
    if outcome.errors:
        print("Import errors:")
        for error in outcome.errors:
            print(f"  - {error}")
        return 1
    print(f"Added {len(outcome.added)} files:")
    for record in outcome.added:
        print(f"  - {record.name}")
    print("Detected layers:")
    for layer in project.layers:
        print(
            f"  - {layer['file']}: {layer['role']} "
            f"(confidence {layer['confidence']})"
        )

    print()
    print("=" * 68)
    print("STEP 2 - Generate real G-code with FlatCAM")
    print("=" * 68)
    result = core.cam.run(timeout_s=300)
    if not result.success:
        print("CAM failed:")
        for error in result.errors:
            print(f"  - {error}")
        return 1
    gcode_dir = project_dir / "generated" / "gcode"
    generated = sorted(
        path for path in gcode_dir.glob("*.nc")
        if not path.name.endswith(".validated.nc")
    )
    for path in generated:
        print(f"  - {path.name}: {path.stat().st_size} bytes")

    print()
    print("=" * 68)
    print("STEP 3 - Validate and create *.validated.nc copies")
    print("=" * 68)
    for path in generated:
        text = path.read_text(encoding="utf-8", errors="replace")
        report = validate_gcode(
            parse_gcode(text, path.name), core.settings, core.active_profile
        )
        status = "SAFE" if report.safe else "NOT SAFE"
        print(f"  - {path.name}: {status}, {len(report.errors)} error(s)")
        if not report.safe:
            for issue in report.errors:
                print(f"      {issue.message}")
            continue
        normalized = normalize_gcode(text)
        rechecked = validate_gcode(
            parse_gcode(normalized, path.name), core.settings, core.active_profile
        )
        if not rechecked.safe:
            print(f"      normalized copy failed re-validation: {rechecked.errors}")
            continue
        target = path.with_name(validated_copy_path(path.name))
        target.write_text(normalized, encoding="utf-8")
        print(f"      -> {target.name} ({len(normalized.splitlines())} lines)")

    validated = sorted(gcode_dir.glob("*.validated.nc"))
    if validated:
        sample = validated[0]
        print()
        print(f"Example of {sample.name} (first 12 lines):")
        for line in sample.read_text(encoding="utf-8").splitlines()[:12]:
            print(f"  | {line}")

    print()
    print("=" * 68)
    print("DONE - no machine was connected and no job was sent")
    print("=" * 68)
    print(f"Project and generated files: {project_dir}")
    print("Machine Control only accepts a *.validated.nc copy after explicit confirmation.")
    core.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
