# Development roadmap

Each phase ends with a testable deliverable and a commit. Major architecture changes require explicit approval.

## Phase 1 — Research and architecture ✅ Complete

- Investigated FlatCAM, UGS, grblHAL, KiCad, Gerbonara and alternatives.
- Verified licenses and runtime constraints.
- Selected a two-process architecture (PySide6 main app + FlatCAM headless worker).
- Deliverables: [research report](01_research_report.md), [architecture](02_architecture.md), [license plan](03_licensing.md), [interfaces](05_module_interfaces.md), [risks](06_risks_and_decisions.md).

## Phase 2 — Basic desktop application ✅ Complete

- Create Python 3.12 environment and dependency files.
- Implement `main.py`, application bootstrap, event bus, logging, settings, main window and navigation.
- Implement Dashboard, New Project and a basic File Manager shell (real upload behavior arrives in Phase 3).
- Deliverable: `python main.py` launches a professional-looking window with working navigation and project creation. See [Phase 2 report](07_phase2_report.md). Result: 8 tests passing.

## Phase 3 — PCB file import ✅ Complete

- Wire Gerbonara into `file_processing/gerber_parser.py` and `excellon_parser.py`.
- Implement content validation, duplicate detection, ZIP/folder import, layer classification and manual overrides.
- Add real sample Gerber/Excellon files to `resources/sample_projects/`.
- Deliverable: a project can be created, files imported, layers identified, and problems reported clearly. See [Phase 3 report](08_phase3_report.md). Result: 16 tests passing.

## Phase 4 — PCB visualization ✅ Complete

- Convert parsed geometry into Shapely/QGraphicsView items.
- Layer toggles, colors, zoom/pan/fit, measurements, dimensions and drill markers.
- Deliverable: real uploaded PCB geometry is displayed (no placeholder images). See [Phase 4 report](09_phase4_report.md). Result: 18 tests passing.

## Phase 5 — CAM engine integration ✅ Complete

- Build and validate the FlatCAM worker environment (Python 3.10).
- Implement `FlatcamAdapter` script generation, execution, timeout handling and result parsing.
- Implement isolation, drilling and outline operations with configurable parameters.
- Real FlatCAM integration produces non-empty G-code with safe modal/end codes.
- Deliverable: uploaded files produce real toolpaths and G-code through FlatCAM. See [Phase 5 report](10_phase5_report.md).

## Phase 6 — G-code generation, validation and preview ✅ Complete

- Normalize and validate FlatCAM G-code; add safe startup/end sequences where needed.
- Parser for movement reconstruction, bounds/time estimates, unsupported-command checks.
- Preview screen with rapid/cut/plunge colors, report and validated-copy export.
- Deliverable: generated G-code can be inspected and exported, but never auto-executed. See [Phase 6 report](11_phase6_report.md).

## Phase 7 — CNC communication ✅ Complete

- Serial port detection, connection settings, controller identification (`$I`, `$$`).
- Line-based streaming with 128-byte RX budget, `ok`/`error` handling, real-time commands, status polling, feed hold/resume/soft reset, jog, home, zero.
- Simulated controller and thread-safe job progress/history.
- Running a job requires a re-validated `*.validated.nc` copy and explicit confirmation.
- Deliverable: SmartDrill Pro executes a validated job against the simulator. See [Phase 7 report](12_phase7_report.md).

## Phase 8 — Hardware integration ⚠️ UNVERIFIED

- Editable machine profile, safety limits and controller identification UI.
- Hardware setup checklist for ESP32-S3/grblHAL.
- **No physical hardware was connected during development. Real machine behaviour is UNVERIFIED.**
- See [Phase 8 report](13_phase8_report.md) and [hardware setup checklist](14_hardware_setup.md).

## Phase 9 — Testing and packaging ✅ Complete

- Full test suite, sample projects, error recovery and offscreen UI smoke test.
- PyInstaller Windows build script, license and third-party notices.
- Deliverable: a working Windows desktop application workflow with documented build steps. See [Phase 9 report](15_phase9_report.md).

## Definition of "done" for a phase

- Code committed and pushed.
- Dependency/install instructions updated.
- At least one automated test or a documented manual verification exists.
- Known limitations recorded in the phase report.
