# Technical research report — Phase 1

Date: 2026-11-19. All findings below were checked against the upstream repositories/sites on that date.

## 1. What problem are we solving?

PCB manufacturing with a CNC machine normally needs several separate programs:

1. A CAD tool (KiCad) exports **Gerber** files (copper, mask, silkscreen, outline) and **Excellon** files (drill holes).
2. A CAM program (FlatCAM) turns those files into **toolpaths** and **G-code**.
3. A G-code sender (UGS) talks to the controller over USB serial.
4. Firmware (grblHAL) turns G-code into step/direction signals for the stepper drivers.

SmartDrill Pro does **not** rewrite these engines. It owns the workflow, the UI, the project files, the validation, and the machine-control interface, and orchestrates the engines underneath.

A useful analogy: FlatCAM is the "calculator" that works out where the tool must move, grblHAL is the "machine driver", and SmartDrill Pro is the "cockpit" that presents everything safely to the operator.

## 2. KiCad (optional upstream design tool)

- Project: https://www.kicad.org/ — source: https://gitlab.com/kicad/code/kicad — license: GPL-3.0-or-later (with specific exceptions).
- KiCad is a **PCB design** tool, not a CAM tool. The user may use it, but SmartDrill Pro only consumes its exported manufacturing files.
- The `kicad-cli` command-line tool can export files without opening the GUI:
  - `kicad-cli pcb export gerbers -o OUT board.kicad_pcb`
  - `kicad-cli pcb export drill -o OUT --format excellon board.kicad_pcb`
  - Options include `--layers F.Cu,B.Cu`, `--excellon-units mm|in`, `--drill-origin absolute|plot`.
  - Source: https://docs.kicad.org/master/en/cli/cli.html
- **Decision:** Do not import KiCad or its file formats into the main app. Optionally expose "Export from KiCad" later as an external-command helper. Main input remains Gerber/Excellon.

## 3. FlatCAM — the CAM engine

### 3.1 Which repository is real?

- `https://github.com/flatcam/flatcam` is an **empty placeholder** repository (created 2026-11-19, no source code, MIT metadata). It cannot be used.
- The maintained source is `https://github.com/vika-sonne/FlatCAM` — "FlatCAM β 2024.4", based on FlatCAM BETA by Marius Stanciu and Juan Pablo Caram. Last push 2024-05-19.
- License: **MIT** (`FlatCAM/LICENSE`, copyright 2023 vika-sonne and 2014-2019 Juan Pablo Caram). MIT permits integration and redistribution provided the copyright and license notice are preserved.

### 3.2 Architecture actually observed in the source

- 254 Python files. Important modules:
  - `appParsers/ParseGerber.py`, `appParsers/ParseExcellon.py` — file readers.
  - `camlib.py` — geometry core (Shapely, NumPy, Rtree, lxml, rasterio, ezdxf, OR-Tools).
  - `appObjects/FlatCAMGerber.py`, `FlatCAMExcellon.py`, `FlatCAMGeometry.py`, `FlatCAMCNCJob.py` — object model.
  - `appTools/ToolIsolation.py`, `ToolDrilling.py`, `ToolCutOut.py` — GUI-facing operations.
  - `tclCommands/*` — scriptable commands (`open_gerber`, `open_excellon`, `isolate`, `drillcncjob`, `cncjob`, `write_gcode`, `export_gcode`, `cutout`, ...).
  - `appGUI/*` — PyQt5-based interface; `app_Main.py` creates a `QApplication`.
