"""Window/workspace coordination for the ImageRect desktop UI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QWidget

from ui.main_window import MainWindow
from ui.project_hub_window import ProjectHubWindow
from ui.review_workspace_window import ReviewWorkspaceWindow
from ui.three_d_workspace_window import ThreeDWorkspaceWindow


class WorkspaceController(QObject):
    """Keep the project hub and specialized workspaces in sync."""

    def __init__(self) -> None:
        super().__init__()
        self.settings = QSettings("ImageRect", "ImageRect")
        self.rectify_window = MainWindow()
        self.project_hub = ProjectHubWindow()
        self.three_d_window = ThreeDWorkspaceWindow(
            viewer=self.rectify_window.reference3d_viewer,
            load_reference_action=self.rectify_window.action_load_reference3d,
            plane_from_points_action=self.rectify_window.action_define_plane_from_points,
            plane_auto_action=self.rectify_window.action_define_plane_auto,
        )
        self.review_window = ReviewWorkspaceWindow(project_panel=self.rectify_window.project_panel)
        self.rectify_window.close_guard = self._handle_window_close
        self.project_hub.close_guard = self._handle_window_close
        self.three_d_window.close_guard = self._handle_window_close
        self.review_window.close_guard = self._handle_window_close

        self._connect_signals()
        self._sync_windows()

    def _connect_signals(self) -> None:
        self.project_hub.new_2d_project_requested.connect(self.new_2d_project)
        self.project_hub.new_3d_project_requested.connect(self.new_3d_project)
        self.project_hub.open_project_requested.connect(self.open_project_dialog)
        self.project_hub.open_rectify_requested.connect(self.show_rectify_workspace)
        self.project_hub.open_three_d_requested.connect(self.show_three_d_workspace)
        self.project_hub.open_review_requested.connect(self.show_review_workspace)
        self.project_hub.recent_project_requested.connect(self._open_recent_project)

        self.three_d_window.open_rectify_requested.connect(self.show_rectify_workspace)
        self.three_d_window.open_project_hub_requested.connect(self.show_project_hub)

        self.review_window.preview_requested.connect(self.rectify_window.show_export_preview)
        self.review_window.export_requested.connect(self.rectify_window.run_export)
        self.review_window.open_last_export_requested.connect(self.open_last_export_folder)
        self.review_window.open_rectify_requested.connect(self.show_rectify_workspace)
        self.review_window.open_project_hub_requested.connect(self.show_project_hub)

        self.rectify_window.request_project_hub.connect(self.show_project_hub)
        self.rectify_window.request_three_d_workspace.connect(self.show_three_d_workspace)
        self.rectify_window.request_review_workspace.connect(self.show_review_workspace)
        self.rectify_window.project_state_changed.connect(self._sync_windows)
        self.rectify_window.project_path_changed.connect(self._record_recent_project)

    def show_initial_ui(self) -> None:
        self.project_hub.show()
        self.project_hub.raise_()
        self.project_hub.activateWindow()

    def show_project_hub(self) -> None:
        self.project_hub.show()
        self.project_hub.raise_()
        self.project_hub.activateWindow()

    def show_rectify_workspace(self) -> None:
        self.rectify_window.show()
        self.rectify_window.raise_()
        self.rectify_window.activateWindow()

    def show_three_d_workspace(self) -> None:
        self.three_d_window.show()
        self.three_d_window.raise_()
        self.three_d_window.activateWindow()

    def show_review_workspace(self) -> None:
        self.review_window.show()
        self.review_window.raise_()
        self.review_window.activateWindow()

    def new_2d_project(self) -> None:
        if not self.rectify_window.confirm_close_with_unsaved_changes():
            return
        self.rectify_window._new_project()
        self.show_rectify_workspace()

    def new_3d_project(self) -> None:
        if not self.rectify_window.confirm_close_with_unsaved_changes():
            return
        self.rectify_window._new_project()
        self.show_three_d_workspace()

    def open_project_dialog(self) -> None:
        if not self.rectify_window.confirm_close_with_unsaved_changes():
            return
        file_name, _ = QFileDialog.getOpenFileName(
            self.project_hub,
            "Open Project",
            str(Path.cwd()),
            "ImageRect Project (*.imagerect.json)",
        )
        if file_name:
            self.load_project_file(file_name)

    def load_project_file(self, path: str | Path) -> None:
        self.rectify_window.load_project_file(path)
        self.show_rectify_workspace()
        if self.rectify_window.project.reference_type in {"e57", "obj"}:
            self.show_three_d_workspace()

    def _open_recent_project(self, path: str) -> None:
        if not self.rectify_window.confirm_close_with_unsaved_changes():
            return
        self.load_project_file(path)

    def open_last_export_folder(self) -> None:
        summary = self.rectify_window.project_summary()
        export_path = str(summary.get("last_export_path", ""))
        if not export_path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(export_path).resolve().parent)))

    def _record_recent_project(self, raw_path: object) -> None:
        if not isinstance(raw_path, Path):
            return
        recent = [str(path) for path in self.recent_projects()]
        normalized = str(raw_path.resolve())
        recent = [normalized, *[path for path in recent if path != normalized]]
        self.settings.setValue("recent_projects", recent[:8])
        self._sync_windows()

    def recent_projects(self) -> list[Path]:
        raw_projects = self.settings.value("recent_projects", [], list)
        recent_paths: list[Path] = []
        for raw_path in raw_projects:
            path = Path(str(raw_path))
            if path.exists():
                recent_paths.append(path)
        return recent_paths

    def _sync_windows(self) -> None:
        summary = self.rectify_window.project_summary()
        self.project_hub.update_summary(summary)
        self.project_hub.set_recent_projects(self.recent_projects())
        self.three_d_window.update_summary(summary)
        self.review_window.update_summary(summary)

    def _all_windows(self) -> tuple[QWidget, ...]:
        return (
            self.project_hub,
            self.rectify_window,
            self.three_d_window,
            self.review_window,
        )

    def _handle_window_close(self, closing_window: QWidget) -> bool:
        remaining_visible = [
            window
            for window in self._all_windows()
            if window is not closing_window and window.isVisible()
        ]
        if remaining_visible:
            return True
        return self.rectify_window.confirm_close_with_unsaved_changes()
