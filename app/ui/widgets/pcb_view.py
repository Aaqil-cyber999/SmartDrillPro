"""QGraphicsView renderer for parsed PCB geometry.

Coordinates from Gerbonara are millimetres with Y pointing up; Qt scene Y points
down, so the Y axis is inverted here. Scene units are ``SCENE_SCALE`` pixels per
millimetre, which keeps the view crisp and gives simple measurement maths.
"""

from __future__ import annotations

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
)
from shapely.geometry import Polygon

from app.models.parsed_layer import ParsedLayer

SCENE_SCALE = 20.0

LAYER_COLORS: dict[str, tuple[str, float]] = {
    "top_copper": ("#e08b3c", 0.85),
    "bottom_copper": ("#4d92d0", 0.80),
    "inner_copper": ("#9b72bd", 0.75),
    "top_solder_mask": ("#2f9c62", 0.35),
    "bottom_solder_mask": ("#257d50", 0.30),
    "top_silkscreen": ("#e8e8e8", 0.80),
    "bottom_silkscreen": ("#cccccc", 0.70),
    "top_paste": ("#b0b0b0", 0.60),
    "bottom_paste": ("#999999", 0.55),
    "outline": ("#f2f2f2", 0.20),
    "plated_drill": ("#161616", 1.0),
    "nonplated_drill": ("#e5484d", 1.0),
    "drill": ("#222222", 1.0),
    "other": ("#808080", 0.60),
}


def _scene_point(x: float, y: float) -> QPointF:
    return QPointF(x * SCENE_SCALE, -y * SCENE_SCALE)


def _polygon_items(geometry, role: str) -> list[QGraphicsPolygonItem]:
    polygons: list[Polygon] = []
    if isinstance(geometry, Polygon):
        polygons.append(geometry)
    elif hasattr(geometry, "geoms"):
        polygons.extend(poly for poly in geometry.geoms if isinstance(poly, Polygon))

    color, alpha = LAYER_COLORS.get(role, LAYER_COLORS["other"])
    fill = QColor(color)
    fill.setAlphaF(alpha)
    pen = QPen(QColor(color), 0.4)
    items: list[QGraphicsPolygonItem] = []
    for polygon in polygons:
        if polygon.is_empty or len(polygon.exterior.coords) < 3:
            continue
        outer = QPolygonF([_scene_point(x, y) for x, y in polygon.exterior.coords])
        item = QGraphicsPolygonItem(outer)
        item.setBrush(QBrush(fill))
        item.setPen(pen)
        items.append(item)
        # Draw interior rings in the scene background colour so holes stay visible.
        for ring in polygon.interiors:
            if len(ring.coords) < 3:
                continue
            hole = QGraphicsPolygonItem(QPolygonF([_scene_point(x, y) for x, y in ring.coords]))
            hole.setBrush(QBrush(QColor("#10151c")))
            hole.setPen(pen)
            items.append(hole)
    return items


class PcbView(QGraphicsView):
    measurement_done = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(QColor("#10151c")))
        self.layer_groups: dict[str, QGraphicsItemGroup] = {}
        self._measure_mode = False
        self._first_point: QPointF | None = None
        self._measure_line: QGraphicsLineItem | None = None

    @property
    def measure_mode(self) -> bool:
        return self._measure_mode

    def set_measure_mode(self, enabled: bool) -> None:
        self._measure_mode = enabled
        self._first_point = None
        if self._measure_line is not None:
            self.scene.removeItem(self._measure_line)
            self._measure_line = None
        self.setDragMode(
            QGraphicsView.DragMode.NoDrag if enabled else QGraphicsView.DragMode.ScrollHandDrag
        )
        self.setCursor(Qt.CursorShape.CrossCursor if enabled else Qt.CursorShape.ArrowCursor)

    def set_layers(self, layers: dict[str, ParsedLayer], roles: dict[str, str] | None = None) -> None:
        """Rebuild the scene from real parsed geometry."""
        self.scene.clear()
        self.layer_groups = {}
        roles = roles or {}
        all_bounds: list[tuple[float, float, float, float]] = []

        for name, layer in layers.items():
            role = roles.get(name, "other")
            if role not in {"plated_drill", "nonplated_drill", "drill"} and layer.content_type == "excellon":
                role = "drill"
            group = QGraphicsItemGroup()
            group.setData(0, name)
            for feature in layer.features:
                for item in _polygon_items(feature.geometry, role):
                    group.addToGroup(item)
            self.scene.addItem(group)
            self.layer_groups[name] = group
            if layer.bounds:
                all_bounds.append(layer.bounds)

        self._add_dimensions(all_bounds)
        if all_bounds:
            minx = min(b[0] for b in all_bounds) * SCENE_SCALE
            miny = -max(b[3] for b in all_bounds) * SCENE_SCALE
            maxx = max(b[2] for b in all_bounds) * SCENE_SCALE
            maxy = -min(b[1] for b in all_bounds) * SCENE_SCALE
            self.scene.setSceneRect(QRectF(minx - 20, miny - 20, maxx - minx + 40, maxy - miny + 40))
        else:
            self.scene.setSceneRect(QRectF(-100, -100, 200, 200))
        self.fit_view()

    def set_layer_visible(self, name: str, visible: bool) -> None:
        group = self.layer_groups.get(name)
        if group is not None:
            group.setVisible(visible)

    def fit_view(self) -> None:
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def zoom(self, factor: float) -> None:
        self.scale(factor, factor)

    def _add_dimensions(self, bounds: list[tuple[float, float, float, float]]) -> None:
        if not bounds:
            return
        minx = min(b[0] for b in bounds)
        miny = min(b[1] for b in bounds)
        maxx = max(b[2] for b in bounds)
        maxy = max(b[3] for b in bounds)
        width, height = maxx - minx, maxy - miny
        label = QGraphicsTextItem(f"Board area: {width:.2f} × {height:.2f} mm")
        label.setDefaultTextColor(QColor("#9aa7b8"))
        label.setPos(_scene_point(minx, miny - 1.2))
        self.scene.addItem(label)

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom(factor)

    def mousePressEvent(self, event) -> None:
        if not self._measure_mode or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        point = self.mapToScene(event.position().toPoint())
        if self._first_point is None:
            self._first_point = point
            return
        if self._measure_line is not None:
            self.scene.removeItem(self._measure_line)
        line = QLineF(self._first_point, point)
        pen = QPen(QColor("#ffd166"), 2.0, Qt.PenStyle.DashLine)
        self._measure_line = self.scene.addLine(line, pen)
        self.measurement_done.emit(line.length() / SCENE_SCALE)
        self._first_point = None
