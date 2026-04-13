"""Lightweight integrated 3D reference viewer for point clouds and meshes."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen, QPolygonF, QWheelEvent
from PySide6.QtWidgets import QWidget

from core.reference3d import (
    Reference3D,
    WorkingPlane,
    plane_corners_from_extents,
    reference_plane_extents,
    reference_source_points,
)
from ui.theme import ACCENT, BG_DARKEST, BORDER, SUCCESS, TEXT_DIM


class Reference3DViewer(QWidget):
    """Simple Qt-native 3D viewer with orbit, pan, zoom, and point picking."""

    point_picked = Signal(float, float, float)
    cursor_message = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reference: Reference3D | None = None
        self._display_points = np.empty((0, 3), dtype=np.float64)
        self._display_edges = np.empty((0, 2), dtype=np.int32)
        self._projected_points = np.empty((0, 2), dtype=np.float64)
        self._projection_scale = 1.0
        self._center = np.zeros(3, dtype=np.float64)
        self._zoom = 1.0
        self._pan = QPointF(0.0, 0.0)
        self._yaw = 0.55
        self._pitch = -0.55
        self._last_pos = QPoint()
        self._is_panning = False
        self._is_rotating = False
        self._control_points: dict[int, np.ndarray] = {}
        self._selected_point_id: int | None = None
        self._temporary_points: list[np.ndarray] = []
        self._plane_extents: tuple[tuple[float, float], tuple[float, float]] | None = None

        self.setMouseTracking(True)
        self.setMinimumHeight(240)

    def set_reference(self, reference: Reference3D | None) -> None:
        self._reference = reference
        self._display_points = np.empty((0, 3), dtype=np.float64)
        self._display_edges = np.empty((0, 2), dtype=np.int32)
        self._projected_points = np.empty((0, 2), dtype=np.float64)
        self._temporary_points = []

        if reference is not None:
            source_points = reference_source_points(reference)
            if source_points is not None:
                self._display_points = _sample_points(source_points, max_points=50_000)
                self._center = self._display_points.mean(axis=0)
            else:
                self._center = np.zeros(3, dtype=np.float64)
            if reference.vertices is not None and reference.faces is not None:
                self._display_points = reference.vertices
                self._display_edges = _mesh_edges(reference.faces, max_edges=25_000)
                self._center = reference.vertices.mean(axis=0)
            self._zoom = 1.0
            self._pan = QPointF(0.0, 0.0)
            self._plane_extents = (
                reference_plane_extents(reference) if reference.working_plane is not None else None
            )
        self.update()

    def set_working_plane(
        self,
        plane: WorkingPlane | None,
        extents: tuple[tuple[float, float], tuple[float, float]] | None = None,
    ) -> None:
        if self._reference is not None:
            self._reference.working_plane = plane
        if plane is None:
            self._plane_extents = None
        elif extents is not None:
            self._plane_extents = extents
        elif self._reference is not None:
            self._plane_extents = reference_plane_extents(self._reference)
        self.update()

    def set_control_points(
        self,
        control_points: dict[int, np.ndarray],
        selected_point_id: int | None = None,
    ) -> None:
        self._control_points = {
            point_id: np.asarray(value, dtype=np.float64)
            for point_id, value in control_points.items()
        }
        self._selected_point_id = selected_point_id
        self.update()

    def set_temporary_points(self, points: Iterable[np.ndarray]) -> None:
        self._temporary_points = [np.asarray(point, dtype=np.float64) for point in points]
        self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._zoom *= 1.12 if event.angleDelta().y() > 0 else 1.0 / 1.12
        self._zoom = max(self._zoom, 0.05)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._last_pos = event.pos()
        if event.button() == Qt.MiddleButton:
            self._is_panning = True
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.RightButton:
            self._is_rotating = True
            self.setCursor(Qt.SizeAllCursor)
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            point = self._pick_display_point(event.pos())
            if point is not None:
                self.point_picked.emit(float(point[0]), float(point[1]), float(point[2]))
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._is_panning:
            delta = event.pos() - self._last_pos
            self._last_pos = event.pos()
            self._pan += QPointF(delta.x(), delta.y())
            self.update()
            event.accept()
            return
        if self._is_rotating:
            delta = event.pos() - self._last_pos
            self._last_pos = event.pos()
            self._yaw += delta.x() * 0.01
            self._pitch += delta.y() * 0.01
            self.update()
            event.accept()
            return

        point = self._pick_display_point(event.pos(), tolerance=12.0)
        if point is not None:
            self.cursor_message.emit(
                f"3D point: x={point[0]:.3f}, y={point[1]:.3f}, z={point[2]:.3f}"
            )
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MiddleButton:
            self._is_panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        if event.button() == Qt.RightButton:
            self._is_rotating = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(BG_DARKEST))

        if self._reference is None or len(self._display_points) == 0:
            painter.setPen(QColor(TEXT_DIM))
            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                "Load an E57 point cloud or OBJ mesh",
            )
            painter.end()
            return

        points_2d, depths = self._project_points(self._display_points)
        self._projected_points = points_2d

        if len(self._display_edges) > 0:
            painter.setPen(QPen(QColor(BORDER), 1.0))
            for start_index, end_index in self._display_edges:
                start = QPointF(*points_2d[start_index])
                end = QPointF(*points_2d[end_index])
                painter.drawLine(start, end)

        z_values = self._display_points[:, 2]
        z_min = float(z_values.min())
        z_span = max(float(z_values.max()) - z_min, 1e-9)
        for screen_point, depth, world_point in zip(
            points_2d,
            depths,
            self._display_points,
            strict=True,
        ):
            alpha = max(40, min(220, int(160 + depth * 0.2)))
            hue_mix = (float(world_point[2]) - z_min) / z_span
            color = QColor(ACCENT)
            color = color.lighter(int(85 + 40 * hue_mix))
            color.setAlpha(alpha)
            painter.setPen(QPen(color, 3.0))
            painter.drawPoint(QPointF(*screen_point))

        if self._reference.working_plane is not None and self._plane_extents is not None:
            plane_corners = plane_corners_from_extents(
                self._reference.working_plane,
                self._plane_extents,
            )
            corners_2d, _ = self._project_points(plane_corners)
            polygon = QPolygonF([QPointF(*corner) for corner in corners_2d])
            painter.setPen(QPen(QColor(ACCENT), 1.2))
            fill = QColor(ACCENT)
            fill.setAlpha(40)
            painter.setBrush(fill)
            painter.drawPolygon(polygon)

        for point_id, world_point in self._control_points.items():
            highlight = self._project_points(np.asarray([world_point], dtype=np.float64))[0][0]
            painter.setBrush(QColor(SUCCESS if point_id != self._selected_point_id else ACCENT))
            painter.setPen(QPen(QColor(0, 0, 0, 180), 1.5))
            radius = 5.0 if point_id != self._selected_point_id else 7.0
            painter.drawEllipse(QPointF(*highlight), radius, radius)

        for world_point in self._temporary_points:
            temp = self._project_points(np.asarray([world_point], dtype=np.float64))[0][0]
            painter.setBrush(QColor(ACCENT))
            painter.setPen(QPen(QColor(255, 255, 255, 200), 1.0))
            painter.drawEllipse(QPointF(*temp), 6.0, 6.0)

        painter.end()

    def _project_points(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        rotation = _rotation_matrix(self._yaw, self._pitch)
        centered = points - self._center
        rotated = centered @ rotation.T
        span = np.ptp(rotated[:, :2], axis=0)
        scale_base = max(float(np.max(span)), 1e-6)
        scale = min(self.width(), self.height()) * 0.42 / scale_base * self._zoom
        self._projection_scale = scale
        screen = np.empty((len(points), 2), dtype=np.float64)
        screen[:, 0] = rotated[:, 0] * scale + self.width() * 0.5 + self._pan.x()
        screen[:, 1] = -rotated[:, 1] * scale + self.height() * 0.5 + self._pan.y()
        return screen, rotated[:, 2]

    def _pick_display_point(
        self,
        position: QPoint,
        tolerance: float = 10.0,
    ) -> np.ndarray | None:
        if len(self._display_points) == 0:
            return None
        if len(self._projected_points) != len(self._display_points):
            self._projected_points, _ = self._project_points(self._display_points)
        click = np.array([float(position.x()), float(position.y())], dtype=np.float64)
        distances = np.linalg.norm(self._projected_points - click, axis=1)
        index = int(np.argmin(distances))
        if float(distances[index]) > tolerance:
            return None
        return np.asarray(self._display_points[index], dtype=np.float64)


def _rotation_matrix(yaw: float, pitch: float) -> np.ndarray:
    cos_yaw = float(np.cos(yaw))
    sin_yaw = float(np.sin(yaw))
    cos_pitch = float(np.cos(pitch))
    sin_pitch = float(np.sin(pitch))
    rotation_yaw = np.array(
        [[cos_yaw, 0.0, sin_yaw], [0.0, 1.0, 0.0], [-sin_yaw, 0.0, cos_yaw]],
        dtype=np.float64,
    )
    rotation_pitch = np.array(
        [[1.0, 0.0, 0.0], [0.0, cos_pitch, -sin_pitch], [0.0, sin_pitch, cos_pitch]],
        dtype=np.float64,
    )
    return rotation_pitch @ rotation_yaw


def _sample_points(points: np.ndarray, max_points: int) -> np.ndarray:
    if len(points) <= max_points:
        return np.asarray(points, dtype=np.float64)
    step = max(len(points) // max_points, 1)
    return np.asarray(points[::step][:max_points], dtype=np.float64)


def _mesh_edges(faces: np.ndarray, max_edges: int) -> np.ndarray:
    edges = set()
    for face in np.asarray(faces, dtype=np.int32):
        indices = [int(face[0]), int(face[1]), int(face[2])]
        for start, end in (
            (indices[0], indices[1]),
            (indices[1], indices[2]),
            (indices[2], indices[0]),
        ):
            if start == end:
                continue
            edges.add(tuple(sorted((start, end))))
            if len(edges) >= max_edges:
                return np.asarray(sorted(edges), dtype=np.int32)
    return np.asarray(sorted(edges), dtype=np.int32)
