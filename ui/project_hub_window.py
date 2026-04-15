"""Project hub and organizer window."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ui.theme import BG_DARK, TEXT_BRIGHT, TEXT_DIM


def _as_int(value: object, default: int = 0) -> int:
    return value if isinstance(value, int) else default


class ProjectHubWindow(QMainWindow):
    """Top-level project organizer and workspace launcher."""

    new_2d_project_requested = Signal()
    new_3d_project_requested = Signal()
    open_project_requested = Signal()
    open_rectify_requested = Signal()
    open_three_d_requested = Signal()
    open_review_requested = Signal()
    recent_project_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ImageRect — Projektsteuerung")
        self.resize(980, 720)

        self.project_name_label = QLabel("Kein Projekt geladen")
        self.project_meta_label = QLabel("Noch kein aktives Projekt")
        self.reference_label = QLabel("Referenz: keine")
        self.export_label = QLabel("Letzter Export: keiner")
        self.images_list = QListWidget()
        self.recent_projects = QListWidget()
        self.close_guard: Callable[[QWidget], bool] | None = None

        self.new_2d_button = QPushButton("Neues 2D-Projekt")
        self.new_3d_button = QPushButton("Neues 3D-Projekt")
        self.open_project_button = QPushButton("Projekt öffnen")
        self.open_rectify_button = QPushButton("2D öffnen")
        self.open_three_d_button = QPushButton("3D öffnen")
        self.open_review_button = QPushButton("Ausgabe öffnen")

        self._build_ui()
        self._connect_signals()

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
        layout = QVBoxLayout(central)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        summary_group = QGroupBox("Projektstatus")
        summary_group.setStyleSheet(f"background: {BG_DARK};")
        summary_layout = QVBoxLayout(summary_group)
        summary_layout.setContentsMargins(16, 16, 16, 16)
        summary_layout.setSpacing(8)
        self.project_name_label.setStyleSheet(f"color: {TEXT_BRIGHT}; font-weight: 700;")
        self.project_meta_label.setStyleSheet(f"color: {TEXT_DIM};")
        self.reference_label.setStyleSheet(f"color: {TEXT_DIM};")
        self.export_label.setStyleSheet(f"color: {TEXT_DIM};")
        summary_layout.addWidget(self.project_name_label)
        summary_layout.addWidget(self.project_meta_label)
        summary_layout.addWidget(self.reference_label)
        summary_layout.addWidget(self.export_label)

        actions_group = QGroupBox("Arbeitsbereiche")
        actions_group.setStyleSheet(f"background: {BG_DARK};")
        actions_layout = QHBoxLayout(actions_group)
        actions_layout.setContentsMargins(16, 16, 16, 16)
        actions_layout.setSpacing(10)
        for button in (
            self.new_2d_button,
            self.new_3d_button,
            self.open_project_button,
            self.open_rectify_button,
            self.open_three_d_button,
            self.open_review_button,
        ):
            actions_layout.addWidget(button)

        lists_row = QWidget(self)
        lists_layout = QHBoxLayout(lists_row)
        lists_layout.setContentsMargins(0, 0, 0, 0)
        lists_layout.setSpacing(14)

        images_group = QGroupBox("Bilder im Projekt")
        images_group.setStyleSheet(f"background: {BG_DARK};")
        images_layout = QVBoxLayout(images_group)
        images_layout.setContentsMargins(12, 16, 12, 12)
        images_layout.addWidget(self.images_list)

        recent_group = QGroupBox("Zuletzt verwendet")
        recent_group.setStyleSheet(f"background: {BG_DARK};")
        recent_layout = QVBoxLayout(recent_group)
        recent_layout.setContentsMargins(12, 16, 12, 12)
        recent_layout.addWidget(self.recent_projects)

        lists_layout.addWidget(images_group, stretch=1)
        lists_layout.addWidget(recent_group, stretch=1)

        layout.addWidget(summary_group)
        layout.addWidget(actions_group)
        layout.addWidget(lists_row, stretch=1)

    def _connect_signals(self) -> None:
        self.new_2d_button.clicked.connect(self.new_2d_project_requested.emit)
        self.new_3d_button.clicked.connect(self.new_3d_project_requested.emit)
        self.open_project_button.clicked.connect(self.open_project_requested.emit)
        self.open_rectify_button.clicked.connect(self.open_rectify_requested.emit)
        self.open_three_d_button.clicked.connect(self.open_three_d_requested.emit)
        self.open_review_button.clicked.connect(self.open_review_requested.emit)
        self.recent_projects.itemActivated.connect(self._activate_recent_project)

    def update_summary(self, summary: dict[str, object]) -> None:
        name = str(summary.get("name", "Untitled"))
        image_count = _as_int(summary.get("image_count", 0))
        active_image = str(summary.get("active_image", "keines"))
        paired_points = _as_int(summary.get("paired_point_count", 0))
        dirty = bool(summary.get("dirty", False))
        reference_name = str(summary.get("reference_name", "keine"))
        reference_type = str(summary.get("reference_type", "dxf")).upper()
        last_export = str(summary.get("last_export_path", "")) or "keiner"

        self.project_name_label.setText(name)
        self.project_meta_label.setText(
            f"{image_count} Bilder | aktiv: {active_image} | Punktpaare: {paired_points} | "
            f"{'ungespeichert' if dirty else 'gespeichert'}"
        )
        if reference_name == "keine":
            self.reference_label.setText("Referenz: keine")
        else:
            self.reference_label.setText(f"Referenz: {reference_name} ({reference_type})")
        export_name = Path(last_export).name if last_export != "keiner" else last_export
        self.export_label.setText(f"Letzter Export: {export_name}")

        self.images_list.clear()
        for label in summary.get("images", []):
            self.images_list.addItem(QListWidgetItem(str(label)))

        self.open_rectify_button.setEnabled(True)
        self.open_three_d_button.setEnabled(True)
        self.open_review_button.setEnabled(True)

    def set_recent_projects(self, projects: Iterable[Path]) -> None:
        self.recent_projects.clear()
        for path in projects:
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(Qt.UserRole, str(path))
            self.recent_projects.addItem(item)

    def _activate_recent_project(self, item: QListWidgetItem) -> None:
        project_path = item.data(Qt.UserRole)
        if isinstance(project_path, str) and project_path:
            self.recent_project_requested.emit(project_path)
