"""DXF reference viewer with snapping, layer visibility, and residual overlays."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPen, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QWidget,
)

from core.project import ControlPoint
from core.reference2d import LayerInfo, Reference2D, snap_to_vertex
from ui.theme import ACCENT, BG_DARKEST, ERROR, SUCCESS, TEXT_BRIGHT, WARNING


class Reference2DViewer(QGraphicsView):
    """Interactive DXF reference viewer."""

    point_picked = Signal(float, float)
    cursor_message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._reference: Reference2D | None = None
        self._layer_items: dict[str, list[QGraphicsLineItem]] = {}
        self._overlay_items: list[QGraphicsItem] = []
        self._is_panning = False
        self._last_pan_pos = QPoint()

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setBackgroundBrush(QColor(BG_DARKEST))

    def set_reference(self, reference: Reference2D | None) -> None:
        self._scene.clear()
        self._layer_items = {}
        self._overlay_items.clear()
        self._reference = reference
        if reference is None:
            self.setSceneRect(0.0, 0.0, 1.0, 1.0)
            return

        colors = _layer_color_lookup(reference.layers)
        for segment in reference.segments:
            start = _world_to_scene(segment.start)
            end = _world_to_scene(segment.end)
            item = QGraphicsLineItem(start.x(), start.y(), end.x(), end.y())
            item.setPen(QPen(colors.get(segment.layer, QColor("#b7b7b7")), 0.0))
            self._scene.addItem(item)
            self._layer_items.setdefault(segment.layer, []).append(item)

        ext_min = reference.extents_min
        ext_max = reference.extents_max
        margin = max((ext_max[0] - ext_min[0]) * 0.05, (ext_max[1] - ext_min[1]) * 0.05, 10.0)
        self.setSceneRect(
            ext_min[0] - margin,
            -ext_max[1] - margin,
            (ext_max[0] - ext_min[0]) + margin * 2.0,
            (ext_max[1] - ext_min[1]) + margin * 2.0,
        )
        self.resetTransform()
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def set_layer_visibility(self, layer_name: str, visible: bool) -> None:
        if self._reference is None:
            return
        for item in self._layer_items.get(layer_name, []):
            item.setVisible(visible)

    def set_points(
        self,
        points: Iterable[ControlPoint],
        selected_point_id: int | None = None,
    ) -> None:
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items.clear()

        for point in points:
            if point.reference_xy is None:
                continue

            x, y = point.reference_xy
            scene = _world_to_scene((x, y))
            color = QColor(SUCCESS) if point.is_paired else QColor(WARNING)
            if point.id == selected_point_id:
                color = QColor(ACCENT)

            shadow = QGraphicsEllipseItem(-6.0, -6.0, 12.0, 12.0)
            shadow.setPos(scene)
            shadow.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            shadow.setPen(QPen(QColor(0, 0, 0, 128), 4.0))
            shadow.setBrush(Qt.NoBrush)
            self._scene.addItem(shadow)

            marker = QGraphicsEllipseItem(-6.0, -6.0, 12.0, 12.0)
            marker.setPos(scene)
            marker.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            marker.setPen(QPen(color, 2.0))
            marker.setBrush(QBrush(color))
            self._scene.addItem(marker)

            selection_ring = None
            if point.id == selected_point_id:
                selection_ring = QGraphicsEllipseItem(-9.0, -9.0, 18.0, 18.0)
                selection_ring.setPos(scene)
                selection_ring.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
                selection_ring.setPen(QPen(QColor(ACCENT), 1.0))
                selection_ring.setBrush(Qt.NoBrush)
                self._scene.addItem(selection_ring)

            label = QGraphicsSimpleTextItem(point.label)
            label_font = QFont()
            label_font.setFamilies(["Inter", "Segoe UI", "Sans Serif"])
            label_font.setPixelSize(11)
            label_font.setWeight(QFont.DemiBold)
            label.setFont(label_font)
            label.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            label.setBrush(QBrush(QColor(TEXT_BRIGHT)))
            label.setPos(scene.x() + 8.0, scene.y() + 8.0)
            self._scene.addItem(label)
            self._overlay_items.extend(
                [item for item in (shadow, marker, selection_ring, label) if item is not None]
            )

            if point.residual_vector is not None:
                dx, dy = point.residual_vector
                predicted_scene = _world_to_scene((x + dx, y + dy))
                residual_line = QGraphicsLineItem(
                    scene.x(),
                    scene.y(),
                    predicted_scene.x(),
                    predicted_scene.y(),
                )
                residual_line.setPen(QPen(QColor(ERROR), 1.2, Qt.DashLine))
                self._scene.addItem(residual_line)
                self._overlay_items.append(residual_line)

                endpoint = QGraphicsEllipseItem(-4.0, -4.0, 8.0, 8.0)
                endpoint.setPos(predicted_scene)
                endpoint.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
                endpoint.setPen(QPen(QColor(ERROR), 1.2))
                endpoint.setBrush(QBrush(QColor(ERROR)))
                self._scene.addItem(endpoint)
                self._overlay_items.append(endpoint)

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton:
            self._is_panning = True
            self._last_pan_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.LeftButton and self._reference is not None:
            world = _scene_to_world(self.mapToScene(event.pos()))
            tolerance = 10.0 / max(abs(self.transform().m11()), 1e-6)
            snapped = snap_to_vertex(self._reference, world[0], world[1], tolerance=tolerance)
            if snapped is not None:
                world = snapped
            self.point_picked.emit(float(world[0]), float(world[1]))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_panning:
            delta = event.pos() - self._last_pan_pos
            self._last_pan_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return

        if self._reference is not None:
            world = _scene_to_world(self.mapToScene(event.pos()))
            self.cursor_message.emit(
                f"Reference {self._reference.units}: x={world[0]:.2f}, y={world[1]:.2f}"
            )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


def _world_to_scene(point: tuple[float, float]) -> QPointF:
    return QPointF(point[0], -point[1])


def _scene_to_world(point: QPointF) -> tuple[float, float]:
    return (float(point.x()), float(-point.y()))


def _layer_color_lookup(layers: Iterable[LayerInfo]) -> dict[str, QColor]:
    mapping: dict[str, QColor] = {}
    for layer in layers:
        mapping[layer.name] = QColor.fromHsv((layer.color * 37) % 360, 140, 220)
    return mapping
