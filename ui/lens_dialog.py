"""Lens correction dialog with preset selection and preview."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.image import image_to_rgb
from core.lens import (
    LensProfile,
    apply_lens_correction,
    exif_float,
    load_presets,
    match_preset,
    read_exif,
)
from ui.theme import ACCENT, BG_MID, BORDER, TEXT_BRIGHT, TEXT_DIM, WARNING


class LensDialog(QDialog):
    """Configure and preview image lens correction."""

    def __init__(
        self,
        image: np.ndarray,
        image_path: Path | None,
        current_profile: LensProfile | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Lens Correction")
        self.resize(1240, 760)

        self._image = image
        self._presets = load_presets()
        self._exif = read_exif(image_path) if image_path is not None and image_path.exists() else {}
        self._matched_preset = match_preset(self._exif, self._presets)

        self.info_label = QLabel(_build_exif_summary(self._exif, self._matched_preset))
        self.info_label.setStyleSheet(f"color: {TEXT_DIM};")
        self.info_label.setWordWrap(True)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Custom")
        for preset in self._presets:
            self.preset_combo.addItem(preset.name)

        self.focal_length = _build_spinbox(1.0, 1000.0, 3)
        self.sensor_width = _build_spinbox(1.0, 100.0, 3)
        self.k1 = _build_spinbox(-10.0, 10.0, 6)
        self.k2 = _build_spinbox(-10.0, 10.0, 6)
        self.p1 = _build_spinbox(-10.0, 10.0, 6)
        self.p2 = _build_spinbox(-10.0, 10.0, 6)
        self.k3 = _build_spinbox(-10.0, 10.0, 6)

        fields_box = QFrame()
        fields_box.setStyleSheet(
            f"QFrame {{ background: {BG_MID}; border: 1px solid {BORDER}; border-radius: 8px; }}"
        )
        fields_form = QFormLayout(fields_box)
        fields_form.setContentsMargins(16, 16, 16, 16)
        fields_form.setSpacing(12)
        fields_form.addRow("Preset", self.preset_combo)
        fields_form.addRow("Focal length (mm)", self.focal_length)
        fields_form.addRow("Sensor width (mm)", self.sensor_width)
        fields_form.addRow("k1", self.k1)
        fields_form.addRow("k2", self.k2)
        fields_form.addRow("p1", self.p1)
        fields_form.addRow("p2", self.p2)
        fields_form.addRow("k3", self.k3)

        self.grid_overlay = QCheckBox("Grid overlay")
        self.grid_overlay.setChecked(True)

        self.apply_button = QPushButton("Apply")
        self.apply_button.setProperty("primary", True)

        controls_row = QWidget()
        controls_layout = QHBoxLayout(controls_row)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.addWidget(self.grid_overlay)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.apply_button)

        self.original_preview = _build_preview_label()
        self.corrected_preview = _build_preview_label()

        preview_row = QWidget()
        preview_layout = QHBoxLayout(preview_row)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(12)
        preview_layout.addWidget(_wrap_preview("Original", self.original_preview))
        preview_layout.addWidget(_wrap_preview("Corrected", self.corrected_preview))

        footer = QLabel("Preset values are approximations. Fine-tune manually for precision work.")
        footer.setStyleSheet(f"color: {WARNING};")
        footer.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        if ok_button is not None:
            ok_button.setText("OK")
            ok_button.setProperty("primary", True)
        if cancel_button is not None:
            cancel_button.setText("Cancel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(self.info_label)
        layout.addWidget(fields_box)
        layout.addWidget(controls_row)
        layout.addWidget(preview_row, stretch=1)
        layout.addWidget(footer)
        layout.addWidget(buttons)

        self.preset_combo.currentIndexChanged.connect(self._handle_preset_changed)
        self.grid_overlay.toggled.connect(self._update_preview)
        self.apply_button.clicked.connect(self._update_preview)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        initial_profile = current_profile or self._matched_preset or _fallback_profile()
        self._apply_profile_to_widgets(initial_profile)
        self._select_preset(initial_profile.name)
        self._update_preview()

    def accept(self) -> None:
        self._update_preview()
        super().accept()

    def selected_profile(self) -> LensProfile:
        name = self.preset_combo.currentText()
        if name == "Custom":
            name = "Custom"
        return LensProfile(
            name=name,
            focal_length_mm=float(self.focal_length.value()),
            sensor_width_mm=float(self.sensor_width.value()),
            k1=float(self.k1.value()),
            k2=float(self.k2.value()),
            p1=float(self.p1.value()),
            p2=float(self.p2.value()),
            k3=float(self.k3.value()),
        )

    def lens_correction_payload(self) -> dict[str, object]:
        return {"profile": self.selected_profile().to_dict(), "applied": True}

    def _handle_preset_changed(self, index: int) -> None:
        if index <= 0:
            return
        preset = self._presets[index - 1]
        self._apply_profile_to_widgets(preset)
        self._update_preview()

    def _apply_profile_to_widgets(self, profile: LensProfile) -> None:
        self.focal_length.setValue(profile.focal_length_mm)
        self.sensor_width.setValue(profile.sensor_width_mm)
        self.k1.setValue(profile.k1)
        self.k2.setValue(profile.k2)
        self.p1.setValue(profile.p1)
        self.p2.setValue(profile.p2)
        self.k3.setValue(profile.k3)

    def _select_preset(self, profile_name: str) -> None:
        combo_index = self.preset_combo.findText(profile_name)
        self.preset_combo.setCurrentIndex(max(combo_index, 0))

    def _update_preview(self) -> None:
        corrected = apply_lens_correction(self._image, self.selected_profile())
        self.original_preview.setPixmap(_preview_pixmap(self._image, self.grid_overlay.isChecked()))
        self.corrected_preview.setPixmap(_preview_pixmap(corrected, self.grid_overlay.isChecked()))


def _build_spinbox(minimum: float, maximum: float, decimals: int) -> QDoubleSpinBox:
    spinbox = QDoubleSpinBox()
    spinbox.setMinimum(minimum)
    spinbox.setMaximum(maximum)
    spinbox.setDecimals(decimals)
    spinbox.setSingleStep(0.001 if decimals >= 3 else 0.1)
    return spinbox


def _build_preview_label() -> QLabel:
    label = QLabel()
    label.setAlignment(Qt.AlignCenter)
    label.setMinimumSize(320, 320)
    label.setStyleSheet(
        f"""
        QLabel {{
            background: {BG_MID};
            border: 1px solid {BORDER};
            border-radius: 8px;
            color: {TEXT_DIM};
        }}
        """
    )
    return label


def _wrap_preview(title: str, label: QLabel) -> QWidget:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    heading = QLabel(title)
    heading.setStyleSheet(f"color: {TEXT_BRIGHT}; font-weight: 600;")
    layout.addWidget(heading)
    layout.addWidget(label, stretch=1)
    return widget


def _preview_pixmap(image: np.ndarray, show_grid: bool) -> QPixmap:
    preview = np.ascontiguousarray(image_to_rgb(image))
    longest_side = max(preview.shape[0], preview.shape[1])
    if longest_side > 600:
        scale = 600.0 / float(longest_side)
        target_width = max(1, round(preview.shape[1] * scale))
        target_height = max(1, round(preview.shape[0] * scale))
        preview = cv2.resize(
            preview,
            (target_width, target_height),
            interpolation=cv2.INTER_AREA,
        )

    if show_grid:
        _draw_grid(preview)

    qimage = QImage(
        preview.data,
        preview.shape[1],
        preview.shape[0],
        preview.strides[0],
        QImage.Format_RGB888,
    )
    return QPixmap.fromImage(qimage.copy())


def _draw_grid(image: np.ndarray) -> None:
    spacing = max(28, min(image.shape[0], image.shape[1]) // 10)
    grid_color = tuple(int(channel) for channel in _hex_to_rgb(ACCENT))
    for x in range(spacing, image.shape[1], spacing):
        cv2.line(image, (x, 0), (x, image.shape[0] - 1), grid_color, 1, cv2.LINE_AA)
    for y in range(spacing, image.shape[0], spacing):
        cv2.line(image, (0, y), (image.shape[1] - 1, y), grid_color, 1, cv2.LINE_AA)


def _build_exif_summary(exif: dict[str, object], matched_preset: LensProfile | None) -> str:
    if not exif:
        return "No EXIF data found"

    make = str(exif.get("Make", "")).strip()
    model = str(exif.get("Model", "")).strip()
    camera = " ".join(part for part in (make, model) if part).strip() or "Unknown camera"
    focal = exif_float(exif, "FocalLength")
    focal_text = f"{focal:.2f}mm" if focal is not None else "n/a"
    if matched_preset is not None:
        return f"Detected: {camera} | Focal: {focal_text} | Preset: {matched_preset.name}"
    return f"Detected: {camera} | Focal: {focal_text}"


def _fallback_profile() -> LensProfile:
    return LensProfile(name="Custom", focal_length_mm=24.0, sensor_width_mm=13.2)


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return (
        int(color[0:2], 16),
        int(color[2:4], 16),
        int(color[4:6], 16),
    )
