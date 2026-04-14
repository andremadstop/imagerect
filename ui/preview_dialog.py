"""Export preview dialog with overlays and quality information."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import pairwise

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.export import (
    MosaicSource,
    RectifiedImageRenderResult,
    build_canvas,
    estimate_output_size_bytes,
    render_mosaic_image,
    render_rectified_image,
)
from core.image import image_to_rgb
from core.project import ControlPoint, ExportSettings, Point2D, ReferenceRoi, unit_to_mm
from core.reference2d import Reference2D
from ui.theme import ACCENT, SUCCESS, WARNING


class PreviewDialog(QDialog):
    """Preview the export result before writing to disk."""

    def __init__(
        self,
        export_settings: ExportSettings,
        units: str,
        project_name: str,
        total_point_count: int,
        reference_extents: tuple[Point2D, Point2D],
        source_image: np.ndarray | None = None,
        homography_image_to_reference: np.ndarray | None = None,
        control_points: Sequence[ControlPoint] | None = None,
        rms_error: float | None = None,
        warnings: Sequence[str] = (),
        reference_2d: Reference2D | None = None,
        clip_polygon: Sequence[Point2D] | None = None,
        reference_roi: ReferenceRoi | None = None,
        mosaic_sources: Sequence[MosaicSource] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Preview")

        screen = QApplication.primaryScreen()
        if screen is not None:
            geometry = screen.availableGeometry()
            self.resize(int(geometry.width() * 0.8), int(geometry.height() * 0.8))
        else:
            self.resize(1440, 900)

        self._render_settings = export_settings
        self._units = units
        self._project_name = project_name
        self._rms_error = rms_error
        self._warnings = list(warnings)
        self._reference_2d = reference_2d
        self._total_point_count = total_point_count
        self._reference_roi = reference_roi
        self._mosaic_source_count = len(mosaic_sources or [])
        self._control_points: list[ControlPoint] = []
        self._clip_overlays: list[tuple[list[Point2D], np.ndarray]] = []
        self._actual_bounds = (
            _roi_bounds(reference_roi)
            if export_settings.use_reference_roi and reference_roi is not None
            else reference_extents
        )
        self._actual_width, self._actual_height, _ = build_canvas(
            self._actual_bounds[0],
            self._actual_bounds[1],
            export_settings.pixel_size / unit_to_mm(units),
        )
        preview_pixel_size = _preview_pixel_size(
            export_settings.pixel_size,
            units,
            self._actual_bounds,
        )
        if mosaic_sources:
            self._control_points = [
                point for source in mosaic_sources for point in source.control_points
            ]
            self._clip_overlays = [
                (list(source.clip_polygon), source.homography_image_to_reference)
                for source in mosaic_sources
                if source.clip_polygon
            ]
            self._rendered_preview = render_mosaic_image(
                sources=mosaic_sources,
                pixel_size=preview_pixel_size,
                units=units,
                bit_depth=export_settings.bit_depth,
                resampling=export_settings.resampling,
                clip_to_hull=export_settings.clip_to_hull,
                reference_roi=reference_roi if export_settings.use_reference_roi else None,
                reference_extents=reference_extents,
                blend_radius_px=export_settings.mosaic_feather_radius_px,
            )
        else:
            if source_image is None or homography_image_to_reference is None:
                raise ValueError("Single-image preview requires image data and a homography.")
            self._control_points = list(control_points or [])
            if clip_polygon is not None:
                self._clip_overlays = [(list(clip_polygon), homography_image_to_reference)]
            self._rendered_preview = render_rectified_image(
                source_image=source_image,
                homography_image_to_reference=homography_image_to_reference,
                control_points=self._control_points,
                pixel_size=preview_pixel_size,
                units=units,
                bit_depth=export_settings.bit_depth,
                resampling=export_settings.resampling,
                clip_to_hull=export_settings.clip_to_hull,
                clip_polygon=clip_polygon if export_settings.use_clip_polygon else None,
                reference_roi=reference_roi if export_settings.use_reference_roi else None,
                reference_extents=reference_extents,
            )

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background: #12141b; border-radius: 8px;")
        self.preview_label.setMinimumSize(640, 480)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.preview_label)
        scroll_area.setFrameShape(QFrame.NoFrame)

        self.overlay_dxf = QCheckBox("DXF geometry")
        self.overlay_dxf.setChecked(reference_2d is not None)
        self.overlay_dxf.setEnabled(reference_2d is not None)
        self.overlay_points = QCheckBox("Control points")
        self.overlay_points.setChecked(True)
        self.overlay_clip_polygon = QCheckBox("Clip polygon")
        self.overlay_clip_polygon.setChecked(bool(self._clip_overlays))
        self.overlay_clip_polygon.setEnabled(bool(self._clip_overlays))
        self.overlay_reference_roi = QCheckBox("DXF ROI")
        self.overlay_reference_roi.setChecked(reference_roi is not None)
        self.overlay_reference_roi.setEnabled(reference_roi is not None)
        self.overlay_checkerboard = QCheckBox("Checkerboard")

        overlay_group = QGroupBox("Overlays")
        overlay_layout = QVBoxLayout(overlay_group)
        overlay_layout.setContentsMargins(12, 16, 12, 12)
        overlay_layout.setSpacing(10)
        overlay_layout.addWidget(self.overlay_dxf)
        overlay_layout.addWidget(self.overlay_points)
        overlay_layout.addWidget(self.overlay_clip_polygon)
        overlay_layout.addWidget(self.overlay_reference_roi)
        overlay_layout.addWidget(self.overlay_checkerboard)

        info_group = QGroupBox("Info")
        info_form = QFormLayout(info_group)
        info_form.setContentsMargins(12, 16, 12, 12)
        info_form.setSpacing(10)
        info_form.addRow(
            "Output canvas",
            QLabel(f"{self._actual_width:,} x {self._actual_height:,} px"),
        )
        info_form.addRow("Pixel size", QLabel(f"{export_settings.pixel_size:.4f} mm/px"))
        info_form.addRow("Scale", QLabel(f"1:{export_settings.scale_denominator:.2f}"))
        info_form.addRow("DPI", QLabel(f"{export_settings.dpi:.0f}"))
        info_form.addRow("Format", QLabel(_format_summary(export_settings)))
        info_form.addRow(
            "Estimated size",
            QLabel(_estimate_summary(self._actual_width, self._actual_height, export_settings)),
        )
        info_form.addRow("RMS error", QLabel(_rms_summary(rms_error, units)))
        info_form.addRow(
            "Point count",
            QLabel(f"{len(self._control_points)} / {total_point_count} paired"),
        )
        if self._mosaic_source_count > 1:
            info_form.addRow("Sources", QLabel(str(self._mosaic_source_count)))
            info_form.addRow(
                "Feather blend",
                QLabel(f"{export_settings.mosaic_feather_radius_px} px"),
            )
        warnings_label = QLabel("\n".join(self._warnings) if self._warnings else "none")
        warnings_label.setWordWrap(True)
        warnings_label.setStyleSheet(f"color: {WARNING};")
        info_form.addRow("Warnings", warnings_label)

        side_panel = QWidget()
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(12)
        side_layout.addWidget(overlay_group)
        side_layout.addWidget(info_group)
        side_layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        export_button = buttons.button(QDialogButtonBox.Ok)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        if export_button is not None:
            export_button.setText("Export")
            export_button.setProperty("primary", True)
        if cancel_button is not None:
            cancel_button.setText("Cancel")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(16)
        body_layout.addWidget(scroll_area, stretch=4)
        body_layout.addWidget(side_panel, stretch=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(body, stretch=1)
        layout.addWidget(buttons)

        for checkbox in (
            self.overlay_dxf,
            self.overlay_points,
            self.overlay_clip_polygon,
            self.overlay_reference_roi,
            self.overlay_checkerboard,
        ):
            checkbox.toggled.connect(self._update_preview)

        self._update_preview()

    def _update_preview(self) -> None:
        preview = np.ascontiguousarray(image_to_rgb(self._rendered_preview.image))
        if self.overlay_checkerboard.isChecked():
            _apply_checkerboard(preview)
        if self.overlay_dxf.isChecked() and self._reference_2d is not None:
            _draw_reference_overlay(preview, self._reference_2d, self._rendered_preview)
        if self.overlay_points.isChecked():
            _draw_point_overlay(preview, self._control_points, self._rendered_preview)
        if self.overlay_clip_polygon.isChecked():
            for polygon, homography in self._clip_overlays:
                _draw_clip_polygon_overlay(
                    preview,
                    polygon,
                    homography,
                    self._rendered_preview,
                )
        if self.overlay_reference_roi.isChecked() and self._reference_roi is not None:
            _draw_reference_roi_overlay(preview, self._reference_roi, self._rendered_preview)
        self.preview_label.setPixmap(_pixmap_from_rgb(preview))


def _preview_pixel_size(
    pixel_size_mm: float,
    units: str,
    bounds: tuple[Point2D, Point2D],
) -> float:
    width, height, _ = build_canvas(bounds[0], bounds[1], pixel_size_mm / unit_to_mm(units))
    longest = max(width, height)
    if longest <= 2500:
        return pixel_size_mm
    return pixel_size_mm * (longest / 2500.0)


def _format_summary(settings: ExportSettings) -> str:
    layers = "3 layers" if settings.multi_layer else "1 layer"
    details = [settings.compression.upper(), f"{settings.bit_depth}-bit", layers]
    return f"{settings.output_format.upper()} ({', '.join(details)})"


def _estimate_summary(width: int, height: int, settings: ExportSettings) -> str:
    layer_count = 4 if settings.multi_layer else 1
    size = estimate_output_size_bytes(width, height, settings.bit_depth, layer_count=layer_count)
    return _format_bytes(size)


def _rms_summary(rms_error: float | None, units: str) -> str:
    if rms_error is None:
        return "n/a"
    return f"{rms_error:.3f} {units}"


def _draw_reference_overlay(
    image: np.ndarray,
    reference: Reference2D,
    rendered: RectifiedImageRenderResult,
) -> None:
    overlay = image.copy()
    color = (255, 255, 255)
    for segment in reference.segments:
        points = _reference_to_canvas_points(
            [segment.start, segment.end],
            rendered.reference_to_canvas,
        )
        start = _pixel_point(points[0])
        end = _pixel_point(points[1])
        cv2.line(overlay, start, end, color, 1, cv2.LINE_AA)
    cv2.addWeighted(overlay, 0.45, image, 0.55, 0.0, dst=image)


def _draw_point_overlay(
    image: np.ndarray,
    control_points: Sequence[ControlPoint],
    rendered: RectifiedImageRenderResult,
) -> None:
    color = _hex_to_rgb(SUCCESS)
    for point in control_points:
        if point.reference_xy is None:
            continue
        canvas_point = _reference_to_canvas_points(
            [point.reference_xy],
            rendered.reference_to_canvas,
        )[0]
        center = _pixel_point(canvas_point)
        cv2.circle(image, center, 5, color, -1, cv2.LINE_AA)
        cv2.putText(
            image,
            point.label,
            (center[0] + 8, center[1] - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )


def _draw_clip_polygon_overlay(
    image: np.ndarray,
    clip_polygon: Sequence[Point2D],
    homography_image_to_reference: np.ndarray,
    rendered: RectifiedImageRenderResult,
) -> None:
    projected = cv2.perspectiveTransform(
        np.asarray(clip_polygon, dtype=np.float32).reshape(-1, 1, 2),
        homography_image_to_reference,
    ).reshape(-1, 2)
    canvas_points = _reference_to_canvas_points(
        [(float(x), float(y)) for x, y in projected],
        rendered.reference_to_canvas,
    )
    _draw_dashed_polyline(image, canvas_points, _hex_to_rgb(ACCENT), closed=True)


def _draw_reference_roi_overlay(
    image: np.ndarray,
    reference_roi: ReferenceRoi,
    rendered: RectifiedImageRenderResult,
) -> None:
    bounds_min, bounds_max = _roi_bounds(reference_roi)
    x0, y0 = bounds_min
    x1, y1 = bounds_max
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    canvas_points = _reference_to_canvas_points(corners, rendered.reference_to_canvas)
    _draw_dashed_polyline(image, canvas_points, _hex_to_rgb(ACCENT), closed=True)


def _reference_to_canvas_points(
    points: Sequence[Point2D],
    reference_to_canvas: np.ndarray,
) -> np.ndarray:
    transformed = cv2.perspectiveTransform(
        np.asarray(points, dtype=np.float32).reshape(-1, 1, 2),
        reference_to_canvas.astype(np.float32),
    )
    return transformed.reshape(-1, 2)


def _draw_dashed_polyline(
    image: np.ndarray,
    points: np.ndarray,
    color: tuple[int, int, int],
    closed: bool,
    dash_length: float = 14.0,
    gap_length: float = 8.0,
) -> None:
    if len(points) < 2:
        return
    point_list = points.tolist()
    if closed:
        point_list.append(point_list[0])

    for start, end in pairwise(point_list):
        start_array = np.asarray(start, dtype=np.float32)
        end_array = np.asarray(end, dtype=np.float32)
        length = float(np.linalg.norm(end_array - start_array))
        if length <= 0.0:
            continue
        direction = (end_array - start_array) / length
        distance = 0.0
        while distance < length:
            dash_end = min(distance + dash_length, length)
            segment_start = start_array + direction * distance
            segment_end = start_array + direction * dash_end
            cv2.line(
                image,
                _pixel_point(segment_start),
                _pixel_point(segment_end),
                color,
                2,
                cv2.LINE_AA,
            )
            distance += dash_length + gap_length


def _apply_checkerboard(image: np.ndarray, cell_size: int = 32) -> None:
    overlay = image.copy()
    for y in range(0, image.shape[0], cell_size):
        for x in range(0, image.shape[1], cell_size):
            if ((x // cell_size) + (y // cell_size)) % 2 == 0:
                cv2.rectangle(
                    overlay,
                    (x, y),
                    (min(x + cell_size, image.shape[1]), min(y + cell_size, image.shape[0])),
                    (255, 255, 255),
                    -1,
                )
    cv2.addWeighted(overlay, 0.06, image, 0.94, 0.0, dst=image)


def _pixmap_from_rgb(image: np.ndarray) -> QPixmap:
    qimage = QImage(
        image.data,
        image.shape[1],
        image.shape[0],
        image.strides[0],
        QImage.Format_RGB888,
    )
    return QPixmap.fromImage(qimage.copy())


def _pixel_point(point: np.ndarray) -> tuple[int, int]:
    return (round(float(point[0])), round(float(point[1])))


def _format_bytes(size: int) -> str:
    value = float(size)
    for suffix in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or suffix == "TB":
            return f"{value:.0f} {suffix}" if suffix == "B" else f"{value:.1f} {suffix}"
        value /= 1024.0
    return f"{value:.1f} TB"


def _roi_bounds(reference_roi: ReferenceRoi) -> tuple[Point2D, Point2D]:
    x0, y0, x1, y1 = reference_roi
    return (min(x0, x1), min(y0, y1)), (max(x0, x1), max(y0, y1))


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return (
        int(color[0:2], 16),
        int(color[2:4], 16),
        int(color[4:6], 16),
    )
