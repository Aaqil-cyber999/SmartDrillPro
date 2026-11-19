# Phase 9 report - Testing and packaging

## Delivered

- Full automated suite: `python -m pytest -q` - 35 tests pass, including the real FlatCAM worker integration test.
- `compileall` check over `app/`, `config/` and `main.py` passes.
- Offscreen `MainWindow` smoke test constructs all navigation pages, including Phase 8 Machine Configuration and Settings.
- `scripts/build_windows.ps1`: installs runtime/build requirements, runs the entire test suite, then builds `dist/SmartDrillPro` with PyInstaller. The FlatCAM worker and grblHAL firmware are intentionally not bundled.
- `requirements-build.txt`, `LICENSE`, `THIRD_PARTY_NOTICES.md` and `INSTALL.md` added.
- `README.md` and `docs/04_roadmap.md` updated to final status.

## Verification performed

- `.\.venv\Scripts\python -m pytest -q` - 35 passed.
- `.\.venv\Scripts\python -m pytest -q -m integration -s` - real FlatCAM output verified (`G21`, `G90`, `M30`, `G00 X`, `G01 Z`).
- `.\.venv\Scripts\python -m compileall -q app config main.py` - no errors.
- Offscreen UI smoke test - navigation and all pages instantiate successfully.

## Known limitations

- The PyInstaller executable build was not executed on this development machine; the script and dependencies are provided, but the final installer/artifact must be produced and smoke-tested on the target Windows machine.
- No signed installer is included. Code signing requires the release owner's certificate.
- Real ESP32-S3/grblHAL hardware remains UNVERIFIED; Phase 8 documents the required physical checks.
- Flash/firmware binaries and FlatCAM are separate by design to respect their licenses and to keep the main app small.
