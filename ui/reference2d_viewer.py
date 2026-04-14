"""DXF reference viewer with snapping, layer visibility, and residual overlays."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QKeyEvent, QMouseEvent, QPen, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsRectItem,
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
    point_selected = Signal(int)
    cursor_message = Signal(str)
    reference_roi_changed = Signal(object)
    reference_roi_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._reference: Reference2D | None = None
        self._layer_items: dict[str, list[QGraphicsLineItem]] = {}
        self._overlay_items: list[QGraphicsItem] = []
        self._points: list[ControlPoint] = []
        self._gps_markers: list[tuple[str, tuple[float, float]]] = []
        self._selected_point_id: int | None = None
        self._is_panning = False
        self._last_pan_pos = QPoint()
        self._reference_roi: tuple[float, float, float, float] | None = None
        self._reference_roi_mode = False
        self._reference_roi_start: tuple[float, float] | None = None
        self._reference_roi_previous: tuple[float, float, float, float] | None = None
        self._roi_zoom_pending = False

        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setBackgroundBrush(QColor(BG_DARKEST))
        self.setFocusPolicy(Qt.StrongFocus)

    def set_reference(self, reference: Reference2D | None) -> None:
        reference_changed = reference is not self._reference
        self._reference = reference
        self._rebuild_scene()
        if reference_changed and reference is not None:
            self._fit_scene_to_view()

    def _rebuild_scene(self) -> None:
        self._scene.clear()
        self._layer_items = {}
        self._overlay_items.clear()
        self._points = []
        if self._reference is None:
            self.setSceneRect(0.0, 0.0, 1.0, 1.0)
            return

        colors = _layer_color_lookup(self._reference.layers)
        for segment in self._reference.segments:
            start = _world_to_scene(segment.start)
            end = _world_to_scene(segment.end)
            item = QGraphicsLineItem(start.x(), start.y(), end.x(), end.y())
            item.setPen(QPen(colors.get(segment.layer, QColor("#b7b7b7")), 0.0))
            self._scene.addItem(item)
            self._layer_items.setdefault(segment.layer, []).append(item)

        ext_min = self._reference.extents_min
        ext_max = self._reference.extents_max
        margin = max((ext_max[0] - ext_min[0]) * 0.05, (ext_max[1] - ext_min[1]) * 0.05, 10.0)
        self.setSceneRect(
            ext_min[0] - margin,
            -ext_max[1] - margin,
            (ext_max[0] - ext_min[0]) + margin * 2.0,
            (ext_max[1] - ext_min[1]) + margin * 2.0,
        )
        self._update_geometry_opacity()
        self._redraw_overlays()
        self._apply_pending_roi_zoom()

    def _fit_scene_to_view(self) -> None:
        self.resetTransform()
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)

    def fit_reference_to_view(self) -> None:
        self._fit_scene_to_view()

    def _fit_roi_to_view(self) -> None:
        if self._reference_roi is None or not _is_meaningful_roi(self._reference_roi):
            return
        x0, y0, x1, y1 = self._reference_roi
        self.resetTransform()
        self.fitInView(QRectF(x0, -y1, x1 - x0, y1 - y0), Qt.KeepAspectRatio)

    def fit_reference_roi_to_view(self) -> None:
        self._fit_roi_to_view()

    def _apply_pending_roi_zoom(self) -> None:
        if self._reference_roi_mode or not self._roi_zoom_pending:
            return
        self._fit_roi_to_view()
        self._roi_zoom_pending = False

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
        self._selected_point_id = selected_point_id
        self._points = list(points)
        self._redraw_overlays()

    def set_gps_markers(self, markers: Iterable[tuple[str, tuple[float, float]]]) -> None:
        self._gps_markers = list(markers)
        self._redraw_overlays()

    def set_reference_roi(self, reference_roi: tuple[float, float, float, float] | None) -> None:
        normalized_roi = _normalize_roi(reference_roi) if reference_roi is not None else None
        if normalized_roi is None:
            self._roi_zoom_pending = False
        elif _is_meaningful_roi(normalized_roi) and not _is_meaningful_roi(self._reference_roi):
            self._roi_zoom_pending = True
        self._reference_roi = normalized_roi
        self._update_geometry_opacity()
        self._redraw_overlays()

    def set_reference_roi_mode(self, active: bool) -> None:
        self._reference_roi_mode = active
        self._reference_roi_start = None
        if active:
            self._reference_roi_previous = self._reference_roi
        self._update_cursor_for_modifiers(Qt.NoModifier)
        self._redraw_overlays()

    def _redraw_overlays(self) -> None:
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items.clear()

        for point in self._points:
            if point.reference_xy is None:
                continue

            x, y = point.reference_xy
            scene = _world_to_scene((x, y))
            color = QColor(SUCCESS) if point.is_paired else QColor(WARNING)
            if point.id == self._selected_point_id:
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
            if point.id == self._selected_point_id:
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

        for label_text, world_xy in self._gps_markers:
            scene = _world_to_scene(world_xy)
            gps_marker = QGraphicsRectItem(-5.0, -5.0, 10.0, 10.0)
            gps_marker.setPos(scene)
            gps_marker.setRotation(45.0)
            gps_marker.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            gps_marker.setPen(QPen(QColor(ACCENT), 1.5))
            gps_marker.setBrush(QBrush(QColor(ACCENT)))
            self._scene.addItem(gps_marker)
            self._overlay_items.append(gps_marker)

            label = QGraphicsSimpleTextItem(label_text)
            label_font = QFont()
            label_font.setFamilies(["Inter", "Segoe UI", "Sans Serif"])
            label_font.setPixelSize(11)
            label_font.setWeight(QFont.DemiBold)
            label.setFont(label_font)
            label.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            label.setBrush(QBrush(QColor(TEXT_BRIGHT)))
            label.setPos(scene.x() + 10.0, scene.y() - 16.0)
            self._scene.addItem(label)
            self._overlay_items.append(label)

        if self._reference_roi is not None:
            self._draw_reference_roi(self._reference_roi)

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus()
        if (
            self._reference_roi_mode
            and self._reference is not None
            and event.button() == Qt.LeftButton
        ):
            self._reference_roi_start = _scene_to_world(self.mapToScene(event.pos()))
            roi = (*self._reference_roi_start, *self._reference_roi_start)
            self.reference_roi_changed.emit(roi)
            event.accept()
            return

        if event.button() == Qt.MiddleButton:
            self._is_panning = True
            self._last_pan_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.LeftButton and self._reference is not None:
            if event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier):
                world = _scene_to_world(self.mapToScene(event.pos()))
                tolerance = 10.0 / max(abs(self.transform().m11()), 1e-6)
                snapped = snap_to_vertex(self._reference, world[0], world[1], tolerance=tolerance)
                if snapped is not None:
                    world = snapped
                self.point_picked.emit(float(world[0]), float(world[1]))
                event.accept()
                return

            existing_point_id = self._find_point_at(event.pos())
            if existing_point_id is not None:
                self.point_selected.emit(existing_point_id)
                event.accept()
                return

            self._is_panning = True
            self._last_pan_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._reference_roi_mode
            and self._reference is not None
            and self._reference_roi_start is not None
        ):
            current = _scene_to_world(self.mapToScene(event.pos()))
            roi = _normalize_roi((*self._reference_roi_start, *current))
            self.reference_roi_changed.emit(roi)
            self._update_cursor_for_modifiers(event.modifiers())
            event.accept()
            return

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
            self._update_cursor_for_modifiers(event.modifiers())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            self._reference_roi_mode
            and event.button() == Qt.LeftButton
            and self._reference_roi_start is not None
        ):
            current = _scene_to_world(self.mapToScene(event.pos()))
            roi = _normalize_roi((*self._reference_roi_start, *current))
            self._reference_roi_start = None
            self.reference_roi_changed.emit(roi)
            self.reference_roi_finished.emit()
            event.accept()
            return

        if event.button() in {Qt.MiddleButton, Qt.LeftButton} and self._is_panning:
            self._is_panning = False
            self._update_cursor_for_modifiers(event.modifiers())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._reference_roi_mode and event.key() == Qt.Key_Escape:
            self._reference_roi_start = None
            self.reference_roi_changed.emit(None)
            self.reference_roi_finished.emit()
            event.accept()
            return
        self._update_cursor_for_modifiers(event.modifiers())
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        self._update_cursor_for_modifiers(event.modifiers())
        super().keyReleaseEvent(event)

    def _find_point_at(self, position: QPoint) -> int | None:
        for point in reversed(self._points):
            if point.reference_xy is None:
                continue
            scene_pos = _world_to_scene(point.reference_xy)
            screen_pos = self.mapFromScene(scene_pos)
            if (screen_pos - position).manhattanLength() <= 15:
                return point.id
        return None

    def _update_cursor_for_modifiers(self, modifiers: object) -> None:
        if self._is_panning:
            return
        if self._reference_roi_mode:
            self.setCursor(Qt.CrossCursor)
            return
        if modifiers & (Qt.ControlModifier | Qt.ShiftModifier):
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def _draw_reference_roi(self, roi: tuple[float, float, float, float]) -> None:
        x0, y0, x1, y1 = _normalize_roi(roi)
        rect_item = QGraphicsRectItem(x0, -y1, x1 - x0, y1 - y0)
        rect_item.setPen(QPen(QColor(ACCENT), 1.5, Qt.DashLine))
        rect_item.setBrush(QBrush(Qt.NoBrush))
        self._scene.addItem(rect_item)
        self._overlay_items.append(rect_item)

    def _update_geometry_opacity(self) -> None:
        if self._reference is None:
            return
        roi = _normalize_roi(self._reference_roi) if self._reference_roi is not None else None
        for items in self._layer_items.values():
            for item in items:
                if roi is None:
                    item.setOpacity(1.0)
                    continue
                line = item.line()
                mid_x = (line.x1() + line.x2()) * 0.5
                mid_y = (line.y1() + line.y2()) * 0.5
                world_x, world_y = _scene_to_world(QPointF(mid_x, mid_y))
                inside = roi[0] <= world_x <= roi[2] and roi[1] <= world_y <= roi[3]
                item.setOpacity(1.0 if inside else 0.2)


def _world_to_scene(point: tuple[float, float]) -> QPointF:
    return QPointF(point[0], -point[1])


def _scene_to_world(point: QPointF) -> tuple[float, float]:
    return (float(point.x()), float(-point.y()))


def _layer_color_lookup(layers: Iterable[LayerInfo]) -> dict[str, QColor]:
    mapping: dict[str, QColor] = {}
    for layer in layers:
        mapping[layer.name] = QColor.fromHsv((layer.color * 37) % 360, 140, 220)
    return mapping


def _normalize_roi(
    roi: tuple[float, float, float, float] | None,
) -> tuple[float, float, float, float]:
    if roi is None:
        return (0.0, 0.0, 0.0, 0.0)
    x0, y0, x1, y1 = roi
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _is_meaningful_roi(roi: tuple[float, float, float, float] | None) -> bool:
    if roi is None:
        return False
    x0, y0, x1, y1 = roi
    return x1 > x0 and y1 > y0
