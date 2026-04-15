"""Dedicated output and review workspace window."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.project_panel import ProjectPanel
from ui.theme import BG_DARK, TEXT_BRIGHT, TEXT_DIM


def _as_int(value: object, default: int = 0) -> int:
    return value if isinstance(value, int) else default


class ReviewWorkspaceWindow(QMainWindow):
    """Output and QA workspace around preview and export settings."""

    preview_requested = Signal()
    export_requested = Signal()
    open_last_export_requested = Signal()
    open_rectify_requested = Signal()
    open_project_hub_requested = Signal()

    def __init__(self, *, project_panel: ProjectPanel) -> None:
        super().__init__()
        self.setWindowTitle("ImageRect — Ausgabe / Prüfung")
        self.resize(1320, 900)

        self.project_panel = project_panel
        self.close_guard: Callable[[QWidget], bool] | None = None
        self.project_label = QLabel("Kein Projekt geladen")
        self.summary_label = QLabel("Noch keine Exportdaten")
        self.last_export_label = QLabel("Letzter Export: keiner")
        self.preview_button = QPushButton("Vorschau öffnen")
        self.export_button = QPushButton("Exportieren")
        self.open_last_export_button = QPushButton("Ausgabeordner öffnen")
        self.back_to_2d_button = QPushButton("Zurück zu 2D")
        self.organizer_button = QPushButton("Projektsteuerung")

        self._build_ui()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not event.spontaneous():
            super().closeEvent(event)
            return
        if self.close_guard is not None and not self.close_guard(self):
            event.ignore()
            return
        super().closeEvent(event)

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        left_column = QWidget(self)
        left_layout = QVBoxLayout(left_column)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(14)

        summary_group = QGroupBox("Review / Ausgabe")
        summary_group.setStyleSheet(f"background: {BG_DARK};")
        summary_layout = QVBoxLayout(summary_group)
        summary_layout.setContentsMargins(16, 16, 16, 16)
        self.project_label.setStyleSheet(f"color: {TEXT_BRIGHT}; font-weight: 700;")
        self.summary_label.setStyleSheet(f"color: {TEXT_DIM};")
        self.summary_label.setWordWrap(True)
        self.last_export_label.setStyleSheet(f"color: {TEXT_DIM};")
        summary_layout.addWidget(self.project_label)
        summary_layout.addWidget(self.summary_label)
        summary_layout.addWidget(self.last_export_label)

        actions_group = QGroupBox("Aktionen")
        actions_group.setStyleSheet(f"background: {BG_DARK};")
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setContentsMargins(16, 16, 16, 16)
        actions_layout.setSpacing(10)
        for button in (
            self.preview_button,
            self.export_button,
            self.open_last_export_button,
            self.back_to_2d_button,
            self.organizer_button,
        ):
            actions_layout.addWidget(button)

        left_layout.addWidget(summary_group)
        left_layout.addWidget(actions_group)
        left_layout.addStretch(1)

        layout.addWidget(left_column, stretch=0)
        layout.addWidget(self.project_panel, stretch=1)

        self.preview_button.clicked.connect(self.preview_requested.emit)
        self.export_button.clicked.connect(self.export_requested.emit)
        self.open_last_export_button.clicked.connect(self.open_last_export_requested.emit)
        self.back_to_2d_button.clicked.connect(self.open_rectify_requested.emit)
        self.organizer_button.clicked.connect(self.open_project_hub_requested.emit)

    def update_summary(self, summary: dict[str, object]) -> None:
        name = str(summary.get("name", "Untitled"))
        reference_name = str(summary.get("reference_name", "keine"))
        image_count = _as_int(summary.get("image_count", 0))
        paired_points = _as_int(summary.get("paired_point_count", 0))
        export_ready = bool(summary.get("export_ready", False))
        last_export = str(summary.get("last_export_path", ""))

        self.project_label.setText(name)
        export_state = "exportbereit" if export_ready else "noch nicht exportbereit"
        self.summary_label.setText(
            f"{image_count} Bilder | Referenz: {reference_name} | "
            f"Punktpaare: {paired_points} | {export_state}"
        )
        self.last_export_label.setText(
            f"Letzter Export: {Path(last_export).name if last_export else 'keiner'}"
        )
        self.preview_button.setEnabled(export_ready)
        self.export_button.setEnabled(export_ready)
        self.open_last_export_button.setEnabled(bool(last_export))
