"""Drill tool definition extracted from an Excellon file."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class DrillTool:
    number: int
    diameter_mm: float
    hole_count: int
    plated: bool | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "DrillTool":
        known = {key: data[key] for key in cls.__dataclass_fields__ if key in data}
        return cls(**known)