- The parser/CAM classes are **not GUI-independent**: `camlib.py` imports PyQt5, `appProcess.py` imports Qt widgets, and operations rely on the `App` object and its defaults. Importing these modules into a PySide6 (Qt6) application would mix Qt5 and Qt6 in one process — unsafe and unnecessary.
- FlatCAM nevertheless provides a supported **headless scripting mode**:
  - `python FlatCAM.zip --headless --shellfile=<script.tcl>`
  - `--shellvar=<...>` passes variables into the script.
  - `app_Main.py` calls `self.shell.exec_command(text, no_echo=True)` in headless mode.
  - Commands documented in source examples include:
    ```
    open_gerber tests/gerber_files/simple1.gbr -outname margin
    isolate margin -dia 3
    cncjob margin_iso
    write_gcode name C:\path\output
    ```
- Environment pinned by `pyproject.toml`: **Python >=3.10,<3.11**, PyQt5 5.15.2, Shapely 1.8.4, NumPy 1.22, OR-Tools, VisPy, Rtree and others.

### 3.3 Integration decision

Use FlatCAM as an **isolated headless worker process**:

- SmartDrill Pro generates a Tcl-style script into a temporary working directory and runs FlatCAM with its own Python 3.10 environment.
- The worker writes G-code/JSON result files into that directory. The adapter reads them back and reports progress/errors.
- Benefits: no Qt5/Qt6 mixing, no dependency version conflicts, no modification of FlatCAM source, MIT notices preserved, and FlatCAM can be upgraded independently.
- Costs: process startup time, a file-based interface, and a need to verify each FlatCAM version's command syntax. A compatibility probe is a Phase 5 task.

Alternatives considered:

