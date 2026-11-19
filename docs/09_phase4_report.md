# Phase 4 report — PCB visualization

## What was delivered

- `app/ui/widgets/pcb_view.py`: a `QGraphicsView`/`QGraphicsScene` renderer. Shapely polygons produced by the Phase 3 parsers are converted to Qt polygons; the Gerber Y axis is inverted and coordinates are scaled to 20 scene units per millimetre.
- Layer colours and opacity by manufacturing role (copper, mask, silk, paste, outline, plated/non-plated drills). Interior polygon rings are cut out using the scene background colour.
- Interactions: mouse-wheel zoom, drag-to-pan, fit-to-view, zoom buttons, per-layer visibility checkboxes, and a two-click measurement tool that reports millimetres.
- A board area label derived from the actual parsed geometry bounds (no placeholder image or hardcoded board size).
- `app/ui/pages/pcb_viewer.py`: the real viewer replaces the Phase 4 placeholder in navigation. It reloads geometry whenever files, layer roles or the active project change.

## Verification

`.\.venv\Scripts\python -m pytest -q` → **18 passed**.

New visualization tests verify that real sampled Gerber geometry becomes non-empty Qt polygon items, that an imported project renders one item group per parsed file, that the dimension label reflects real bounds, that layer visibility toggles work, and that measurement mode can be switched. The existing offscreen main-window smoke test now opens the real viewer page.

## Known limitations

- Gerber region holes are approximated from their bounding box in the parser, so complex negative polygons are not pixel-perfect.
- Complex aperture macros are rendered as generic small circles until aperture-macro support is added to the parser.
- Measurement is screen-space Euclidean distance after scaling; it does not snap to features.
- Rendering performance has only been checked with the small sample board; large fab outputs with hundreds of thousands of flashes have not been benchmarked.
