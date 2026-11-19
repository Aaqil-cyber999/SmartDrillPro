# SMARTDRILL PRO

**PCB CNC Manufacturing and Machine Control Software**

SmartDrill Pro is one desktop application that takes a PCB design's manufacturing files (Gerber and Excellon), prepares machining toolpaths, generates and validates G-code, and sends that G-code to an ESP32-S3 controller running grblHAL.

The user works in one application. The mature open-source engines (FlatCAM for CAM, Gerbonara for file parsing, grblHAL on the controller) work behind the scenes.

> **SAFETY NOTICE:** This software controls real machinery. Software "stop" buttons are **not** a substitute for a properly designed hardware emergency-stop circuit. Always verify toolpaths, limits, and machine state before cutting material.

## Current status

| Phase | Status |
| --- | --- |
| 1 – Technical investigation and architecture | Complete |
| 2 – Basic desktop application | Complete ([report](docs/07_phase2_report.md)) |
| 3 – PCB file import | Complete ([report](docs/08_phase3_report.md)) |
| 4 – PCB visualization | Complete ([report](docs/09_phase4_report.md)) |
| 5 – CAM engine integration | Not started |
| 6 – G-code generation and validation | Not started |
| 7 – CNC communication (simulation first) | Not started |
| 8 – Hardware integration | Not started |
| 9 – Testing and packaging | Not started |

## Documentation

- [Technical research report](docs/01_research_report.md)
- [Software architecture](docs/02_architecture.md)
- [License compliance plan](docs/03_licensing.md)
- [Development roadmap](docs/04_roadmap.md)
- [Module interfaces](docs/05_module_interfaces.md)
- [Technical decisions and risks](docs/06_risks_and_decisions.md)
- [Phase 2 report](docs/07_phase2_report.md)
- [Phase 3 report](docs/08_phase3_report.md)
- [Phase 4 report](docs/09_phase4_report.md)

## Repository layout

```
config/          Application, default and machine-profile configuration
app/core/        Application lifecycle, events, logging, projects
app/ui/          PySide6 main window, pages and reusable widgets
app/file_processing/  Gerber/Excellon import, validation, layer classification
app/cam/         CAM orchestration and FlatCAM worker adapter
app/gcode/       G-code generation, parsing, validation, preview data
app/machine/     Serial transport, grblHAL interface, streaming, job control
app/models/      Project, layer, tool, job and machine-state data models
app/services/    Project/export/settings services
tests/           Unit and integration tests (simulated hardware)
resources/       Styles, icons, sample projects
data/            Local projects, generated output, logs (not committed)
docs/            Research, architecture, user and developer documentation
```

## Development environment

Python **3.12** is recommended for the main application. The FlatCAM worker uses its own **Python 3.10** environment because FlatCAM 2024.4 pins Python 3.10 and PyQt5.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py
```

See the roadmap and architecture documents for the full setup and the intended staged workflow.
