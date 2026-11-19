# Phase 3 report — PCB file import

## What was delivered

- **Content validation** (`app/file_processing/file_validator.py`): detects Gerber RS-274X and Excellon by content, not just by file extension. ZIP bundles are detected from their signature. Empty, binary and unrelated files are rejected with a clear reason.
- **Real Gerbonara parsers** (`gerber_parser.py`, `excellon_parser.py`): Gerber flashes, lines, arcs and regions become Shapely geometry with millimetre coordinates. Excellon hits become circular drill geometry; tool diameters and hit counts are extracted.
- **Layer classification** (`layer_classifier.py`): 14 roles (copper, mask, silk, paste, outline, plated/non-plated drill, etc.) with confidence scores and reasons. Excellon content always takes precedence over ambiguous filenames.
- **Import service** (`app/services/import_service.py`): expands a selection of files, folders and ZIP bundles; sanitises ZIP entry names to prevent path traversal; copies files into the project untouched; validates, classifies, parses and stores metadata in `project.json`. It can re-parse a project on demand and apply manual role overrides.
- **File manager UI** (`app/ui/pages/file_manager.py`): file, folder and ZIP buttons, drag-and-drop, a result dialog that reports accepted/skipped files with detected roles, a layer role column with manual override, and confidence tooltips.
- **Sample project** (`resources/sample_projects/simple_board/`): real, hand-authored RS-274X Gerber and Excellon files: front/back copper, solder mask, board outline, PTH and NPTH drills. The files parse with Gerbonara and contain non-trivial geometry (traces, pads, a 12 × 12 mm outline, three plated and one non-plated hole).

## Verification

`.\.venv\Scripts\python -m pytest -q` → **16 passed** (8 from Phase 2, 8 new Phase 3 tests).

The new tests cover validation of the real sample files, rejection of empty/binary/non-PCB content, layer rules, Gerber geometry extraction, Excellon drill/tool extraction, a full folder import with metadata persistence and manual override, ZIP name sanitisation, and invalid-file reporting.

## Known limitations

- Gerber polarity changes, aperture macros and region holes are approximated; the current viewer-oriented geometry model keeps flashes, lines, arcs and a region bounding box. This is sufficient for preview and CAM hand-off but not for manufacturing-grade DRC.
- Excellon slots are reported as drill hits at the slot start; slot walls are not yet modelled.
- The `LayerStack` helper from Gerbonara needs a full fab layer set and is not used; our classifier deliberately works with partial layer sets.
- Manual role overrides are stored in metadata; the original files are never renamed or modified.
- Hardware, CAM and G-code remain untested at this stage (Phases 5–8).
