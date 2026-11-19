"""Parse RS-274X Gerber files into Shapely geometry using Gerbonara."""

from __future__ import annotations

import math
from pathlib import Path

from gerbonara import GerberFile
from gerbonara import apertures as ap
from gerbonara import graphic_objects as go
from shapely.geometry import LineString, Point, Polygon, box

from app.models.parsed_layer import GeometryFeature, ParsedLayer


def _mm(value) -> float:
    if value is None:
        return 0.0
    return float(value)


def _flash_geometry(obj: go.Flash):
    aperture = obj.aperture
    x, y = _mm(obj.x), _mm(obj.y)
    if isinstance(aperture, ap.CircleAperture):
        radius = max(_mm(aperture.diameter) / 2.0, 1e-6)
        return Point(x, y).buffer(radius, quad_segs=16), radius * 2.0, "circle"
    if isinstance(aperture, ap.RectangleAperture):
        width, height = max(_mm(aperture.w), 1e-6), max(_mm(aperture.h), 1e-6)
        return box(x - width / 2, y - height / 2, x + width / 2, y + height / 2), width, "rectangle"
    if isinstance(aperture, ap.ObroundAperture):
        width, height = max(_mm(aperture.w), 1e-6), max(_mm(aperture.h), 1e-6)
        return box(x - width / 2, y - height / 2, x + width / 2, y + height / 2), max(width, height), "obround"
    if isinstance(aperture, ap.PolygonAperture):
        radius = max(_mm(aperture.diameter) / 2.0, 1e-6)
        sides = int(aperture.n_vertices) if aperture.n_vertices else 3
        rotation = _mm(aperture.rotation) if aperture.rotation else 0.0
        points = [
            (x + radius * math.cos(rotation + i * 2 * math.pi / sides),
             y + radius * math.sin(rotation + i * 2 * math.pi / sides))
            for i in range(sides)
        ]
        return Polygon(points), radius * 2.0, "polygon"
    return Point(x, y).buffer(0.1, quad_segs=8), 0.2, "unknown_aperture"


def _arc_points(obj: go.Arc, segments: int = 32) -> list[tuple[float, float]]:
    x1, y1, x2, y2 = _mm(obj.x1), _mm(obj.y1), _mm(obj.x2), _mm(obj.y2)
    cx, cy = _mm(obj.cx), _mm(obj.cy)
    start = math.atan2(y1 - cy, x1 - cx)
    end = math.atan2(y2 - cy, x2 - cx)
    if obj.clockwise:
        while end >= start:
            end -= 2 * math.pi
    else:
        while end <= start:
            end += 2 * math.pi
    radius = math.hypot(x1 - cx, y1 - cy)
    return [
        (cx + radius * math.cos(start + (end - start) * i / segments),
         cy + radius * math.sin(start + (end - start) * i / segments))
        for i in range(segments + 1)
    ]


def _geometry_bounds(features: list[GeometryFeature]) -> tuple[float, float, float, float] | None:
    if not features:
        return None
    minx = min(f.geometry.bounds[0] for f in features)
    miny = min(f.geometry.bounds[1] for f in features)
    maxx = max(f.geometry.bounds[2] for f in features)
    maxy = max(f.geometry.bounds[3] for f in features)
    return (minx, miny, maxx, maxy)


class GerberParser:
    """Thin wrapper around Gerbonara that returns app-level geometry."""

    def parse(self, path: str | Path) -> ParsedLayer:
        source = Path(path)
        gerber = GerberFile.open(source)
        features: list[GeometryFeature] = []
        warnings: list[str] = []

        for obj in gerber.objects:
            try:
                if isinstance(obj, go.Line):
                    width = max(_mm(obj.aperture.diameter) if obj.aperture else 0.0, 1e-5)
                    geometry = LineString([(_mm(obj.x1), _mm(obj.y1)), (_mm(obj.x2), _mm(obj.y2))]).buffer(
                        width / 2, cap_style=1
                    )
                    features.append(GeometryFeature("line", geometry, width))
                elif isinstance(obj, go.Flash):
                    geometry, width, shape = _flash_geometry(obj)
                    features.append(GeometryFeature("flash", geometry, width, {"shape": shape}))
                elif isinstance(obj, go.Arc):
                    width = max(_mm(obj.aperture.diameter) if obj.aperture else 0.0, 1e-5)
                    geometry = LineString(_arc_points(obj)).buffer(width / 2, cap_style=1)
                    features.append(GeometryFeature("arc", geometry, width))
                elif isinstance(obj, go.Region):
                    minx, miny, maxx, maxy = obj.bounding_box(unit="mm")
                    features.append(GeometryFeature("region", box(minx, miny, maxx, maxy), 0.0))
                else:
                    warnings.append(f"Unsupported Gerber object skipped: {type(obj).__name__}")
            except (ValueError, TypeError, AttributeError) as exc:
                warnings.append(f"Could not convert {type(obj).__name__}: {exc}")

        return ParsedLayer(
            source_file=source.name,
            content_type="gerber",
            features=features,
            bounds=_geometry_bounds(features),
            warnings=warnings,
        )
