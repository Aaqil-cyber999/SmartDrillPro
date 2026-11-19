# Phase 5 report - CAM engine integration

## Delivered

- `app/cam/cam_settings.py`: validated, persisted CAM parameters (tool diameters, depths, feeds, passes and operation toggles).
- `app/cam/flatcam_adapter.py`: builds a FlatCAM Tcl script from **real imported Gerber/Excellon files**, runs the gitignored FlatCAM 2024.4 worker in an isolated Python 3.10 environment and verifies that expected non-empty `.nc` files actually appear.
- `app/cam/cam_service.py`: plans isolation/drilling/outline operations from classified layers, saves parameters and records `cam_jobs` in the active project.
- `app/ui/pages/cam_processing.py`: PySide6 form and background `QThread`; generated output paths and worker logs are shown to the user.
- `tools/flatcam/` is vendored but gitignored; `ensure_resources()` compiles its Qt resources and applies small, idempotent headless fixes on first run:
  - make `write_gcode` synchronous and export via a Qt timer once the asynchronous CNCJob object exists;
  - skip headless-only plotting geometry;
  - fix FlatCAM's `check_zcut()` returning `None` for negative depths in Tcl mode.
- Worker logs are redirected to files so FlatCAM's offscreen Qt warnings cannot fill the OS pipe buffer and stall the child process.
- Generated files receive an explicit `G21`/`G90` preamble and `M30` postamble from the Tcl script. No motion is hardcoded by SmartDrill Pro.

## Verification

- `python -m pytest -q -m "not integration"` - 34 non-integration tests pass at final Phase 9 check.
- Real FlatCAM integration: `python -m pytest -q -m integration -s` passes; a real `PTH.drl` import produces a 446-byte `drill.nc` containing `G21`, `G90`, `M30`, `G00 X`, `G01 Z` and the three drilled holes from the sample file.
- The worker is terminated as soon as expected outputs exist, avoiding a full 300-second timeout.

## Known limitations

- FlatCAM and its Python 3.10 environment are intentionally not committed. A fresh checkout must fetch FlatCAM 2024.4 and create `.venv-flatcam`; see `README.md`.
- Source patches are literal string replacements tied to FlatCAM 2024.4 and must be reviewed after upgrading the vendored engine.
- Only the first classified top/bottom copper layer and first outline are used; dual-side and multi-tool jobs are not supported yet.
- CAM settings are not automatically cross-checked against the active machine profile; G-code Preview performs that check.
- No cancel button for a running CAM job; the worker has a timeout and terminate/kill fallback.
