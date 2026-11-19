"""Colored G-code movement preview."""

from __future__ import annotations

from PySide6.QtCore import QLineF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from app.gcode.gcode_parser import ParsedGcode

SCALE = 20.0
COLORS = {
    "rapid": "#ffd166",
    "cut": "#4dd2ff",
    "plunge": "#ff7bd5",
    "travel": "#8b98a8",
    "drill": "#ff6b6b",
    "other": "#6c757d",
}


def _point(x: float, y: float):
    from PySide6.QtCore import QPointF
    return QPointF(x * SCALE, -y * SCALE)


class GcodePreviewView(QGraphicsView):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(QColor("#10151c")))

    def set_gcode(self, parsed: ParsedGcode | None) -> None:
        self.scene.clear()
        if parsed is None or not parsed.moves:
            self.scene.setSceneRect(QRectF(-100, -100, 200, 200))
            return
        for move in parsed.moves:
            color = QColor(COLORS.get(move.kind, COLORS["other"]))
            pen = QPen(color, 1.2)
            self.scene.addLine(QLineF(_point(*move.start[:2]), _point(*move.end[:2])), pen)
        minx, miny, maxx, maxy = parsed.bounds
        self.scene.setSceneRect(
            QRectF(_point(minx, maxy), _point(maxx, miny)).adjusted(-20, -20, 20, 20)
        )
        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event) -> None:
        self.scale(1.15 if event.angleDelta().y() > 0 else 1 / 1.15,
                   1.15 if event.angleDelta().y() > 0 else 1 / 1.15)
