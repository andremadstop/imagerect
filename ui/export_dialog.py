"""Simple export settings dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QVBoxLayout,
    QWidget,
)

from core.project import ExportSettings


class ExportDialog(QDialog):
    """Configure pixel size, format, and interpolation for export."""

    def __init__(self, settings: ExportSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Rectified Image")

        self.pixel_size = QDoubleSpinBox()
        self.pixel_size.setDecimals(4)
        self.pixel_size.setMinimum(0.0001)
        self.pixel_size.setMaximum(1000000.0)
        self.pixel_size.setValue(settings.pixel_size)

        self.output_format = QComboBox()
        self.output_format.addItems(["tiff", "png"])
        self.output_format.setCurrentText(settings.output_format)

        self.resampling = QComboBox()
        self.resampling.addItems(["nearest", "bilinear", "bicubic"])
        self.resampling.setCurrentText(settings.resampling)

        self.clip_to_hull = QCheckBox("Clip to control-point hull")
        self.clip_to_hull.setChecked(settings.clip_to_hull)

        output_group = QGroupBox("Output")
        output_form = QFormLayout(output_group)
        output_form.setContentsMargins(12, 16, 12, 12)
        output_form.setSpacing(12)
        output_form.addRow("Pixel size", self.pixel_size)
        output_form.addRow("Format", self.output_format)

        sampling_group = QGroupBox("Sampling")
        sampling_form = QFormLayout(sampling_group)
        sampling_form.setContentsMargins(12, 16, 12, 12)
        sampling_form.setSpacing(12)
        sampling_form.addRow("Resampling", self.resampling)
        sampling_form.addRow("", self.clip_to_hull)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_button = buttons.button(QDialogButtonBox.Ok)
        cancel_button = buttons.button(QDialogButtonBox.Cancel)
        if ok_button is not None:
            ok_button.setText("Export")
            ok_button.setProperty("primary", True)
        if cancel_button is not None:
            cancel_button.setText("Cancel")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        layout.addWidget(output_group)
        layout.addWidget(sampling_group)
        layout.addWidget(buttons)

    def get_settings(self) -> ExportSettings:
        return ExportSettings(
            pixel_size=float(self.pixel_size.value()),
            resampling=self.resampling.currentText(),
            output_format=self.output_format.currentText(),
            clip_to_hull=self.clip_to_hull.isChecked(),
        )
