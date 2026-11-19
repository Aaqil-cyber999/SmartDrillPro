# SMARTDRILL PRO

**PCB CNC Manufacturing and Machine Control Software**

SmartDrill Pro is one Windows desktop application that takes a PCB design's manufacturing files (Gerber and Excellon), prepares machining toolpaths with the real FlatCAM engine, generates and validates G-code, previews the toolpath, and streams a validated job to an ESP32-S3 controller running grblHAL.

The user works in one application. Mature open-source engines work behind the scenes: Gerbonara parses files, FlatCAM produces CAM toolpaths in an isolated Python 3.10 worker, and grblHAL runs on the separate controller.

> **SAFETY NOTICE:** This software controls real machinery. Software "stop" buttons are **not** a substitute for a properly designed hardware emergency-stop circuit. Always verify toolpaths, limits and machine state before cutting material. **No physical ESP32-S3/CNC hardware was tested during development; the machine profile and real hardware behaviour remain UNVERIFIED.**

## Current status

| Phase | Status |
| --- | --- |
| 1 — Technical investigation and architecture | Complete |
| 2 — Basic desktop application | Complete ([report](docs/07_phase2_report.md)) |
| 3 — PCB file import | Complete ([report](docs/08_phase3_report.md)) |
| 4 — PCB visualization | Complete ([report](docs/09_phase4_report.md)) |
| 5 — CAM engine integration | Complete ([report](docs/10_phase5_report.md)) |
| 6 — G-code generation and validation | Complete ([report](docs/11_phase6_report.md)) |
| 7 — CNC communication (simulation first) | Complete ([report](docs/12_phase7_report.md)) |
| 8 — Hardware integration | UNVERIFIED ([report](docs/13_phase8_report.md)) |
| 9 — Testing and packaging | Complete ([report](docs/15_phase9_report.md)) |

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py
```

Real CAM requires the separate FlatCAM worker described in [INSTALL.md](INSTALL.md). Without it the app still imports, views and inspects files, but cannot produce toolpaths.

## Documentation

- [Installation](INSTALL.md)
- [Technical research report](docs/01_research_report.md)
- [Software architecture](docs/02_architecture.md)
- [License compliance plan](docs/03_licensing.md)
- [Development roadmap](docs/04_roadmap.md)
- [Module interfaces](docs/05_module_interfaces.md)
- [Technical decisions and risks](docs/06_risks_and_decisions.md)
- [Hardware setup checklist (UNVERIFIED)](docs/14_hardware_setup.md)
- [Third-party notices](THIRD_PARTY_NOTICES.md)

## Repository layout

```
config/          Application, default, safety and machine-profile configuration
app/core/        Application lifecycle, events, logging, projects
app/ui/          PySide6 main window, pages and reusable widgets
app/file_processing/  Gerber/Excellon import, validation, layer classification
app/cam/         CAM orchestration and FlatCAM worker adapter
app/gcode/       Parsing, validation, normalization and preview data
app/machine/     Serial transport, grblHAL interface, streaming, job control
app/models/      Project, layer, tool, job and machine-state data models
app/services/    Project/export/settings services
tests/           Unit and integration tests (simulated hardware)
resources/       Styles, icons, sample projects
data/            Local projects, generated output, logs (not committed)
docs/            Research, architecture, user and developer documentation
scripts/         Windows build helper
tools/flatcam/   Vendored FlatCAM 2024.4 worker (gitignored)
```

## Safety workflow

1. Import real Gerber/Excellon files and inspect them in PCB Viewer.
2. Generate G-code in CAM Processing using the FlatCAM worker.
3. In G-code Preview, load and validate the file, then create a `*.validated.nc` copy. Inch programs and unsupported commands are rejected.
4. In Machine Control, connect (simulation by default), select a validated copy, tick the confirmation checkbox, then run. Generated G-code is **never** auto-executed.
5. Machine Configuration stores measured calibration values but remains UNVERIFIED until checked on real hardware.

## Development environment

Python **3.12** runs the main application. The FlatCAM worker uses its own **Python 3.10** environment because FlatCAM 2024.4 pins Python 3.10 and PyQt5.

```powershell
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\python -m pytest -q -m integration -s
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```
