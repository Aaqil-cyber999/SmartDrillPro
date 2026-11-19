"""Conservative, user-editable CAM parameters.

All distances are millimetres and feeds are mm/min. These values are starting
points, not cutting recommendations: the operator must match them to the tool,
material, spindle and machine.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass
class CamSettings:
    isolation_tool_mm: float = 0.4
    isolation_passes: int = 1
    isolation_overlap: float = 0.0
    cut_depth_mm: float = -0.1
    travel_height_mm: float = 2.0
    depth_per_pass_mm: float = 0.1
    feed_xy: float = 120.0
    feed_z: float = 100.0
    feed_rapid: float = 300.0
    spindle_rpm: int = 1000
    outline_tool_mm: float = 0.8
    outline_depth_mm: float = -1.6
    drill_depth_mm: float = -1.6
    isolation_enabled: bool = True
    drilling_enabled: bool = True
    outline_enabled: bool = True

    def validate(self) -> None:
        if self.isolation_tool_mm <= 0 or self.outline_tool_mm <= 0:
            raise ValueError("Tool diameters must be positive.")
        if self.isolation_passes < 1 or self.isolation_passes > 10:
            raise ValueError("Isolation passes must be between 1 and 10.")
        if not 0 <= self.isolation_overlap < 100:
            raise ValueError("Isolation overlap must be between 0 and 100 percent.")
        if self.cut_depth_mm >= 0 or self.outline_depth_mm >= 0 or self.drill_depth_mm >= 0:
            raise ValueError("Cut and drill depths must be negative (below the material surface).")
        if self.travel_height_mm <= 0 or self.depth_per_pass_mm <= 0:
            raise ValueError("Travel height and depth per pass must be positive.")
        if min(self.feed_xy, self.feed_z, self.feed_rapid) <= 0:
            raise ValueError("Feed rates must be positive.")
        if self.spindle_rpm < 0:
            raise ValueError("Spindle speed cannot be negative.")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CamSettings":
        known = {key: data[key] for key in cls.__dataclass_fields__ if key in data}
        return cls(**known)


def load_cam_settings(path: Path) -> CamSettings:
    if not path.is_file():
        return CamSettings()
    return CamSettings.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_cam_settings(path: Path, settings: CamSettings) -> None:
    settings.validate()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.to_dict(), indent=2), encoding="utf-8")
