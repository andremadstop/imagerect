"""Image viewer with zoom, pan, point picking, and overlay markers."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QWidget,
)

from core.image import image_to_rgb
from core.project import ControlPoint
from ui.theme import ACCENT, BG_DARKEST, SUCCESS, TEXT_BRIGHT, WARNING


class ImageViewer(QGraphicsView):
    """Interactive source image viewer."""

    point_picked = Signal(float, float)
    point_selected = Signal(int)
    cursor_message = Signal(str)
    clip_polygon_changed = Signal(object)
    clip_polygon_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._overlay_items: list[QGraphicsItem] = []
        self._image_shape: tuple[int, int] | None = None
        self._points: list[ControlPoint] = []
        self._is_panning = False
        self._last_pan_pos = QPoint()
        self._selected_point_id: int | None = None
        self._clip_polygon: list[tuple[float, float]] | None = None
        self._clip_polygon_mode = False
        self._clip_polygon_previous: list[tuple[float, float]] | None = None
        self._clip_polygon_working: list[tuple[float, float]] = []

        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setBackgroundBrush(QColor(BG_DARKEST))
        self.setFocusPolicy(Qt.StrongFocus)

    def set_image(self, image: np.ndarray | None) -> None:
        previous_shape = self._image_shape
        previous_transform = QTransform(self.transform())
        previous_horizontal = self.horizontalScrollBar().value()
        previous_vertical = self.verticalScrollBar().value()
        self._clear_overlays()
        self._image_shape = None
        self._points = []

        if image is None:
            self._pixmap_item.setPixmap(QPixmap())
            self.setSceneRect(0.0, 0.0, 1.0, 1.0)
            return

        qimage = _array_to_qimage(image)
        pixmap = QPixmap.fromImage(qimage)
        self._pixmap_item.setPixmap(pixmap)
        self._image_shape = image.shape[:2]
        self.setSceneRect(self._pixmap_item.boundingRect())
        if previous_shape is None or previous_shape != self._image_shape:
            self.fit_image_to_view()
            return
        self.setTransform(previous_transform)
        self.horizontalScrollBar().setValue(previous_horizontal)
        self.verticalScrollBar().setValue(previous_vertical)

    def fit_image_to_view(self) -> None:
        if self._pixmap_item.pixmap().isNull():
            return
        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)

    def set_points(
        self,
        points: Iterable[ControlPoint],
        selected_point_id: int | None = None,
    ) -> None:
        self._points = list(points)
        self._selected_point_id = selected_point_id
        self._redraw_overlays()

    def set_clip_polygon(self, polygon: list[tuple[float, float]] | None) -> None:
        self._clip_polygon = polygon
        if not self._clip_polygon_mode:
            self._clip_polygon_working = list(polygon or [])
        self._redraw_overlays()

    def set_clip_polygon_mode(self, active: bool) -> None:
        self._clip_polygon_mode = active
        if active:
            self._clip_polygon_previous = list(self._clip_polygon or [])
            self._clip_polygon_working = list(self._clip_polygon or [])
        else:
            self._clip_polygon_working = list(self._clip_polygon or [])
        self._redraw_overlays()
        self._update_cursor_for_modifiers(Qt.NoModifier)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if (
            self._clip_polygon_mode
            and event.button() == Qt.LeftButton
            and len(self._clip_polygon_working) >= 3
        ):
            self.clip_polygon_changed.emit(list(self._clip_polygon_working))
            self.clip_polygon_finished.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _redraw_overlays(self) -> None:
        self._clear_overlays()

        for point in self._points:
            if point.image_xy is None:
                continue
            x, y = point.image_xy
            color = QColor(SUCCESS) if point.is_paired else QColor(WARNING)
            if point.id == self._selected_point_id:
                color = QColor(ACCENT)

            shadow = QGraphicsEllipseItem(-6.0, -6.0, 12.0, 12.0)
            shadow.setPos(x, y)
            shadow.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            shadow.setPen(QPen(QColor(0, 0, 0, 128), 4.0))
            shadow.setBrush(Qt.NoBrush)
            self._scene.addItem(shadow)

            marker = QGraphicsEllipseItem(-6.0, -6.0, 12.0, 12.0)
            marker.setPos(x, y)
            marker.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            marker.setPen(QPen(color, 2.0))
            marker.setBrush(QBrush(color))
            self._scene.addItem(marker)

            selection_ring = None
            if point.id == self._selected_point_id:
                selection_ring = QGraphicsEllipseItem(-9.0, -9.0, 18.0, 18.0)
                selection_ring.setPos(x, y)
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
            label.setPos(x + 8.0, y + 8.0)
            self._scene.addItem(label)

            self._overlay_items.extend(
                [item for item in (shadow, marker, selection_ring, label) if item is not None]
            )

        self._draw_clip_polygon()

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus()
        if self._clip_polygon_mode and self._image_shape is not None:
            if event.button() == Qt.LeftButton:
                scene_pos = self.mapToScene(event.pos())
                width = float(self._image_shape[1])
                height = float(self._image_shape[0])
                if 0.0 <= scene_pos.x() <= width and 0.0 <= scene_pos.y() <= height:
                    self._clip_polygon_working.append((float(scene_pos.x()), float(scene_pos.y())))
                    self.clip_polygon_changed.emit(list(self._clip_polygon_working))
                    self._redraw_overlays()
                    event.accept()
                    return
            if event.button() == Qt.RightButton and self._clip_polygon_working:
                self._clip_polygon_working.pop()
                self.clip_polygon_changed.emit(list(self._clip_polygon_working))
                self._redraw_overlays()
                event.accept()
                return

        if event.button() == Qt.MiddleButton:
            self._is_panning = True
            self._last_pan_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.LeftButton and self._image_shape is not None:
            scene_pos = self.mapToScene(event.pos())
            width = float(self._image_shape[1])
            height = float(self._image_shape[0])
            if not (0.0 <= scene_pos.x() <= width and 0.0 <= scene_pos.y() <= height):
                super().mousePressEvent(event)
                return

            if event.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier):
                self.point_picked.emit(float(scene_pos.x()), float(scene_pos.y()))
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
        if self._is_panning:
            delta = event.pos() - self._last_pan_pos
            self._last_pan_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return

        if self._image_shape is not None:
            scene_pos = self.mapToScene(event.pos())
            self.cursor_message.emit(f"Image px: x={scene_pos.x():.2f}, y={scene_pos.y():.2f}")
            self._update_cursor_for_modifiers(event.modifiers())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() in {Qt.MiddleButton, Qt.LeftButton} and self._is_panning:
            self._is_panning = False
            self._update_cursor_for_modifiers(event.modifiers())
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self._clip_polygon_mode:
            if (
                event.key() in {Qt.Key_Return, Qt.Key_Enter}
                and len(self._clip_polygon_working) >= 3
            ):
                self.clip_polygon_changed.emit(list(self._clip_polygon_working))
                self.clip_polygon_finished.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Escape:
                self._clip_polygon_working = list(self._clip_polygon_previous or [])
                self.clip_polygon_changed.emit(
                    list(self._clip_polygon_previous or []) if self._clip_polygon_previous else None
                )
                self.clip_polygon_finished.emit()
                event.accept()
                return
            if event.key() == Qt.Key_Delete:
                self._clip_polygon_working = []
                self.clip_polygon_changed.emit(None)
                self._redraw_overlays()
                event.accept()
                return
        self._update_cursor_for_modifiers(event.modifiers())
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        self._update_cursor_for_modifiers(event.modifiers())
        super().keyReleaseEvent(event)

    def _find_point_at(self, position: QPoint) -> int | None:
        for point in reversed(self._points):
            if point.image_xy is None:
                continue
            screen_pos = self.mapFromScene(point.image_xy[0], point.image_xy[1])
            if (screen_pos - position).manhattanLength() <= 15:
                return point.id
        return None

    def _update_cursor_for_modifiers(self, modifiers: object) -> None:
        if self._is_panning:
            return
        if self._clip_polygon_mode:
            self.setCursor(Qt.CrossCursor)
            return
        if modifiers & (Qt.ControlModifier | Qt.ShiftModifier):
            self.setCursor(Qt.CrossCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def _draw_clip_polygon(self) -> None:
        polygon_points = (
            self._clip_polygon_working if self._clip_polygon_mode else (self._clip_polygon or [])
        )
        if not polygon_points or self._image_shape is None:
            return

        polygon = QPolygonF([QPointF(x, y) for x, y in polygon_points])
        if len(polygon_points) >= 3:
            outside = QPainterPath()
            outside.addRect(0.0, 0.0, float(self._image_shape[1]), float(self._image_shape[0]))
            inside = QPainterPath()
            inside.addPolygon(polygon)
            outside = outside.subtracted(inside)
            outside_item = QGraphicsPathItem(outside)
            outside_item.setPen(QPen(Qt.NoPen))
            outside_item.setBrush(QBrush(QColor(0, 0, 0, 76)))
            self._scene.addItem(outside_item)
            self._overlay_items.append(outside_item)

            polygon_item = QGraphicsPolygonItem(polygon)
            fill = QColor(ACCENT)
            fill.setAlpha(26)
            polygon_item.setBrush(QBrush(fill))
        else:
            polygon_item = QGraphicsPolygonItem(polygon)
            polygon_item.setBrush(QBrush(Qt.NoBrush))

        polygon_item.setPen(QPen(QColor(ACCENT), 1.5, Qt.DashLine))
        self._scene.addItem(polygon_item)
        self._overlay_items.append(polygon_item)

        for x, y in polygon_points:
            vertex = QGraphicsRectItem(-2.5, -2.5, 5.0, 5.0)
            vertex.setPos(x, y)
            vertex.setPen(QPen(QColor(ACCENT), 1.0))
            vertex.setBrush(QBrush(QColor(ACCENT)))
            vertex.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
            self._scene.addItem(vertex)
            self._overlay_items.append(vertex)

    def _clear_overlays(self) -> None:
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items.clear()


def _array_to_qimage(image: np.ndarray) -> QImage:
    rgb = np.ascontiguousarray(image_to_rgb(image))
    height, width = rgb.shape[:2]
    if rgb.ndim == 2:
        qimage = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format_Grayscale8)
    elif rgb.shape[2] == 4:
        qimage = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format_RGBA8888)
    else:
        qimage = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format_RGB888)
    return qimage.copy()
