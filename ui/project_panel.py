"""Persistent project settings panel with live export estimates."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.export import build_canvas, estimate_output_size_bytes
from core.project import ExportSettings, Point2D, ProjectData, unit_to_mm
from ui.theme import ERROR, TEXT_BRIGHT, TEXT_DIM, WARNING

SCALE_PRESETS = [50.0, 100.0, 200.0, 500.0, 1000.0]
FORMAT_OPTIONS = [
    ("TIFF", "tiff"),
    ("BigTIFF", "bigtiff"),
    ("PNG", "png"),
    ("JPEG", "jpeg"),
]


class ProjectPanel(QWidget):
    """Persistent project/output settings editor."""

    project_name_changed = Signal(str)
    units_changed = Signal(str)
    export_settings_changed = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._updating = False
        self._reference_bounds: tuple[Point2D, Point2D] | None = None
        self._has_clip_polygon = False
        self._has_reference_roi = False

        self.project_name = QLineEdit()
        self.units = QComboBox()
        self.units.addItems(["mm", "cm", "m", "in", "ft"])

        self.scale = QComboBox()
        for value in SCALE_PRESETS:
            self.scale.addItem(f"1:{int(value)}", value)
        self.scale.addItem("Custom", None)
        self.scale_custom = _build_spinbox(1.0, 1000000.0, 3)

        self.pixel_size = _build_spinbox(0.0001, 1000000.0, 4)
        self.dpi = _build_spinbox(1.0, 2400.0, 2)

        self.output_format = QComboBox()
        for label, format_value in FORMAT_OPTIONS:
            self.output_format.addItem(label, format_value)
        self.bit_depth = QComboBox()
        self.compression = QComboBox()
        self.resampling = QComboBox()
        self.resampling.addItems(["nearest", "bilinear", "bicubic", "lanczos"])
        self.multi_layer = QCheckBox("Write helper overlay layers")

        self.use_clip_polygon = QCheckBox("Use clip polygon")
        self.use_reference_roi = QCheckBox("Use DXF ROI")
        self.clip_to_hull = QCheckBox("Use control-point convex hull")

        self.include_json_sidecar = QCheckBox("Include JSON sidecar")
        self.embed_in_tiff = QCheckBox("Embed in TIFF")

        self.canvas_label = QLabel("Canvas: n/a")
        self.file_size_label = QLabel("File size: n/a")
        self.canvas_label.setStyleSheet(f"color: {TEXT_BRIGHT}; font-weight: 600;")
        self.file_size_label.setStyleSheet(f"color: {TEXT_DIM};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(self._build_project_group())
        layout.addWidget(self._build_scale_group())
        layout.addWidget(self._build_output_group())
        layout.addWidget(self._build_region_group())
        layout.addWidget(self._build_metadata_group())
        layout.addStretch(1)

        self._connect_signals()
        self._apply_format_constraints()
        self._update_canvas_estimate()

    def set_project(self, project: ProjectData) -> None:
        self._updating = True
        try:
            self.project_name.setText(project.name)
            self.units.setCurrentText(project.units)

            settings = project.export_settings
            self.pixel_size.setValue(settings.pixel_size)
            self.dpi.setValue(settings.dpi)
            self._set_scale_value(settings.scale_denominator)

            self.output_format.setCurrentIndex(
                max(self.output_format.findData(settings.output_format), 0)
            )
            self._set_bit_depth(settings.bit_depth)
            self._set_compression(settings.compression)
            self.resampling.setCurrentText(settings.resampling)
            self.multi_layer.setChecked(settings.multi_layer)
            self.use_clip_polygon.setChecked(settings.use_clip_polygon)
            self.use_reference_roi.setChecked(settings.use_reference_roi)
            self.clip_to_hull.setChecked(settings.clip_to_hull)
            self.include_json_sidecar.setChecked(settings.include_json_sidecar)
            self.embed_in_tiff.setChecked(settings.embed_in_tiff)
        finally:
            self._updating = False

        self._apply_format_constraints()
        self._update_region_controls()
        self._update_canvas_estimate()

    def set_context(
        self,
        reference_bounds: tuple[Point2D, Point2D] | None,
        has_clip_polygon: bool,
        has_reference_roi: bool,
    ) -> None:
        self._reference_bounds = reference_bounds
        self._has_clip_polygon = has_clip_polygon
        self._has_reference_roi = has_reference_roi
        self._update_region_controls()
        self._update_canvas_estimate()

    def current_export_settings(self) -> ExportSettings:
        return ExportSettings(
            pixel_size=float(self.pixel_size.value()),
            scale_denominator=self._scale_value(),
            dpi=float(self.dpi.value()),
            resampling=self.resampling.currentText(),
            output_format=str(self.output_format.currentData()),
            bit_depth=int(self.bit_depth.currentText()),
            compression=self.compression.currentText().lower(),
            multi_layer=self.multi_layer.isChecked(),
            use_clip_polygon=self.use_clip_polygon.isChecked(),
            use_reference_roi=self.use_reference_roi.isChecked(),
            clip_to_hull=self.clip_to_hull.isChecked(),
            include_json_sidecar=self.include_json_sidecar.isChecked(),
            embed_in_tiff=self.embed_in_tiff.isChecked(),
        )

    def _build_project_group(self) -> QGroupBox:
        group = QGroupBox("Project")
        form = QFormLayout(group)
        form.setContentsMargins(12, 16, 12, 12)
        form.setSpacing(10)
        form.addRow("Project name", self.project_name)
        form.addRow("Units", self.units)
        return group

    def _build_scale_group(self) -> QGroupBox:
        group = QGroupBox("Scale")
        form = QFormLayout(group)
        form.setContentsMargins(12, 16, 12, 12)
        form.setSpacing(10)

        scale_row = QWidget()
        scale_layout = QHBoxLayout(scale_row)
        scale_layout.setContentsMargins(0, 0, 0, 0)
        scale_layout.setSpacing(8)
        scale_layout.addWidget(self.scale, stretch=1)
        scale_layout.addWidget(self.scale_custom)

        form.addRow("Scale", scale_row)
        form.addRow("Pixel size (mm/px)", self.pixel_size)
        form.addRow("DPI", self.dpi)
        form.addRow("", self.canvas_label)
        form.addRow("", self.file_size_label)
        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("Output")
        form = QFormLayout(group)
        form.setContentsMargins(12, 16, 12, 12)
        form.setSpacing(10)
        form.addRow("Format", self.output_format)
        form.addRow("Bit depth", self.bit_depth)
        form.addRow("Resampling", self.resampling)
        form.addRow("Compression", self.compression)
        form.addRow("", self.multi_layer)
        return group

    def _build_region_group(self) -> QGroupBox:
        group = QGroupBox("Region")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self.use_clip_polygon)
        layout.addWidget(self.use_reference_roi)
        layout.addWidget(self.clip_to_hull)
        return group

    def _build_metadata_group(self) -> QGroupBox:
        group = QGroupBox("Metadata")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self.include_json_sidecar)
        layout.addWidget(self.embed_in_tiff)
        return group

    def _connect_signals(self) -> None:
        self.project_name.editingFinished.connect(self._emit_project_name)
        self.units.currentTextChanged.connect(self._handle_units_changed)

        self.scale.currentIndexChanged.connect(self._handle_scale_selector_changed)
        self.scale_custom.valueChanged.connect(self._sync_from_scale)
        self.dpi.valueChanged.connect(self._sync_from_scale)
        self.pixel_size.valueChanged.connect(self._sync_from_pixel_size)
        self.scale_custom.editingFinished.connect(self._emit_export_settings)
        self.dpi.editingFinished.connect(self._emit_export_settings)
        self.pixel_size.editingFinished.connect(self._emit_export_settings)

        self.output_format.currentIndexChanged.connect(self._handle_output_format_changed)
        self.bit_depth.currentIndexChanged.connect(self._emit_export_settings)
        self.compression.currentIndexChanged.connect(self._emit_export_settings)
        self.resampling.currentIndexChanged.connect(self._emit_export_settings)
        self.multi_layer.toggled.connect(self._emit_export_settings)
        self.use_clip_polygon.toggled.connect(self._emit_export_settings)
        self.use_reference_roi.toggled.connect(self._emit_export_settings)
        self.clip_to_hull.toggled.connect(self._emit_export_settings)
        self.include_json_sidecar.toggled.connect(self._emit_export_settings)
        self.embed_in_tiff.toggled.connect(self._emit_export_settings)

    def _emit_project_name(self) -> None:
        if not self._updating:
            self.project_name_changed.emit(self.project_name.text().strip() or "Untitled")

    def _handle_units_changed(self, units: str) -> None:
        self._update_canvas_estimate()
        if not self._updating:
            self.units_changed.emit(units)
            self._emit_export_settings()

    def _handle_scale_selector_changed(self) -> None:
        is_custom = self.scale.currentData() is None
        self.scale_custom.setEnabled(is_custom)
        if not is_custom:
            data = self.scale.currentData()
            if isinstance(data, int | float):
                self._updating = True
                try:
                    self.scale_custom.setValue(float(data))
                finally:
                    self._updating = False
        self._sync_from_scale()

    def _sync_from_scale(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            pixel_size_mm = (self._scale_value() * 25.4) / max(float(self.dpi.value()), 1e-6)
            self.pixel_size.setValue(pixel_size_mm)
        finally:
            self._updating = False
        self._update_canvas_estimate()

    def _sync_from_pixel_size(self) -> None:
        if self._updating:
            return
        self._updating = True
        try:
            scale_denominator = (float(self.pixel_size.value()) * float(self.dpi.value())) / 25.4
            self._set_scale_value(scale_denominator)
        finally:
            self._updating = False
        self._update_canvas_estimate()

    def _handle_output_format_changed(self) -> None:
        self._apply_format_constraints()
        self._update_canvas_estimate()
        self._emit_export_settings()

    def _apply_format_constraints(self) -> None:
        output_format = str(self.output_format.currentData())
        if output_format in {"tiff", "bigtiff"}:
            self._set_combo_values(
                self.bit_depth,
                ["8", "16", "32"],
                self.bit_depth.currentText(),
            )
            self._set_combo_values(
                self.compression,
                ["none", "lzw", "deflate", "jpeg"],
                self.compression.currentText().lower() or "none",
            )
            self.compression.setEnabled(True)
            self.multi_layer.setEnabled(True)
            self.embed_in_tiff.setEnabled(True)
        elif output_format == "png":
            self._set_combo_values(
                self.bit_depth,
                ["8", "16"],
                self.bit_depth.currentText(),
            )
            self._set_combo_values(self.compression, ["none"], "none")
            self.compression.setEnabled(False)
            self.multi_layer.setChecked(False)
            self.multi_layer.setEnabled(False)
            self.embed_in_tiff.setChecked(False)
            self.embed_in_tiff.setEnabled(False)
        else:
            self._set_combo_values(self.bit_depth, ["8"], "8")
            self._set_combo_values(self.compression, ["none"], "none")
            self.compression.setEnabled(False)
            self.multi_layer.setChecked(False)
            self.multi_layer.setEnabled(False)
            self.embed_in_tiff.setChecked(False)
            self.embed_in_tiff.setEnabled(False)

    def _update_region_controls(self) -> None:
        self.use_clip_polygon.setEnabled(self._has_clip_polygon)
        if not self._has_clip_polygon:
            self.use_clip_polygon.setChecked(False)

        self.use_reference_roi.setEnabled(self._has_reference_roi)
        if not self._has_reference_roi:
            self.use_reference_roi.setChecked(False)

    def _update_canvas_estimate(self) -> None:
        if self._reference_bounds is None:
            self.canvas_label.setText("Canvas: n/a")
            self.file_size_label.setText("File size: n/a")
            self.canvas_label.setStyleSheet(f"color: {TEXT_BRIGHT}; font-weight: 600;")
            self.file_size_label.setStyleSheet(f"color: {TEXT_DIM};")
            return

        pixel_size_units = float(self.pixel_size.value()) / unit_to_mm(self.units.currentText())
        if pixel_size_units <= 0.0:
            self.canvas_label.setText("Canvas: invalid pixel size")
            return

        width, height, _matrix = build_canvas(
            self._reference_bounds[0],
            self._reference_bounds[1],
            pixel_size_units,
        )
        layer_count = (
            3
            if self.multi_layer.isChecked()
            and str(self.output_format.currentData()) in {"tiff", "bigtiff"}
            else 1
        )
        estimated_size = estimate_output_size_bytes(
            width,
            height,
            int(self.bit_depth.currentText()),
            layer_count=layer_count,
        )
        self.canvas_label.setText(f"Canvas: {width:,} x {height:,} px")
        self.file_size_label.setText(f"File size: ~{_format_bytes(estimated_size)}")

        if width > 100_000 or height > 100_000:
            color = ERROR
        elif width > 50_000 or height > 50_000:
            color = WARNING
        else:
            color = TEXT_BRIGHT
        self.canvas_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        file_color = color if color != TEXT_BRIGHT else TEXT_DIM
        self.file_size_label.setStyleSheet(f"color: {file_color};")

    def _emit_export_settings(self) -> None:
        if not self._updating:
            self.export_settings_changed.emit(self.current_export_settings())

    def _scale_value(self) -> float:
        return float(self.scale_custom.value())

    def _set_scale_value(self, scale_denominator: float) -> None:
        self.scale_custom.setValue(scale_denominator)
        matched_index = next(
            (
                index
                for index, preset in enumerate(SCALE_PRESETS)
                if abs(scale_denominator - preset) < 1e-6
            ),
            len(SCALE_PRESETS),
        )
        self.scale.setCurrentIndex(matched_index)
        self.scale_custom.setEnabled(matched_index == len(SCALE_PRESETS))

    def _set_bit_depth(self, bit_depth: int) -> None:
        current_values = [
            self.bit_depth.itemText(index) for index in range(self.bit_depth.count())
        ] or ["8", "16", "32"]
        self._set_combo_values(self.bit_depth, current_values, str(bit_depth))

    def _set_compression(self, compression: str) -> None:
        current_values = [
            self.compression.itemText(index) for index in range(self.compression.count())
        ] or ["none", "lzw", "deflate", "jpeg"]
        self._set_combo_values(self.compression, current_values, compression)

    @staticmethod
    def _set_combo_values(combo: QComboBox, values: list[str], selected: str) -> None:
        combo.blockSignals(True)
        try:
            current = selected if selected in values else values[0]
            combo.clear()
            combo.addItems(values)
            combo.setCurrentText(current)
        finally:
            combo.blockSignals(False)


def _build_spinbox(minimum: float, maximum: float, decimals: int) -> QDoubleSpinBox:
    spinbox = QDoubleSpinBox()
    spinbox.setRange(minimum, maximum)
    spinbox.setDecimals(decimals)
    spinbox.setSingleStep(0.1 if decimals <= 2 else 0.01)
    spinbox.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return spinbox


def _format_bytes(size: int) -> str:
    value = float(size)
    for suffix in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024.0 or suffix == "TB":
            return f"{value:.0f} {suffix}" if suffix == "B" else f"{value:.1f} {suffix}"
        value /= 1024.0
    return f"{value:.1f} TB"