| Option | Verdict |
| --- | --- |
| Import FlatCAM modules directly | Rejected: Qt5/Qt6 conflict and tight `App` coupling. |
| Embed FlatCAM GUI in PySide6 | Rejected: different Qt major versions; not a supported API. |
| Headless worker process | **Selected.** |
| pcb2gcode (https://github.com/pcb2gcode/pcb2gcode, GPL-3.0, active C++ CLI) | Viable fallback for isolation/drilling, but weaker integration with our object model. |

## 4. File parsing libraries (in-process)

- **Gerbonara** — https://github.com/jaseg/gerbonara / https://gerbolyze.gitlab.io/gerbonara — **Apache-2.0**, version 1.6.3, requires Python ≥3.12, deps: click, rtree, quart.
  - Reads **Gerber, Excellon and IPC-356**, exposes meaningful objects (Line, Arc, Region, drill hits), unit-safe geometry, SVG rendering, and `LayerStack.from_directory()` which parses filenames/metadata to classify layers.
  - Tested against real files from many CAD tools.
  - **Selected** for file import, layer classification, verification and 2D preview geometry.
- **PyGerber** — https://github.com/Argmaster/pygerber — **MIT**, modern Gerber X3 parser/renderer. Good library, but no Excellon support; not chosen as the primary parser.
- **pcb-tools** — Apache-2.0 but unmaintained upstream; maintained forks exist. Not chosen because Gerbonara has a cleaner object model and active maintenance.

## 5. Universal Gcode Sender — protocol reference, not code

- https://github.com/winder/Universal-G-Code-Sender — **GPL-3.0**, Java, active (last push 2026-11-14).
- Architecture: `ugs-core` contains communication, G-code parsing, machine state and streaming; `ugs-platform` is the NetBeans Platform GUI. It uses JSSC/JSerialComm for serial, JTS for geometry, and has dedicated `GrblController` and `GrblHalController` implementations.
- Useful verified protocol facts from `GrblUtils.java`:
  - GRBL RX buffer = **128 bytes**; real-time commands do not consume that buffer.
  - Real-time bytes: `0x18` soft-reset, `!` feed hold (0x21), `~` resume (0x7E), `?` status (0x3F), `0x84` door, `0x85` jog cancel.
  - System commands: `$H` home, `$X` unlock alarm, `$C` check mode, `$G` parser state, `$$` settings, `$I` build info.
  - Work zero: `G10 P0 L20 X0 Y0 Z0` on modern versions (`G92 X0 Y0 Z0` on older ones).
  - Status reports: `<Idle|WPos:...|MPos:...|Bf:...|WCO:...|Ov:...|F:...|FS:...|Pn:...|A:...>`; responses `ok`, `error:N`, `ALARM:N`.
- **Decision:** Do **not** import or port UGS Java code (GPL-3.0 incompatibility with our integration goals and no supported Python API). Implement a small Python `pyserial` layer using this documented line-based protocol: one line at a time, wait for `ok`/`error`, bounded receive buffer, real-time bytes written outside the ack flow, status polling for monitoring.

## 6. grblHAL and ESP32-S3

- Core: https://github.com/grblHAL/core — **GPL-3.0-or-later** (file `COPYING`, copyright Terje Io / Sungeun K. Jeon / Simen Svale Skogsrud).
- ESP32 driver: https://github.com/grblHAL/ESP32 — "grblHAL driver for ESP32 and ESP32-S3", active (last push 2026-11-17).
- **ESP32-S3 support verified** in the repository: `main/boards/generic_s3_map.h`, `main/boards/generic_i2s_s3_map.h`, `main/boards/cnc_boosterpack_s3_map.h`, `sdkconfig.defaults.esp32s3`, `partitions_s3_8m.csv`, `main/i2s_out_s3.c`.
- Firmware is built with ESP-IDF (README describes v4.3) or the vendor Web Builder, configured in `main/CMakeLists.txt`, `grbl/config.h`, and a `*_map.h` pin map, then flashed with `idf.py -p PORT flash`.
- Machine parameters (steps/mm `$100-$102`, max rate `$110-$112`, acceleration `$120-$122`, limits `$20-$22`, homing `$22`, soft limits `$20`, spindle settings) are firmware settings, not hardcoded app values.
- **Decision:** Use grblHAL unchanged. SmartDrill Pro queries `$I`/`$$`, sends `$H`, `G10 L20`, jogging and G-code, and stores editable machine profiles. No custom firmware.

## 7. Chosen technology stack

| Layer | Choice | Reason |
| --- | --- | --- |
| Language | Python 3.12 (main), Python 3.10 (CAM worker) | Matches Gerbonara and FlatCAM requirements without conflicts. |
| UI | PySide6 / Qt6 | Professional cross-platform desktop UI; QGraphicsView for 2D preview. |
| File parsing | Gerbonara | Real Gerber + Excellon parsing, layer classification, Apache-2.0. |
| Geometry | Shapely + NumPy | Standard, reliable geometry operations for preview/validation. |
| CAM | FlatCAM 2024.4 headless worker | Mature isolation/drill/outline CAM, MIT, already solves the hard geometry. |
| Serial | pyserial | Standard Python serial library; custom GRBL streaming layer. |
| Packaging | PyInstaller (planned) | Windows executable with bundled worker environment. |
| Tests | pytest + simulated controller | Development without physical hardware. |

## 8. Legal summary

See [03_licensing.md](03_licensing.md). Short version: FlatCAM MIT and Gerbonara Apache-2.0 are compatible with a proprietary/commercial wrapper if notices are retained; grblHAL GPL-3.0 stays on the controller; UGS GPL-3.0 code is not copied; PySide6 LGPL-3.0 requires dynamic linking and notice/attribution.

## 9. Sources

- https://github.com/flatcam/flatcam , https://github.com/vika-sonne/FlatCAM (README, LICENSE, pyproject.toml, source tree, tclCommands, app_Main.py)
- https://github.com/winder/Universal-G-Code-Sender (README, GrblUtils.java, GrblCommunicator.java, source tree)
- https://github.com/grblHAL/core (COPYING, source tree), https://github.com/grblHAL/ESP32 (README, board maps)
- https://docs.kicad.org/master/en/cli/cli.html
- https://github.com/jaseg/gerbonara , https://gerbolyze.gitlab.io/gerbonara , https://pypi.org/project/gerbonara
- https://github.com/Argmaster/pygerber , https://github.com/pcb2gcode/pcb2gcode
