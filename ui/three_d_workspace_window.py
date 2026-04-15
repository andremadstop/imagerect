"""Dedicated 3D workspace window."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ui.reference3d_viewer import Reference3DViewer
from ui.theme import TEXT_BRIGHT, TEXT_DIM, icon_size


class ThreeDWorkspaceWindow(QMainWindow):
    """Standalone 3D module focused on plane preparation."""

    open_rectify_requested = Signal()
    open_project_hub_requested = Signal()

    def __init__(
        self,
        *,
        viewer: Reference3DViewer,
        load_reference_action: QAction,
        plane_from_points_action: QAction,
        plane_auto_action: QAction,
    ) -> None:
        super().__init__()
        self.setWindowTitle("ImageRect — 3D-Modul")
        self.resize(1280, 860)

        self.viewer = viewer
        self.load_reference_action = load_reference_action
        self.plane_from_points_action = plane_from_points_action
        self.plane_auto_action = plane_auto_action
        self.close_guard: Callable[[QWidget], bool] | None = None

        self.project_label = QLabel("Kein Projekt geladen")
        self.reference_label = QLabel("3D-Referenz: keine")
        self.plane_label = QLabel("Working Plane: nicht definiert")
        self.handoff_button = QPushButton("An 2D-Arbeitsplatz übergeben")
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
        toolbar = QToolBar("3D", self)
        toolbar.setMovable(False)
        toolbar.setIconSize(icon_size())
        toolbar.addAction(self.load_reference_action)
        toolbar.addAction(self.plane_from_points_action)
        toolbar.addAction(self.plane_auto_action)
        self.addToolBar(toolbar)

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        summary = QGroupBox("3D-Status")
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(16, 16, 16, 16)
        self.project_label.setStyleSheet(f"color: {TEXT_BRIGHT}; font-weight: 700;")
        self.reference_label.setStyleSheet(f"color: {TEXT_DIM};")
        self.plane_label.setStyleSheet(f"color: {TEXT_DIM};")
        summary_layout.addWidget(self.project_label)
        summary_layout.addWidget(self.reference_label)
        summary_layout.addWidget(self.plane_label)

        actions_row = QWidget(self)
        actions_layout = QHBoxLayout(actions_row)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.addWidget(self.handoff_button)
        actions_layout.addWidget(self.organizer_button)
        actions_layout.addStretch(1)

        layout.addWidget(summary)
        layout.addWidget(actions_row)
        layout.addWidget(self.viewer, stretch=1)

        self.handoff_button.clicked.connect(self.open_rectify_requested.emit)
        self.organizer_button.clicked.connect(self.open_project_hub_requested.emit)

    def update_summary(self, summary: dict[str, object]) -> None:
        self.project_label.setText(str(summary.get("name", "Untitled")))
        reference_name = str(summary.get("reference_name", "keine"))
        reference_type = str(summary.get("reference_type", "dxf")).upper()
        if reference_name == "keine":
            self.reference_label.setText("3D-Referenz: keine")
        else:
            self.reference_label.setText(f"3D-Referenz: {reference_name} ({reference_type})")
        self.plane_label.setText(
            "Working Plane: definiert"
            if bool(summary.get("has_working_plane", False))
            else "Working Plane: nicht definiert"
        )
        has_3d = reference_type in {"E57", "OBJ"}
        self.plane_from_points_action.setEnabled(has_3d)
        self.plane_auto_action.setEnabled(has_3d)
        self.handoff_button.setEnabled(has_3d)
