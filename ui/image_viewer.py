"""Image viewer with zoom, pan, point picking, and overlay markers."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QMouseEvent,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPixmapItem,
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
    cursor_message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._overlay_items: list[QGraphicsItem] = []
        self._image_shape: tuple[int, int] | None = None
        self._is_panning = False
        self._last_pan_pos = QPoint()

        self.setRenderHints(self.renderHints())
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setBackgroundBrush(QColor(BG_DARKEST))

    def set_image(self, image: np.ndarray | None) -> None:
        self._scene.clear()
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._overlay_items.clear()
        self._image_shape = None

        if image is None:
            self.setSceneRect(0.0, 0.0, 1.0, 1.0)
            return

        qimage = _array_to_qimage(image)
        pixmap = QPixmap.fromImage(qimage)
        self._pixmap_item.setPixmap(pixmap)
        self._image_shape = image.shape[:2]
        self.setSceneRect(self._pixmap_item.boundingRect())
        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.KeepAspectRatio)

    def set_points(
        self,
        points: Iterable[ControlPoint],
        selected_point_id: int | None = None,
    ) -> None:
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items.clear()

        for point in points:
            if point.image_xy is None:
                continue
            x, y = point.image_xy
            color = QColor(SUCCESS) if point.is_paired else QColor(WARNING)
            if point.id == selected_point_id:
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
            if point.id == selected_point_id:
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

        if event.button() == Qt.LeftButton and self._image_shape is not None:
            scene_pos = self.mapToScene(event.pos())
            width = float(self._image_shape[1])
            height = float(self._image_shape[0])
            if 0.0 <= scene_pos.x() <= width and 0.0 <= scene_pos.y() <= height:
                self.point_picked.emit(float(scene_pos.x()), float(scene_pos.y()))
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
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)


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
