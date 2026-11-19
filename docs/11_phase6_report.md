# Phase 6 report - G-code validation and preview

## Delivered

- `app/gcode/gcode_parser.py`: reconstructs modal position, units, feed, bounds, move counts and a line-numbered program list from real G-code.
- `app/gcode/gcode_validator.py`: errors on inch units, no motion, unsupported G/M commands, missing program end, travel/depth/feed violations; warns on arcs and on the UNVERIFIED machine profile.
- `app/gcode/gcode_normalizer.py`: writes a separate `*.validated.nc` copy with `G21/G90/G17/M5` startup and `M5/M30` shutdown. Inch programs are **rejected**, not silently converted; early `M30` is truncated and the copy is re-validated.
- `app/ui/widgets/gcode_preview.py`: QGraphicsView rendering of parsed rapid/cut/plunge segments.
- `app/ui/pages/gcode_preview.py`: file list, SAFE/NOT SAFE report, bounds/time/move counts, validated-copy creation, export. This page never sends commands to a machine.

## Verification

- 7 automated tests in `tests/test_gcode.py` cover parsing, inch/feed/unsupported-command/end-code validation, safe fixtures, normalizer safety, and real image-scene rendering.
- Full suite passes (35 tests including the real FlatCAM integration test).
- Manual UI path: import sample project -> CAM Processing -> Generate -> G-code Preview -> Load and validate -> Create validated copy. The original `.nc` remains unchanged.

## Known limitations

- Arc moves are approximated as straight chords in the 2D preview.
- Canned cycles and incremental subprograms are not expanded; unsupported commands are reported as errors rather than executed.
- Validation checks move endpoints, not the swept path between them; tool diameter and holder clearance are not modelled.
- Per-operation inspection (separate isolation/drill/outline views) is not implemented.
- FlatCAM's default postprocessor emits simple motion code; the wrapper adds modal/end codes, but all jobs must still be reviewed visually.
