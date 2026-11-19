# Phase 2 report — Basic desktop application

## What was built

A launchable PySide6 desktop application with:

- `main.py` entry point with `--data-dir` and `--simulate` options.
- `Application` composition root: settings, logging, event bus, project manager, machine profiles.
- `MainWindow` with the full ten-item professional navigation and an industrial dark theme.
- Dashboard with the 10-step workflow and an explicit safety banner.
- **Working** project creation, saving, listing and opening.
- **Working** basic file manager: multi-file browse, copy into `project/source/`, duplicate detection by SHA-256 and filename, removal, and clear result messages.
- Honest placeholder screens for Phases 4-9 (no fake PCB images or G-code).
- Tests for configuration, events, projects, duplicate detection and an offscreen UI smoke test.

## Why

This phase establishes the architecture before any manufacturing logic is added: UI, core services, models and configuration are separate, so later phases can add parsing/CAM/machine modules without restructuring the application.

## Install and run

```powershell
# Python 3.12 is required
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python main.py
```

Useful options:

```powershell
.\.venv\Scripts\python main.py --simulate
.\.venv\Scripts\python main.py --data-dir "C:\temp\smartdrill-data"
```

Tests:

```powershell
.\.venv\Scripts\python -m pytest -q
```

Result on 2026-11-19: **8 passed** (including the offscreen window/navigation test).

## Files created

```
main.py, pyproject.toml, requirements.txt, .gitignore
config/application_config.py, default_settings.py, machine_profiles.py
app/core/application.py, event_manager.py, logging_manager.py, project_manager.py
app/models/pcb_project.py
app/ui/main_window.py
app/ui/pages/dashboard.py, project_page.py, file_manager.py, placeholder.py
resources/styles/app.qss
tests/test_core.py, tests/test_ui_smoke.py
docs/07_phase2_report.md
```

## Known limitations (intentional for Phase 2)

- File import checks extensions and hashes only; **no content validation** yet (Phase 3).
- Files are not classified into PCB layers yet (Phase 3).
- No PCB rendering, CAM, G-code or machine communication yet (Phases 4-7).
- ZIP/folder/drag-and-drop import and project metadata editing are planned for Phase 3.
- Settings page is a placeholder; settings are currently read from/written to `settings.json` by the core.
- Imported files are copied, not moved; originals on disk are never modified.

## Dependency note

`PySide6-Essentials` + `PySide6-Addons` are installed instead of the full `PySide6` meta-package. They contain QtWidgets, QtCore and QtGui used by this app and avoid a 131 MB WebEngine download that SmartDrill Pro does not need.
