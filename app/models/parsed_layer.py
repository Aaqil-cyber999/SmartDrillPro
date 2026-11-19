"""In-memory geometry produced by the file parsers.

Shapely geometry objects live only in memory. Project JSON stores metadata,
not geometry, so re-opening a project re-parses the original source files.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from shapely.geometry.base import BaseGeometry

from app.models.drill_tool import DrillTool


@dataclass
class GeometryFeature:
    kind: str  # line, circle, region, drill
    geometry: BaseGeometry
    width_mm: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedLayer:
    source_file: str
    content_type: str
    features: list[GeometryFeature] = field(default_factory=list)
    bounds: tuple[float, float, float, float] | None = None
    drill_tools: list[DrillTool] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def feature_count(self) -> int:
        return len(self.features)
