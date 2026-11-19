"""Application-wide constants and paths.

Beginner note: this module answers "where does the app store things?" and
"what version am I running?". Nothing here controls the physical machine.
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "SmartDrill Pro"
APP_VERSION = "0.2.0"
ORGANIZATION = "SmartDrillPro"

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resolve_data_dir(override: str | None = None) -> Path:
    """Return the writable data directory, allowing an explicit override."""
    candidate = override or os.environ.get("SMARTDRILL_DATA_DIR")
    return Path(candidate).expanduser().resolve() if candidate else PROJECT_ROOT / "data"


def data_paths(data_dir: Path) -> dict[str, Path]:
    paths = {
        "root": data_dir,
        "projects": data_dir / "projects",
        "generated": data_dir / "generated_gcode",
        "logs": data_dir / "logs",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


# GRBL/grblHAL defaults used by the future communication layer. The controller
# is always queried at connection time; these are only starting values.
DEFAULT_BAUD_RATE = 115200
DEFAULT_RX_BUFFER_BYTES = 128  # Verified from public GRBL protocol constants.
DEFAULT_STATUS_POLL_MS = 500
DEFAULT_SERIAL_TIMEOUT_S = 2.0

# Human-readable workflow steps shown on the dashboard.
WORKFLOW_STEPS: list[tuple[str, str]] = [
    ("1", "Create project"),
    ("2", "Upload files"),
    ("3", "Identify layers"),
    ("4", "Preview PCB"),
    ("5", "Configure machining"),
    ("6", "Generate toolpaths"),
    ("7", "Generate G-code"),
    ("8", "Validate G-code"),
    ("9", "Connect machine"),
    ("10", "Execute job"),
]
