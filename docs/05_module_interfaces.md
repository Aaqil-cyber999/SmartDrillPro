# Module interfaces (contracts)

These are the agreed contracts for Phase 2+. Signatures may be refined during implementation, but module boundaries must stay intact.

## Events (`app/core/event_manager.py`)

```python
event_bus.subscribe("project_changed", callback)
event_bus.emit("project_changed", project)
```

Stable event names: `project_created`, `project_changed`, `files_imported`, `layers_changed`, `cam_progress`, `cam_finished`, `gcode_ready`, `gcode_validated`, `machine_state_changed`, `job_progress`, `job_finished`, `error_raised`.

## Models (`app/models/`)

```python
@dataclass
class PcbLayer:
    id: str
    path: Path              # relative to project/source
    detected_role: LayerRole
    assigned_role: LayerRole
    confidence: float       # 0.0 - 1.0
    content_type: str       # "gerber" | "excellon" | "unknown"
    warnings: list[str]

class LayerRole(Enum):
    FRONT_COPPER = "front_copper"
    BACK_COPPER = "back_copper"
    FRONT_SOLDER_MASK = "front_solder_mask"
    BACK_SOLDER_MASK = "back_solder_mask"
    FRONT_SILKSCREEN = "front_silkscreen"
    BACK_SILKSCREEN = "back_silkscreen"
    OUTLINE = "outline"
    PLATED_DRILL = "plated_drill"
    NON_PLATED_DRILL = "non_plated_drill"
    OTHER = "other"
    UNASSIGNED = "unassigned"

@dataclass
class DrillTool:
    number: int
    diameter_mm: float
    hole_count: int
    plated: bool

@dataclass
class MachiningOperation:
    id: str
    kind: str               # "isolation" | "drilling" | "outline"
    source_layer_ids: list[str]
    tool_diameter_mm: float
    toolpaths: list[Toolpath]
    gcode_path: Path
    settings: dict
    validated: bool = False

@dataclass
class Toolpath:
    kind: str               # "rapid" | "cut" | "travel" | "drill"
    points: list[tuple[float, float, float]]
    feed_rate: int | None = None
```

## File processing

```python
class FileValidator:
    def validate(path: Path) -> ValidationResult   # type, confidence, errors, warnings

class GerberParser:
    def parse(path: Path) -> ParsedLayer            # real geometry via gerbonara

class ExcellonParser:
    def parse(path: Path) -> tuple[ParsedLayer, list[DrillTool]]

class LayerClassifier:
    def classify(files: list[ParsedLayer]) -> list[PcbLayer]
```

Rules: validation reads magic/content, not just extension; parse errors are surfaced, never silently skipped.

## CAM

```python
class CamManager:
    def isolate(layer: PcbLayer, settings: IsolationSettings) -> MachiningOperation
    def drill(tools: list[DrillTool], settings: DrillSettings) -> MachiningOperation
    def outline(layer: PcbLayer, settings: OutlineSettings) -> MachiningOperation

class CamBackend(Protocol):
    def run(spec: CamJobSpec, workdir: Path, progress_cb) -> CamResult

class FlatcamAdapter(CamBackend):
    """Writes a Tcl script, launches isolated Python 3.10 FlatCAM, parses results."""
```

`CamResult` carries G-code paths, console output, warnings and duration. A non-zero FlatCAM exit code is always an error.

## G-code

```python
class GcodeParser:
    def parse_file(path: Path) -> list[GcodeLine]     # expands modal state for preview

class GcodeValidator:
    def validate(gcode: list[GcodeLine], machine: MachineProfile,
                 limits: WorkpieceLimits) -> ValidationReport

@dataclass
class ValidationReport:
    errors: list[ValidationIssue]        # blocking
    warnings: list[ValidationIssue]      # non-blocking
    bounds: tuple[float, float, float, float]
    estimated_seconds: float
```

Checks: finite coordinates, normalized units, safe Z before XY rapid at cutting height, depth limits, feed/spindle limits, unsupported M/G commands relative to the machine profile, travel outside workpiece/machine bounds, empty program, missing program end.

## Machine

```python
class Transport(Protocol):
    def open(port: str, baudrate: int, timeout: float) -> None
    def close() -> None
    def send_line(line: str) -> None
    def write_realtime(byte: bytes) -> None
    def read_line(timeout: float) -> str | None

class SerialTransport(Transport):   # pyserial
class SimulatedTransport(Transport): # tests/offline mode

class GrblHalInterface:
    def identify() -> ControllerInfo      # from $I / $$ / status
    def status() -> MachineState
    def home() -> None
    def set_work_zero(axes: str = "XYZ") -> None
    def jog(axis: str, distance: float, feed: int) -> None
    def feed_hold() -> None
    def resume() -> None
    def soft_reset() -> None

class GcodeStreamer:
    def start(lines: list[str]) -> None
    def pause() -> None
    def resume() -> None
    def cancel() -> None
```

Streaming rules:

- Send **one line at a time**, then wait for `ok` or `error:N`.
- Track a byte budget for the controller RX buffer (default 128 bytes, configurable after `$I`/`Bf` reports); real-time bytes do not consume the budget.
- `!` hold, `~` resume, `?` status, `0x18` soft reset, `0x85` jog cancel.
- Timeout on a missing acknowledgement → pause and report; never assume success.
- Status polling while RUN/HOLD; `error:` or `ALARM:` stops the job and shows a decoded message.

## Services

```python
class ProjectService:
    def create(name: str, folder: Path) -> PcbProject
    def open(path: Path) -> PcbProject
    def save(project: PcbProject) -> None
    def add_files(project: PcbProject, paths: list[Path]) -> list[PcbLayer]

class ExportService:
    def export_gcode(operation: MachiningOperation, destination: Path) -> None
    def export_report(project: PcbProject, destination: Path) -> None

class SettingsService:
    def load() -> AppSettings
    def save(settings: AppSettings) -> None
```
