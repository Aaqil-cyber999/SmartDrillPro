# Software architecture

## 1. Guiding principles

1. **Own the workflow, reuse the engines.** SmartDrill Pro implements project management, UI, validation, job control and integration. It does not reimplement Gerber parsing or isolation geometry.
2. **Separate processes for incompatible runtimes.** Qt5/FlatCAM and Qt6/PySide6 must not share a process. Python 3.10 and Python 3.12 dependencies must not share an environment.
3. **Data flows one way through explicit interfaces.** UI → services → models/engines → results → UI. Machine communication never calls CAM code directly.
4. **Nothing moves the machine without an explicit, validated, human-approved action.**
5. **Simulation first.** A simulated grblHAL controller allows all development and tests without hardware.
6. **Original files are immutable.** Uploaded files are copied into a project's `source/` directory and never overwritten.

## 2. System context

```
 KiCad (optional, external)
        | kicad-cli pcb export gerbers / drill
        v
 Gerber + Excellon files
        |
        v
+--------------------------- SmartDrill Pro ---------------------------+
| PySide6 UI (Qt6, Python 3.12)                                        |
|   Dashboard | Project | Files | PCB Viewer | CAM | G-code | Machine  |
|                    |                    |                  |          |
|              file_processing       cam/gcode          machine        |
|              (Gerbonara)       (orchestration)     (pyserial)        |
|                    |                    |                  |          |
|      project models + event bus + validation + job controller        |
+----------------------------+---------------------------+------------+
                             | subprocess (script + JSON)
                             v
                 FlatCAM 2024.4 headless worker
                 Python 3.10 / PyQt5 / MIT
                             | generated G-code
                             v
                  G-code validator / preview
                             |
                 USB serial (line based + real-time bytes)
                             v
                 ESP32-S3 + grblHAL (GPL-3.0 firmware)
                             v
                 STEP/DIR -> drivers -> NEMA 17 -> CNC
```

## 3. Process boundaries

### Main process (Python 3.12)

- Owns the GUI, project state, Gerber/Excellon parsing (Gerbonara), 2D previews (Shapely + QGraphicsView), G-code parsing/validation, and the serial/job controller.
- Never imports FlatCAM or PyQt5.

### FlatCAM worker process (Python 3.10)

- Started only for CAM operations (isolation, drilling, outline).
- Input: a generated `.tcl`-style script and copied source files in a temporary directory.
- Output: G-code files plus a small JSON status file written by the adapter's wrapper.
- Communicates by stdout/stderr and files. No sockets, no shared memory, no GUI.
- Exit code, stdout and stderr are captured; timeouts and parse errors are reported to the user.

### Simulated controller

- Implements the same interface as the serial grblHAL transport (`connect`, `send_line`, `write_realtime`, `read`, `close`).
- Responds `ok`/`error:N`, emits status reports, supports feed hold/reset, and simulates motion for progress/time estimates.

## 4. Data flow for one machining job

1. **Create project** → `data/projects/<id>/project.json` plus `source/`, `generated/`, `history/`.
2. **Import files** → gerbonara parses geometry; `file_validator` checks content; `layer_classifier` assigns layer roles with confidence; unresolved roles are shown to the user for manual assignment.
3. **Preview PCB** → geometry converted to Shapely objects, rendered by `PcbCanvas`.
4. **Configure machining** → user selects machine profile and operation parameters (all marked *unverified* until calibrated).
5. **Generate toolpaths** → `CamManager` calls `FlatcamAdapter` for each operation; results become `MachiningOperation` objects with toolpath geometry and G-code.
6. **Validate** → `GcodeValidator` checks coordinates, depths, feed rates, supported commands, boundaries and safe-Z moves. Errors block execution.
7. **Preview G-code** → `ToolpathViewer` colors rapid/cutting/travel moves and estimates time.
8. **Approve** → explicit confirmation dialog; machine must be connected, not alarmed, homed/known-zero as required.
9. **Execute** → `GcodeStreamer` sends one line at a time with ack handling and a bounded RX budget; `MachineStatus` polls `?` reports; pause/resume/cancel are available.
10. **Finish** → job result appended to project history; generated files preserved.

## 5. Module responsibilities

| Module | Responsibility | Must not do |
| --- | --- | --- |
| `app/core` | Lifecycle, event bus, logging, project open/save | Parse files or talk to hardware |
| `app/ui` | Screens, dialogs, widgets, user input | Contain manufacturing math or serial protocol |
| `app/file_processing` | Validation, Gerber/Excellon parsing, layer classification | Decide toolpaths |
| `app/cam` | Operation configuration, FlatCAM adapter, result normalization | Generate final G-code or control machine |
| `app/gcode` | Generators (when needed), parser, validator, preview data | Talk to serial ports |
| `app/machine` | Serial transport, grblHAL commands, streaming, status, job control | Read Gerber files |
| `app/models` | Typed data structures shared between modules | Perform I/O |
| `app/services` | Project/export/settings orchestration | Implement UI widgets |

## 6. Project storage format

```
data/projects/<project-id>/
    project.json              # metadata, layer roles, settings, warnings, history
    source/                   # untouched original uploads
    generated/                # toolpaths, gcode, reports
    history/                  # job records
```

`project.json` is human-readable JSON with a version field so future versions can migrate old projects. Timestamps are ISO-8601 UTC. Paths inside are relative to the project root.

## 7. Safety model

- **Validation gate:** no G-code reaches the machine unless `GcodeValidator` reports no blocking errors.
- **Approval gate:** a separate confirmation is required at start; generation alone never executes a job.
- **State gate:** alarm, door/hold, unknown state or missing homing/zero confirmation blocks start.
- **Boundary gate:** toolpath extents are checked against the active machine profile's travel limits and workpiece dimensions.
- **Depth/feed gate:** cutting depth, plunge rate and feed rate are checked against configurable maxima.
- **Connection gate:** serial timeouts and disconnects pause streaming safely; the operator decides whether to resume.
- **E-stop:** UI shows *status only*; a physical emergency-stop circuit is required and must be documented as such.

## 8. Technology rationale for deviations from the proposed stack

- The specification proposed a single Python stack. We keep Python and PySide6 but split runtimes (3.12 main / 3.10 CAM worker) because FlatCAM 2024.4 hard-pins Python 3.10 and PyQt5. This is the minimum change that lets us reuse the mature CAM engine instead of rewriting it.
- The specification suggested "Shapely, NumPy, appropriate Gerber/Excellon parsers". We selected Gerbonara because it covers **both** formats and layer classification in one maintained Apache-2.0 library.
- G-code streaming is implemented in Python with pyserial rather than wrapping UGS, because UGS is a Java/GPL-3.0 application with no supported Python API.

## 9. Future extension points

- Plugin interface for alternative CAM backends (pcb2gcode) behind `CamBackend`.
- Optional KiCad export helper via `kicad-cli`.
- Ethernet/WebUI grblHAL transports behind the same `Transport` interface.
- 3D view or OpenGL rendering behind a `PreviewRenderer` interface.
