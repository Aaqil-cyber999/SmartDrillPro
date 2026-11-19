"""Parse Excellon drill files into Shapely geometry using Gerbonara."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from gerbonara import ExcellonFile
from gerbonara import graphic_objects as go
from shapely.geometry import Point

from app.file_processing.gerber_parser import _geometry_bounds
from app.models.drill_tool import DrillTool
from app.models.parsed_layer import GeometryFeature, ParsedLayer


class ExcellonParser:
    def parse(self, path: str | Path) -> ParsedLayer:
        source = Path(path)
        drill_file = ExcellonFile.open(source)
        name_lower = source.name.lower()
        plated = None
        if "npth" in name_lower or "nonplated" in name_lower or "unplated" in name_lower:
            plated = False
        elif "pth" in name_lower or "plated" in name_lower:
            plated = True

        features: list[GeometryFeature] = []
        hits_by_diameter: Counter[float] = Counter()
        for obj in drill_file.drills():
            if not isinstance(obj, go.Flash):
                continue
            diameter = float(obj.aperture.diameter)
            if diameter <= 0:
                continue
            geometry = Point(float(obj.x), float(obj.y)).buffer(diameter / 2, quad_segs=16)
            features.append(GeometryFeature("drill", geometry, diameter, {"plated": plated}))
            hits_by_diameter[round(diameter, 4)] += 1

        tools: list[DrillTool] = []
        try:
            raw_sizes = list(drill_file.drill_sizes())
        except TypeError:
            raw_sizes = list(drill_file.drill_sizes)
        for index, diameter in enumerate(raw_sizes, start=1):
            size = round(float(diameter), 4)
            tools.append(DrillTool(index, size, hits_by_diameter.get(size, 0), plated))

        return ParsedLayer(
            source_file=source.name,
            content_type="excellon",
            features=features,
            bounds=_geometry_bounds(features),
            drill_tools=tools,
            warnings=[] if features else ["Excellon file contains no drill hits."],
        )
