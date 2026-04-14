"""Main window for the ImageRect desktop application."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QFont, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.diagnose import build_diagnose_package
from core.export import (
    ExportCancelledError,
    MosaicSource,
    RectificationExportResult,
    export_mosaic_image,
    export_rectified_image,
)
from core.image import load_image
from core.lens import (
    LensProfile,
    apply_lens_correction,
    lens_profile_from_dict,
    remap_points_between_profiles,
)
from core.logging_setup import log_directory
from core.pose import build_camera_pose, extract_gps_pose, gps_offset_meters, gps_to_reference_xy
from core.project import (
    ControlPoint,
    ExportSettings,
    ImageEntry,
    Point2D,
    ProjectData,
    ReferenceRoi,
    unit_to_mm,
)
from core.reference2d import Reference2D, load_dxf
from core.reference3d import (
    Reference3D,
    WorkingPlane,
    define_plane_from_3_points,
    define_plane_ransac,
    load_e57,
    load_obj,
    pick_nearest_point,
    project_3d_to_plane,
    reference_plane_extents,
    reference_source_points,
    working_plane_from_dict,
    working_plane_to_dict,
)
from core.transform import HomographyResult, solve_planar_homography
from ui.image_viewer import ImageViewer
from ui.lens_dialog import LensDialog
from ui.point_table import PointTable
from ui.preview_dialog import PreviewDialog
from ui.project_panel import ProjectPanel
from ui.reference2d_viewer import Reference2DViewer
from ui.reference3d_viewer import Reference3DViewer
from ui.theme import (
    BG_DARK,
    TEXT_BRIGHT,
    TEXT_DIM,
    WARNING,
    color_for_rms,
    icon_size,
    make_symbol_icon,
)

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window with 2D and 3D reference workflows."""

    def __init__(self) -> None:
        super().__init__()
        self.project = ProjectData()
        self.project_path: Path | None = None
        self.reference_2d: Reference2D | None = None
        self.reference_3d: Reference3D | None = None
        self.source_image_original: np.ndarray | None = None
        self.source_image: np.ndarray | None = None
        self.transform_result: HomographyResult | None = None
        self.selected_point_id: int | None = None
        self.pending_plane_points: list[np.ndarray] = []
        self.plane_pick_mode = False
        self._current_mode = "view"
        self._history: list[ProjectData] = [self.project.clone()]
        self._history_index = 0
        self._restoring_history = False
        self._saved_project_state = self._project_state_snapshot()

        self._build_ui()
        self._create_actions()
        self._connect_signals()
        self._refresh_ui()

    def load_image_file(self, path: str | Path) -> None:
        image_path = Path(path).resolve()
        logger.info("Loading image | path=%s", image_path)
        self.project.sync_to_active_image()
        self._activate_or_create_image(image_path)
        self.source_image_original = load_image(image_path)
        if self.project.images:
            self.project.images[self.project.active_image_index].gps_pose = extract_gps_pose(
                image_path
            )
        self._refresh_source_image()
        if self.project.name == "Untitled":
            self.project.name = image_path.stem
        self._record_history()
        logger.info(
            "Loaded image | path=%s | active_index=%d", image_path, self.project.active_image_index
        )
        self._refresh_ui(status=f"Loaded image {image_path.name}")

    def load_reference_file(self, path: str | Path) -> None:
        reference_path = Path(path).resolve()
        if reference_path.suffix.lower() == ".dwg":
            self._show_dwg_help_dialog()
            return
        logger.info("Loading 2D reference from UI | path=%s", reference_path)
        self.reference_2d = load_dxf(reference_path)
        self.reference_3d = None
        self.project.clear_reference_alignment()
        self.transform_result = None
        self.project.reference_path = str(reference_path)
        self.project.reference_type = "dxf"
        self.project.reference_crs_epsg = self.reference_2d.crs_epsg
        if self.reference_2d.units != "unitless":
            self.project.units = self.reference_2d.units
        self.project.working_plane = None
        self.project.reference_roi = None
        self.selected_point_id = None
        self.pending_plane_points = []
        self.plane_pick_mode = False
        self._current_mode = "view"
        self._record_history()
        logger.info("Loaded 2D reference from UI | path=%s", reference_path)
        self._refresh_ui(status=f"Loaded reference {reference_path.name}")

    def load_3d_reference_file(self, path: str | Path) -> None:
        reference_path = Path(path).resolve()
        suffix = reference_path.suffix.lower()
        if suffix == ".e57":
            reference = load_e57(reference_path)
        elif suffix == ".obj":
            reference = load_obj(reference_path)
        else:
            raise ValueError("3D reference must be .e57 or .obj")

        self.reference_3d = reference
        self.reference_2d = None
        self.project.clear_reference_alignment()
        self.transform_result = None
        self.pending_plane_points = []
        self.plane_pick_mode = False
        self.project.reference_path = str(reference_path)
        self.project.reference_type = reference.source_type
        self.project.reference_crs_epsg = None
        if reference.units != "unitless":
            self.project.units = reference.units
        self.project.working_plane = None
        self.project.reference_roi = None
        self.selected_point_id = None
        self._record_history()
        logger.info("Loaded 3D reference from UI | path=%s | type=%s", reference_path, suffix)
        self._refresh_ui(status=f"Loaded 3D reference {reference_path.name}")

    def load_project_file(self, path: str | Path) -> None:
        project_path = Path(path)
        logger.info("Loading project | path=%s", project_path)
        self.project = ProjectData.load(project_path)
        self.project.sync_from_active_image()
        self.project_path = project_path
        self.selected_point_id = None
        self.pending_plane_points = []
        self.plane_pick_mode = False
        self._reload_assets_from_project()
        self._reset_history()
        self._mark_project_clean()
        logger.info("Loaded project | path=%s | images=%d", project_path, len(self.project.images))
        self._refresh_ui(status=f"Loaded project {project_path.name}")

    def save_project_file(self, path: str | Path | None = None) -> bool:
        target = Path(path) if path is not None else self.project_path
        if target is None:
            file_name, _ = QFileDialog.getSaveFileName(
                self,
                "Save Project",
                str(Path.cwd() / f"{self.project.name}.imagerect.json"),
                "ImageRect Project (*.imagerect.json)",
            )
            if not file_name:
                return False
            target = Path(file_name)

        self.project.save(target)
        self.project_path = target
        self._mark_project_clean()
        self._update_window_title()
        logger.info("Saved project | path=%s", target)
        self.statusBar().showMessage(f"Saved project to {target}", 5000)
        return True

    def save_project_as(self) -> bool:
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            str(Path.cwd() / f"{self.project.name}.imagerect.json"),
            "ImageRect Project (*.imagerect.json)",
        )
        if file_name:
            return self.save_project_file(file_name)
        return False

    def closeEvent(self, event: QCloseEvent) -> None:
        if not event.spontaneous():
            super().closeEvent(event)
            return
        if not self._confirm_close_with_unsaved_changes():
            event.ignore()
            return
        super().closeEvent(event)

    def _project_state_snapshot(self) -> str:
        self.project.sync_to_active_image()
        return json.dumps(self.project.to_dict(), sort_keys=True, ensure_ascii=False)

    def _mark_project_clean(self) -> None:
        self._saved_project_state = self._project_state_snapshot()

    def _has_unsaved_changes(self) -> bool:
        return self._project_state_snapshot() != self._saved_project_state

    def _confirm_close_with_unsaved_changes(self) -> bool:
        if not self._has_unsaved_changes():
            return True

        decision = QMessageBox.question(
            self,
            "Ungespeicherte Änderungen",
            "Das Projekt enthält ungespeicherte Änderungen. Vor dem Schließen speichern?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if decision == QMessageBox.Save:
            return self.save_project_file()
        return bool(decision == QMessageBox.Discard)

    def run_export(self) -> RectificationExportResult | None:
        self.project.sync_to_active_image()
        settings = self.project.export_settings
        sources, export_warnings = self._collect_export_sources()
        reference_extents = self._current_reference_extents()
        default_path = Path.cwd() / f"{self.project.name}_rectified"
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Export Rectified Image",
            str(default_path),
            "All Files (*)",
        )
        if not file_name:
            return None
        logger.info(
            "Starting export from UI | output=%s | sources=%d | format=%s",
            file_name,
            len(sources),
            settings.output_format,
        )

        reference_segments = None
        if self.reference_2d is not None:
            reference_segments = [
                (segment.start, segment.end) for segment in self.reference_2d.segments
            ]

        source = sources[0]
        combined_warnings = list(dict.fromkeys([*export_warnings, *source.warnings]))

        if len(sources) > 1:
            result = export_mosaic_image(
                sources=sources,
                output_path=file_name,
                pixel_size=settings.pixel_size,
                units=self.project.units,
                output_format=settings.output_format,
                dpi=settings.dpi,
                bit_depth=settings.bit_depth,
                resampling=settings.resampling,
                compression=settings.compression,
                clip_to_hull=settings.clip_to_hull,
                reference_roi=self.project.reference_roi if settings.use_reference_roi else None,
                write_metadata_json=settings.include_json_sidecar,
                embed_in_tiff=settings.embed_in_tiff,
                bigtiff_threshold_bytes=4 * 1024**3,
                multi_layer=settings.multi_layer,
                reference_segments=reference_segments,
                reference_extents=reference_extents,
                project_name=self.project.name,
                warnings=export_warnings,
                blend_radius_px=settings.mosaic_feather_radius_px,
            )
        else:
            progress_dialog = QProgressDialog("Preparing export...", "Cancel", 0, 1, self)
            progress_dialog.setWindowTitle("Exporting")
            progress_dialog.setWindowModality(Qt.WindowModal)
            progress_dialog.setMinimumDuration(0)
            progress_dialog.setValue(0)

            def _progress_callback(current: int, total: int, message: str) -> None:
                progress_dialog.setMaximum(max(total, 1))
                progress_dialog.setValue(min(current, max(total, 1)))
                progress_dialog.setLabelText(message)
                QApplication.processEvents()

            def _cancel_checker() -> bool:
                QApplication.processEvents()
                return bool(progress_dialog.wasCanceled())

            try:
                result = export_rectified_image(
                    source_image=source.source_image,
                    homography_image_to_reference=source.homography_image_to_reference,
                    control_points=source.control_points,
                    output_path=file_name,
                    pixel_size=settings.pixel_size,
                    units=self.project.units,
                    output_format=settings.output_format,
                    dpi=settings.dpi,
                    bit_depth=settings.bit_depth,
                    resampling=settings.resampling,
                    compression=settings.compression,
                    clip_to_hull=settings.clip_to_hull,
                    clip_polygon=source.clip_polygon if settings.use_clip_polygon else None,
                    reference_roi=self.project.reference_roi
                    if settings.use_reference_roi
                    else None,
                    write_metadata_json=settings.include_json_sidecar,
                    embed_in_tiff=settings.embed_in_tiff,
                    multi_layer=settings.multi_layer,
                    reference_segments=reference_segments,
                    progress_callback=_progress_callback,
                    cancel_checker=_cancel_checker,
                    reference_extents=reference_extents,
                    project_name=self.project.name,
                    rms_error=source.rms_error,
                    warnings=combined_warnings,
                    gps_pose=source.gps_pose,
                    camera_pose=source.camera_pose,
                )
            except ExportCancelledError:
                progress_dialog.cancel()
                logger.warning("Export cancelled by user | output=%s", file_name)
                self.statusBar().showMessage("Export cancelled", 5000)
                return None
            finally:
                progress_dialog.close()

        self.statusBar().showMessage(f"Exported {result.image_path.name}", 5000)
        logger.info("Export finished in UI | image=%s", result.image_path)
        metadata_text = (
            f"\nMetadata: {result.metadata_path}"
            if result.metadata_path.exists()
            else "\nMetadata: disabled"
        )
        QMessageBox.information(
            self,
            "Export complete",
            f"Image: {result.image_path}{metadata_text}",
        )
        return result

    def run_synthetic_smoke_test(self, output_root: Path) -> RectificationExportResult:
        """Exercise the window, solver, and export path with synthetic data."""

        reference_path = (
            Path(__file__).resolve().parent.parent
            / "tests"
            / "sample_data"
            / "synthetic_reference.dxf"
        )
        output_root.mkdir(parents=True, exist_ok=True)
        source_path = output_root / "synthetic_source.png"
        plane = np.zeros((301, 401, 3), dtype=np.uint8)
        plane[:] = (238, 238, 238)
        cv2.rectangle(plane, (0, 0), (400, 300), (20, 20, 20), 3)
        cv2.line(plane, (0, 150), (400, 150), (40, 140, 220), 2)
        cv2.line(plane, (200, 0), (200, 300), (40, 140, 220), 2)
        cv2.putText(
            plane,
            "ImageRect",
            (85, 165),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.1,
            (30, 30, 30),
            2,
            cv2.LINE_AA,
        )

        reference_points = np.array(
            [[0.0, 0.0], [400.0, 0.0], [400.0, 300.0], [0.0, 300.0]],
            dtype=np.float32,
        )
        image_points = np.array(
            [[120.0, 420.0], [620.0, 360.0], [560.0, 90.0], [170.0, 120.0]],
            dtype=np.float32,
        )
        canvas = np.zeros((520, 760, 3), dtype=np.uint8)
        homography_ref_to_image = cv2.getPerspectiveTransform(reference_points, image_points)
        cv2.warpPerspective(
            plane,
            homography_ref_to_image,
            (760, 520),
            dst=canvas,
            borderMode=cv2.BORDER_TRANSPARENT,
        )
        if not cv2.imwrite(str(source_path), canvas):
            raise ValueError(f"Unable to write smoke-test source image to {source_path}")

        self.project = ProjectData(name="synthetic_smoke")
        self.project_path = None
        self.source_image_original = None
        self.source_image = None
        self.reference_2d = None
        self.reference_3d = None
        self.transform_result = None
        self.selected_point_id = None
        self.pending_plane_points = []
        self.plane_pick_mode = False
        self._reset_history()
        self.load_image_file(source_path)
        self.load_reference_file(reference_path)

        for image_xy, reference_xy in zip(
            image_points.tolist(), reference_points.tolist(), strict=True
        ):
            point = self.project.add_point()
            point.image_xy = (float(image_xy[0]), float(image_xy[1]))
            point.reference_xy = (float(reference_xy[0]), float(reference_xy[1]))

        self._record_history()
        self._recompute_transform()
        if self.transform_result is None:
            raise ValueError("Smoke test could not solve a homography.")

        return export_rectified_image(
            source_image=self.source_image,
            homography_image_to_reference=self.transform_result.matrix,
            control_points=self.project.paired_points(),
            output_path=output_root / "synthetic_rectified",
            pixel_size=1.0,
            units=self.project.units,
            output_format="png",
            resampling="bilinear",
            clip_to_hull=False,
            reference_extents=self._current_reference_extents(),
            project_name=self.project.name,
            rms_error=self.project.rms_error,
            warnings=self.project.warnings,
        )

    def _build_ui(self) -> None:
        self.setWindowTitle("ImageRect — Metric Image Rectification")
        self.setMinimumSize(1200, 800)
        self.resize(1560, 980)

        self.image_viewer = ImageViewer(self)
        self.reference_viewer = Reference2DViewer(self)
        self.reference3d_viewer = Reference3DViewer(self)
        self.reference_stack = QStackedWidget(self)
        self.reference_stack.addWidget(self.reference_viewer)
        self.reference_stack.addWidget(self.reference3d_viewer)

        self.point_table = PointTable(self)
        self.rms_label = QLabel("RMS: n/a")
        self.warning_label = QLabel("Warnings: need at least four point pairs")
        self.workflow_label = QLabel("Workflow: click image point, then matching reference point")
        self.layer_list = QListWidget(self)
        self.layer_select_all_button = QPushButton("All", self)
        self.layer_select_none_button = QPushButton("None", self)
        self.info_separator = QFrame(self)
        self.info_separator.setObjectName("infoSeparator")
        self.info_separator.setFrameShape(QFrame.HLine)

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.reference_stack, stretch=1)

        self.layer_box = QGroupBox("Layers")
        layer_layout = QVBoxLayout(self.layer_box)
        layer_layout.setContentsMargins(8, 8, 8, 8)
        layer_controls = QWidget(self.layer_box)
        layer_controls_layout = QHBoxLayout(layer_controls)
        layer_controls_layout.setContentsMargins(0, 0, 0, 0)
        layer_controls_layout.addWidget(self.layer_select_all_button)
        layer_controls_layout.addWidget(self.layer_select_none_button)
        layer_controls_layout.addStretch(1)
        layer_layout.addWidget(layer_controls)
        layer_layout.addWidget(self.layer_list)
        right_layout.addWidget(self.layer_box)

        top_splitter = QSplitter(Qt.Horizontal)
        top_splitter.addWidget(self.image_viewer)
        top_splitter.addWidget(right_panel)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 1)

        table_box = QWidget(self)
        table_layout = QVBoxLayout(table_box)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(8)
        info_row = QWidget(self)
        info_layout = QHBoxLayout(info_row)
        info_layout.setContentsMargins(8, 6, 8, 6)
        info_layout.addWidget(self.workflow_label, stretch=2)
        info_layout.addWidget(self.rms_label, stretch=1)
        info_layout.addWidget(self.warning_label, stretch=2)
        table_box.setStyleSheet(f"background: {BG_DARK};")
        self.workflow_label.setStyleSheet(f"color: {TEXT_DIM}; font-style: italic;")
        self.warning_label.setStyleSheet(f"color: {WARNING};")
        rms_font = QFont()
        rms_font.setFamilies(["JetBrains Mono", "SF Mono", "DejaVu Sans Mono", "Monospace"])
        rms_font.setPixelSize(16)
        rms_font.setWeight(QFont.DemiBold)
        self.rms_label.setFont(rms_font)
        self.rms_label.setStyleSheet(f"color: {TEXT_BRIGHT};")
        table_layout.addWidget(self.info_separator)
        table_layout.addWidget(info_row)
        table_layout.addWidget(self.point_table)

        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(table_box)
        main_splitter.setStretchFactor(0, 5)
        main_splitter.setStretchFactor(1, 2)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(main_splitter)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar(self))

        self.project_panel = ProjectPanel(self)
        self.project_dock = QDockWidget("Project Settings", self)
        self.project_dock.setObjectName("projectSettingsDock")
        self.project_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.project_dock.setWidget(self.project_panel)
        self.project_dock.setMinimumWidth(320)
        self.addDockWidget(Qt.RightDockWidgetArea, self.project_dock)

    def _create_actions(self) -> None:
        self.action_new = QAction("New", self)
        self.action_new.setShortcut(QKeySequence.New)
        self.action_open_project = QAction("Open Project", self)
        self.action_open_project.setShortcut(QKeySequence.Open)
        self.action_save_project = QAction("Save Project", self)
        self.action_save_project.setShortcut(QKeySequence.Save)
        self.action_save_project_as = QAction("Save Project As", self)
        self.action_save_project_as.setShortcut(QKeySequence.SaveAs)
        self.action_load_image = QAction("Load Image", self)
        self.action_load_image.setShortcut(QKeySequence("Ctrl+I"))
        self.action_lens_correction = QAction("Lens Correction", self)
        self.action_load_reference = QAction("Load DXF", self)
        self.action_load_reference.setShortcut(QKeySequence("Ctrl+D"))
        self.action_load_reference3d = QAction("Load 3D Reference", self)
        self.action_load_reference3d.setShortcut(QKeySequence("Ctrl+Shift+D"))
        self.action_image_roi = QAction("Image ROI", self)
        self.action_image_roi.setCheckable(True)
        self.action_reference_roi = QAction("DXF Region", self)
        self.action_reference_roi.setCheckable(True)
        self.action_fit_reference_view = QAction("An DXF anpassen", self)
        self.action_fit_reference_view.setShortcut(QKeySequence("Ctrl+0"))
        self.action_fit_reference_roi_view = QAction("An ROI anpassen", self)
        self.action_fit_reference_roi_view.setShortcut(QKeySequence("Ctrl+Shift+0"))
        self.action_fit_image_view = QAction("Bild anpassen", self)
        self.action_fit_image_view.setShortcut(QKeySequence("Ctrl+1"))
        self.action_define_plane_from_points = QAction("Plane From 3 Points", self)
        self.action_define_plane_auto = QAction("Plane Auto", self)
        self.action_export = QAction("Export Rectified Image", self)
        self.action_export.setShortcut(QKeySequence("Ctrl+E"))
        self.action_toggle_project_panel = self.project_dock.toggleViewAction()
        self.action_toggle_project_panel.setText("Project Settings")
        self.action_toggle_project_panel.setShortcut(QKeySequence("Ctrl+P"))
        self.action_delete_point = QAction("Delete Point", self)
        self.action_delete_point.setShortcut(QKeySequence.Delete)
        self.action_move_up = QAction("Move Point Up", self)
        self.action_move_up.setShortcut(QKeySequence("Ctrl+Up"))
        self.action_move_down = QAction("Move Point Down", self)
        self.action_move_down.setShortcut(QKeySequence("Ctrl+Down"))
        self.action_undo = QAction("Undo", self)
        self.action_undo.setShortcut(QKeySequence.Undo)
        self.action_redo = QAction("Redo", self)
        self.action_redo.setShortcut(QKeySequence.Redo)
        self.action_open_log_directory = QAction("Log-Ordner öffnen", self)
        self.action_export_diagnose_package = QAction("Diagnose-Paket exportieren...", self)
        self._apply_action_descriptions()

        self.action_load_image.setIcon(make_symbol_icon("📷"))
        self.action_lens_correction.setIcon(make_symbol_icon("🔍"))
        self.action_load_reference.setIcon(make_symbol_icon("📐"))
        self.action_load_reference3d.setIcon(make_symbol_icon("📦"))
        self.action_image_roi.setIcon(make_symbol_icon("✂"))
        self.action_reference_roi.setIcon(make_symbol_icon("▭"))
        self.action_define_plane_from_points.setIcon(make_symbol_icon("◫"))
        self.action_define_plane_auto.setIcon(make_symbol_icon("🧭"))
        self.action_export.setIcon(make_symbol_icon("💾"))
        self.action_undo.setIcon(make_symbol_icon("↩"))
        self.action_redo.setIcon(make_symbol_icon("↪"))

        menu_file = self.menuBar().addMenu("File")
        menu_file.addAction(self.action_new)
        menu_file.addAction(self.action_open_project)
        menu_file.addAction(self.action_save_project)
        menu_file.addAction(self.action_save_project_as)
        menu_file.addSeparator()
        menu_file.addAction(self.action_load_image)
        menu_file.addAction(self.action_lens_correction)
        menu_file.addAction(self.action_load_reference)
        menu_file.addAction(self.action_load_reference3d)
        menu_file.addSeparator()
        menu_file.addAction(self.action_export)

        menu_view = self.menuBar().addMenu("Ansicht")
        menu_view.addAction(self.action_fit_reference_view)
        menu_view.addAction(self.action_fit_reference_roi_view)
        menu_view.addAction(self.action_fit_image_view)
        menu_view.addSeparator()
        menu_view.addAction(self.action_image_roi)
        menu_view.addAction(self.action_reference_roi)
        menu_view.addSeparator()
        menu_view.addAction(self.action_toggle_project_panel)

        menu_edit = self.menuBar().addMenu("Edit")
        menu_edit.addAction(self.action_undo)
        menu_edit.addAction(self.action_redo)
        menu_edit.addSeparator()
        menu_edit.addAction(self.action_delete_point)
        menu_edit.addAction(self.action_move_up)
        menu_edit.addAction(self.action_move_down)

        menu_3d = self.menuBar().addMenu("3D")
        menu_3d.addAction(self.action_define_plane_from_points)
        menu_3d.addAction(self.action_define_plane_auto)

        menu_help = self.menuBar().addMenu("Hilfe")
        menu_help.addAction(self.action_open_log_directory)
        menu_help.addAction(self.action_export_diagnose_package)

        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        toolbar.setIconSize(icon_size())
        toolbar.addAction(self.action_load_image)
        toolbar.addAction(self.action_lens_correction)
        toolbar.addAction(self.action_load_reference)
        toolbar.addAction(self.action_load_reference3d)
        toolbar.addSeparator()
        toolbar.addAction(self.action_image_roi)
        toolbar.addAction(self.action_reference_roi)
        toolbar.addSeparator()
        toolbar.addAction(self.action_define_plane_from_points)
        toolbar.addAction(self.action_define_plane_auto)
        toolbar.addSeparator()
        toolbar.addAction(self.action_export)
        toolbar.addSeparator()
        toolbar.addAction(self.action_undo)
        toolbar.addAction(self.action_redo)
        self.addToolBar(toolbar)

    def _apply_action_descriptions(self) -> None:
        descriptions = {
            self.action_new: "Start a new empty project",
            self.action_open_project: "Open a saved ImageRect project",
            self.action_save_project: "Save the current project",
            self.action_save_project_as: "Save the current project under a new name",
            self.action_load_image: "Load a source image from disk",
            self.action_lens_correction: "Open the lens correction dialog for the active image",
            self.action_load_reference: "Load a DXF reference drawing",
            self.action_load_reference3d: "Load an E57 point cloud or OBJ mesh",
            self.action_image_roi: "Draw or edit the image clip polygon",
            self.action_reference_roi: "Draw or edit the DXF export region",
            self.action_fit_reference_view: "Fit the full DXF reference to the viewport",
            self.action_fit_reference_roi_view: "Fit the current DXF ROI to the viewport",
            self.action_fit_image_view: "Fit the source image to the viewport",
            self.action_define_plane_from_points: "Define a 3D working plane from three picks",
            self.action_define_plane_auto: "Estimate a 3D working plane automatically",
            self.action_export: "Export the rectified image or mosaic",
            self.action_toggle_project_panel: "Show or hide the project settings panel",
            self.action_delete_point: "Delete the selected control point",
            self.action_move_up: "Move the selected point one row up",
            self.action_move_down: "Move the selected point one row down",
            self.action_undo: "Undo the last project edit",
            self.action_redo: "Redo the previously undone project edit",
            self.action_open_log_directory: "Open the local ImageRect log folder",
            self.action_export_diagnose_package: (
                "Export logs, system info, and the current project"
            ),
        }
        for action, text in descriptions.items():
            action.setStatusTip(text)
            action.setToolTip(text)

    def _connect_signals(self) -> None:
        self.image_viewer.point_picked.connect(self._handle_image_pick)
        self.image_viewer.point_selected.connect(self._set_selected_point)
        self.image_viewer.clip_polygon_changed.connect(self._handle_clip_polygon_changed)
        self.image_viewer.clip_polygon_finished.connect(self._finish_clip_polygon_mode)
        self.reference_viewer.point_picked.connect(self._handle_reference_pick)
        self.reference_viewer.point_selected.connect(self._set_selected_point)
        self.reference_viewer.reference_roi_changed.connect(self._handle_reference_roi_changed)
        self.reference_viewer.reference_roi_finished.connect(self._finish_reference_roi_mode)
        self.reference3d_viewer.point_picked.connect(self._handle_reference3d_pick)
        self.reference3d_viewer.point_selected.connect(self._set_selected_point)
        self.image_viewer.cursor_message.connect(self._show_cursor_message)
        self.reference_viewer.cursor_message.connect(self._show_cursor_message)
        self.reference3d_viewer.cursor_message.connect(self._show_cursor_message)
        self.point_table.point_selected.connect(self._set_selected_point)
        self.point_table.label_changed.connect(self._update_point_label)
        self.point_table.enabled_changed.connect(self._update_point_enabled)
        self.point_table.lock_changed.connect(self._update_point_lock)
        self.point_table.delete_requested.connect(self._delete_selected_point)
        self.project_panel.active_image_changed.connect(self._switch_active_image)
        self.project_panel.project_name_changed.connect(self._update_project_name)
        self.project_panel.units_changed.connect(self._update_project_units)
        self.project_panel.export_settings_changed.connect(self._update_export_settings)
        self.layer_list.itemChanged.connect(self._layer_item_changed)
        self.layer_select_all_button.clicked.connect(lambda: self._set_all_layers_visible(True))
        self.layer_select_none_button.clicked.connect(lambda: self._set_all_layers_visible(False))

        self.action_new.triggered.connect(self._new_project)
        self.action_open_project.triggered.connect(self._open_project_dialog)
        self.action_save_project.triggered.connect(lambda checked=False: self.save_project_file())
        self.action_save_project_as.triggered.connect(self.save_project_as)
        self.action_load_image.triggered.connect(self._open_image_dialog)
        self.action_lens_correction.triggered.connect(self._open_lens_dialog)
        self.action_load_reference.triggered.connect(self._open_reference_dialog)
        self.action_load_reference3d.triggered.connect(self._open_reference3d_dialog)
        self.action_fit_reference_view.triggered.connect(
            self.reference_viewer.fit_reference_to_view
        )
        self.action_fit_reference_roi_view.triggered.connect(
            self.reference_viewer.fit_reference_roi_to_view
        )
        self.action_fit_image_view.triggered.connect(self.image_viewer.fit_image_to_view)
        self.action_image_roi.toggled.connect(self._toggle_clip_polygon_mode)
        self.action_reference_roi.toggled.connect(self._toggle_reference_roi_mode)
        self.action_define_plane_from_points.triggered.connect(self._start_plane_from_3_points)
        self.action_define_plane_auto.triggered.connect(self._define_plane_auto)
        self.action_export.triggered.connect(self._run_export_dialog)
        self.action_delete_point.triggered.connect(self._delete_selected_point)
        self.action_move_up.triggered.connect(lambda checked=False: self._move_selected_point(-1))
        self.action_move_down.triggered.connect(lambda checked=False: self._move_selected_point(1))
        self.action_undo.triggered.connect(self._undo)
        self.action_redo.triggered.connect(self._redo)
        self.action_open_log_directory.triggered.connect(self._open_log_directory)
        self.action_export_diagnose_package.triggered.connect(self._export_diagnose_package)

    def _open_image_dialog(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Load Image",
            str(Path.cwd()),
            "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.ppm)",
        )
        if file_name:
            try:
                self.load_image_file(file_name)
            except Exception as exc:
                self._show_file_action_error("Bild laden fehlgeschlagen", exc)

    def _open_lens_dialog(self) -> None:
        if self.source_image_original is None:
            self.statusBar().showMessage("Load an image before configuring lens correction", 5000)
            return

        image_path = self.project.resolve_active_image_path()
        dialog = LensDialog(
            image=self.source_image_original,
            image_path=image_path,
            current_profile=self._current_lens_profile(),
            parent=self,
        )
        if dialog.exec() == 0:
            return

        previous_profile = self._current_lens_profile()
        next_profile = dialog.selected_profile()
        self._remap_active_image_geometry_for_lens_change(previous_profile, next_profile)
        self.project.lens_correction = dialog.lens_correction_payload()
        self._refresh_source_image()
        self._record_history()
        self._recompute_transform()
        logger.info(
            "Applied lens correction in UI | previous=%s | next=%s",
            previous_profile.name if previous_profile is not None else "none",
            next_profile.name,
        )
        self._refresh_ui(status="Applied lens correction; image points and ROI were updated")

    def _open_reference_dialog(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Load DXF",
            str(Path.cwd()),
            "DXF Files (*.dxf);;DWG Files — shows help (*.dwg)",
        )
        if file_name:
            try:
                self.load_reference_file(file_name)
            except Exception as exc:
                self._show_file_action_error("DXF laden fehlgeschlagen", exc)

    def _open_reference3d_dialog(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Load 3D Reference",
            str(Path.cwd()),
            "3D Reference (*.e57 *.obj)",
        )
        if file_name:
            try:
                self.load_3d_reference_file(file_name)
            except Exception as exc:
                self._show_file_action_error("3D-Referenz laden fehlgeschlagen", exc)

    def _open_project_dialog(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            str(Path.cwd()),
            "ImageRect Project (*.imagerect.json)",
        )
        if file_name:
            try:
                self.load_project_file(file_name)
            except Exception as exc:
                self._show_file_action_error("Projekt laden fehlgeschlagen", exc)

    def _show_file_action_error(self, title: str, exc: Exception) -> None:
        logger.exception("%s | error=%s", title, exc)
        QMessageBox.critical(self, title, str(exc))

    def _run_export_dialog(self) -> None:
        try:
            if not self._confirm_export_preview():
                return
            self.run_export()
        except Exception as exc:
            logger.exception("Export dialog failed")
            QMessageBox.critical(self, "Export failed", str(exc))

    def _open_log_directory(self) -> None:
        directory = log_directory()
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory))):
            logger.warning("Could not open log directory in file manager | path=%s", directory)
            QMessageBox.warning(
                self,
                "Log-Ordner öffnen fehlgeschlagen",
                f"Der Log-Ordner konnte nicht geöffnet werden:\n{directory}",
            )
            return
        logger.info("Opened log directory in file manager | path=%s", directory)

    def _export_diagnose_package(self) -> None:
        suggested_name = f"imagerect-diagnose-{datetime.now().strftime('%Y-%m-%d')}.zip"
        default_path = Path.cwd() / suggested_name
        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "Diagnose-Paket exportieren",
            str(default_path),
            "ZIP-Dateien (*.zip)",
        )
        if not file_name:
            return

        try:
            package_path = build_diagnose_package(Path(file_name), self.project_path)
        except Exception as exc:
            logger.exception("Diagnose package export failed")
            QMessageBox.critical(self, "Diagnose-Paket fehlgeschlagen", str(exc))
            return

        QMessageBox.information(
            self,
            "Diagnose-Paket exportiert",
            f"Datei gespeichert unter:\n{package_path}",
        )
        logger.info("Diagnose package exported from UI | path=%s", package_path)

    def _new_project(self) -> None:
        self.project = ProjectData()
        self.project.sync_from_active_image()
        self.project_path = None
        self.reference_2d = None
        self.reference_3d = None
        self.source_image_original = None
        self.source_image = None
        self.transform_result = None
        self.selected_point_id = None
        self.pending_plane_points = []
        self.plane_pick_mode = False
        self._current_mode = "view"
        self._reset_history()
        self._mark_project_clean()
        self._refresh_ui(status="Started a new project")

    def _handle_image_pick(self, x: float, y: float) -> None:
        point = self._resolve_target_point("image")
        if point is None:
            return
        point.image_xy = (x, y)
        self._record_history()
        self._recompute_transform()
        self._refresh_ui(
            status=f"Stored image point for {point.label}; pick matching reference point"
        )

    def _handle_reference_pick(self, x: float, y: float) -> None:
        point = self._resolve_target_point("reference")
        if point is None:
            return
        point.reference_xy = (x, y)
        self._record_history()
        self._recompute_transform()
        self._refresh_ui(status=f"Stored reference point for {point.label}")

    def _handle_reference3d_pick(self, x: float, y: float, z: float) -> None:
        if self.reference_3d is None:
            return
        point_3d = np.array([x, y, z], dtype=np.float64)

        if self.plane_pick_mode:
            self.pending_plane_points.append(point_3d)
            self.reference3d_viewer.set_temporary_points(self.pending_plane_points)
            if len(self.pending_plane_points) == 3:
                plane = define_plane_from_3_points(*self.pending_plane_points)
                self._apply_working_plane(plane, "Defined working plane from 3 points")
            else:
                self.statusBar().showMessage(
                    f"Working plane: picked {len(self.pending_plane_points)}/3 points",
                    5000,
                )
            return

        if self.reference_3d.working_plane is None:
            self.statusBar().showMessage(
                "Define a working plane before picking 3D reference points",
                5000,
            )
            return

        snapped = pick_nearest_point(
            self.reference_3d,
            point_3d,
            tolerance=self._point_pick_tolerance(),
        )
        world_point = snapped if snapped is not None else point_3d
        uv = project_3d_to_plane(
            np.asarray([world_point], dtype=np.float64),
            self.reference_3d.working_plane,
        )[0]
        point = self._resolve_target_point("reference")
        if point is None:
            return
        point.reference_xy = (float(uv[0]), float(uv[1]))
        self.project.reference_world_points[point.id] = (
            float(world_point[0]),
            float(world_point[1]),
            float(world_point[2]),
        )
        self._record_history()
        self._recompute_transform()
        self._refresh_ui(status=f"Stored 3D reference point for {point.label}")

    def _start_plane_from_3_points(self) -> None:
        if self.reference_3d is None:
            self.statusBar().showMessage("Load a 3D reference first", 5000)
            return
        self.pending_plane_points = []
        self.plane_pick_mode = True
        self._current_mode = "view"
        self.reference3d_viewer.set_temporary_points([])
        self.statusBar().showMessage(
            "Plane mode: pick three points on the 3D geometry",
            5000,
        )

    def _define_plane_auto(self) -> None:
        if self.reference_3d is None:
            self.statusBar().showMessage("Load a 3D reference first", 5000)
            return
        source_points = reference_source_points(self.reference_3d)
        if source_points is None or len(source_points) < 3:
            logger.warning("Automatic plane fit rejected due to too few 3D points")
            QMessageBox.warning(self, "Plane fit failed", "3D reference contains too few points.")
            return
        try:
            plane = define_plane_ransac(source_points)
        except Exception as exc:
            logger.exception("Automatic plane fit failed")
            QMessageBox.critical(self, "Plane fit failed", str(exc))
            return
        self._apply_working_plane(plane, "Defined working plane automatically")

    def _apply_working_plane(self, plane: WorkingPlane, status: str) -> None:
        if self.reference_3d is None:
            return
        self.reference_3d.working_plane = plane
        self.project.working_plane = working_plane_to_dict(plane)
        self.pending_plane_points = []
        self.plane_pick_mode = False
        self._current_mode = "view"
        for point_id, world_point in list(self.project.reference_world_points.items()):
            point = self.project.get_point(point_id)
            if point is None:
                self.project.reference_world_points.pop(point_id, None)
                continue
            uv = project_3d_to_plane(np.asarray([world_point], dtype=np.float64), plane)[0]
            point.reference_xy = (float(uv[0]), float(uv[1]))
        self._record_history()
        self._recompute_transform()
        self._refresh_ui(status=status)

    def _resolve_target_point(self, side: str) -> ControlPoint | None:
        current_point_id = self.point_table.current_point_id()
        selected = (
            self.project.get_point(current_point_id) if current_point_id is not None else None
        )
        if selected is not None and selected.locked:
            self.statusBar().showMessage("Selected point is locked", 3000)
            return None

        if side == "image":
            if selected is not None and selected.image_xy is None:
                return selected
            for point in reversed(self.project.points):
                if (
                    point.enabled
                    and not point.locked
                    and point.image_xy is None
                    and point.reference_xy is not None
                ):
                    self._set_selected_point(point.id)
                    return point
        else:
            if selected is not None and selected.reference_xy is None:
                return selected
            for point in reversed(self.project.points):
                if (
                    point.enabled
                    and not point.locked
                    and point.reference_xy is None
                    and point.image_xy is not None
                ):
                    self._set_selected_point(point.id)
                    return point

        point = self.project.add_point()
        self._set_selected_point(point.id)
        return point

    def _delete_selected_point(self) -> None:
        point_id = self.point_table.current_point_id()
        if point_id is None:
            return
        self.project.remove_point(point_id)
        if self.selected_point_id == point_id:
            self.selected_point_id = None
        self._record_history()
        self._recompute_transform()
        self._refresh_ui(status=f"Deleted point {point_id}")

    def _move_selected_point(self, offset: int) -> None:
        point_id = self.point_table.current_point_id()
        if point_id is None:
            return
        self.project.move_point(point_id, offset)
        self._record_history()
        self._refresh_ui(status=f"Reordered point {point_id}")
        self._set_selected_point(point_id)

    def _update_point_label(self, point_id: int, label: str) -> None:
        point = self.project.get_point(point_id)
        if point is None:
            return
        point.label = label or point.label
        self._record_history()
        self._refresh_ui(status=f"Updated label for point {point_id}")

    def _update_point_enabled(self, point_id: int, enabled: bool) -> None:
        point = self.project.get_point(point_id)
        if point is None:
            return
        point.enabled = enabled
        self._record_history()
        self._recompute_transform()
        self._refresh_ui(status=f"{'Enabled' if enabled else 'Disabled'} point {point_id}")

    def _update_point_lock(self, point_id: int, locked: bool) -> None:
        point = self.project.get_point(point_id)
        if point is None:
            return
        point.locked = locked
        self._record_history()
        self._refresh_ui(status=f"{'Locked' if locked else 'Unlocked'} point {point_id}")

    def _update_project_name(self, name: str) -> None:
        self.project.name = name
        self.project.touch()
        self._update_window_title()

    def _switch_active_image(self, index: int) -> None:
        if index < 0 or index == self.project.active_image_index:
            return
        self.project.sync_to_active_image()
        self.project.active_image_index = index
        self.project.sync_from_active_image()
        self.selected_point_id = None
        self._load_current_image_asset()
        self._recompute_transform()
        self._refresh_ui(status=f"Switched to image {Path(self.project.image_path).name}")

    def _update_project_units(self, units: str) -> None:
        locked_units = self._locked_reference_units()
        if locked_units is not None:
            self.project.units = locked_units
            self._refresh_project_panel_context()
            return
        self.project.units = units
        self.project.touch()
        if self.project.rms_error is None:
            self.rms_label.setText("RMS: n/a")
        else:
            self.rms_label.setText(f"RMS: {self.project.rms_error:.3f} {self.project.units}")
        self._refresh_project_panel_context()

    def _update_export_settings(self, settings: object) -> None:
        if not isinstance(settings, ExportSettings):
            return
        self.project.export_settings = settings
        self.project.touch()
        self._refresh_project_panel_context()

    @staticmethod
    def _lens_profile_from_correction(
        correction: dict[str, object] | None,
    ) -> LensProfile | None:
        if not correction or not correction.get("applied"):
            return None

        profile_payload = correction.get("profile")
        if not isinstance(profile_payload, dict):
            return None

        try:
            return lens_profile_from_dict(profile_payload)
        except (KeyError, TypeError, ValueError):
            return None

    def _load_image_entry_source(self, entry: ImageEntry) -> np.ndarray:
        image_path = self.project.resolve_image_entry_path(entry)
        if image_path is None:
            raise ValueError("Image entry has no source path.")
        image = load_image(image_path)
        profile = self._lens_profile_from_correction(entry.lens_correction)
        if profile is None:
            return image
        return apply_lens_correction(image, profile)

    def _locked_reference_units(self) -> str | None:
        if self.reference_2d is not None and self.reference_2d.units != "unitless":
            return self.reference_2d.units
        if self.reference_3d is not None and self.reference_3d.units != "unitless":
            return self.reference_3d.units
        return None

    def _entry_label(self, entry: ImageEntry, index: int) -> str:
        image_path = self.project.resolve_image_entry_path(entry)
        if image_path is not None:
            return image_path.stem or f"Image {index + 1}"
        return Path(entry.path).stem or f"Image {index + 1}"

    def _entry_gps_pose(self, entry: ImageEntry) -> dict[str, object] | None:
        if entry.gps_pose is not None:
            return entry.gps_pose
        image_path = self.project.resolve_image_entry_path(entry)
        if image_path is None:
            return None
        entry.gps_pose = extract_gps_pose(image_path)
        return entry.gps_pose

    def _homography_for_entry(self, entry: ImageEntry) -> tuple[np.ndarray, list[str]]:
        paired_points = [point for point in entry.points if point.is_enabled_pair]
        if len(paired_points) < 4:
            raise ValueError("at least four paired points are required")
        if entry.transform_matrix is not None:
            return np.asarray(entry.transform_matrix, dtype=np.float64), list(entry.warnings)

        result = solve_planar_homography(
            [point.image_xy for point in paired_points if point.image_xy is not None],
            [point.reference_xy for point in paired_points if point.reference_xy is not None],
        )
        warnings = list(dict.fromkeys([*entry.warnings, *result.warnings]))
        if warnings == list(entry.warnings):
            warnings.append("Homography recomputed from stored control points")
        return result.matrix, warnings

    def _build_entry_camera_pose(
        self,
        entry: ImageEntry,
        source_image: np.ndarray,
        homography_image_to_reference: np.ndarray,
    ) -> dict[str, object] | None:
        profile = self._lens_profile_from_correction(entry.lens_correction)
        if profile is None:
            return None
        return build_camera_pose(
            homography_image_to_reference=homography_image_to_reference,
            image_size=(source_image.shape[1], source_image.shape[0]),
            profile=profile,
            gps_pose=entry.gps_pose,
            reference_crs_epsg=self.project.reference_crs_epsg,
        )

    def _collect_export_sources(self) -> tuple[list[MosaicSource], list[str]]:
        self.project.ensure_image_entries()

        sources: list[MosaicSource] = []
        warnings: list[str] = []
        for index, entry in enumerate(self.project.images):
            if not entry.path:
                continue
            label = self._entry_label(entry, index)
            paired_points = [point for point in entry.points if point.is_enabled_pair]
            if len(paired_points) < 4:
                warnings.append(f"Skipped {label}: needs at least four paired points")
                continue
            image_path = self.project.resolve_image_entry_path(entry)
            if image_path is None:
                continue
            if not image_path.exists():
                warnings.append(f"Skipped {label}: source image not found")
                continue

            gps_pose = (
                entry.gps_pose if entry.gps_pose is not None else extract_gps_pose(image_path)
            )
            entry.gps_pose = gps_pose
            source_image = self._load_image_entry_source(entry)
            try:
                homography, entry_warnings = self._homography_for_entry(entry)
            except Exception as exc:
                warnings.append(f"Skipped {label}: homography invalid ({exc})")
                continue
            sources.append(
                MosaicSource(
                    label=label,
                    source_image=source_image,
                    homography_image_to_reference=homography,
                    control_points=paired_points,
                    clip_polygon=entry.clip_polygon,
                    gps_pose=gps_pose,
                    camera_pose=self._build_entry_camera_pose(entry, source_image, homography),
                    rms_error=entry.rms_error,
                    warnings=tuple(entry_warnings),
                )
            )
            warnings.extend(entry_warnings)

        if not sources:
            raise ValueError("At least one image with four valid point pairs is required.")
        return sources, list(dict.fromkeys(warnings))

    def _total_project_point_count(self) -> int:
        self.project.ensure_image_entries()
        return sum(len(entry.points) for entry in self.project.images)

    def _remap_active_image_geometry_for_lens_change(
        self,
        old_profile: LensProfile | None,
        new_profile: LensProfile | None,
    ) -> None:
        if self.source_image_original is None or old_profile == new_profile:
            return

        image_size = (
            self.source_image_original.shape[1],
            self.source_image_original.shape[0],
        )
        image_points = [
            point.image_xy for point in self.project.points if point.image_xy is not None
        ]
        if image_points:
            remapped_points = iter(
                remap_points_between_profiles(
                    image_points,
                    image_size,
                    old_profile,
                    new_profile,
                )
            )
            for point in self.project.points:
                if point.image_xy is not None:
                    point.image_xy = next(remapped_points)

        if self.project.clip_polygon:
            self.project.clip_polygon = remap_points_between_profiles(
                self.project.clip_polygon,
                image_size,
                old_profile,
                new_profile,
            )

    def _activate_or_create_image(self, image_path: Path) -> None:
        normalized_image_path = image_path.resolve()
        existing_index = next(
            (
                index
                for index, entry in enumerate(self.project.images)
                if self.project.resolve_image_entry_path(entry) == normalized_image_path
            ),
            None,
        )
        if existing_index is None:
            if not self.project.images:
                self.project.images.append(ImageEntry(path=str(normalized_image_path)))
                self.project.active_image_index = 0
            elif len(self.project.images) == 1 and not self.project.images[0].path:
                self.project.images[0].path = str(normalized_image_path)
                self.project.active_image_index = 0
            else:
                self.project.images.append(ImageEntry(path=str(normalized_image_path)))
                self.project.active_image_index = len(self.project.images) - 1
        else:
            self.project.active_image_index = existing_index

        self.project.sync_from_active_image()
        self.project.image_path = str(normalized_image_path)
        if existing_index is None:
            self.project.lens_correction = None
            self.project.clip_polygon = None
            self.project.points = []
            self.project.reference_world_points = {}
            self.project.rms_error = None
            self.project.transform_matrix = None
            self.project.warnings = []

    def _load_current_image_asset(self) -> None:
        self.source_image_original = None
        self.source_image = None
        image_path = self.project.resolve_active_image_path()
        if image_path is not None and image_path.exists():
            self.source_image_original = load_image(image_path)
            self._refresh_source_image()
            if self.project.images:
                self.project.images[self.project.active_image_index].gps_pose = extract_gps_pose(
                    image_path
                )

    def _rough_gps_markers(self) -> list[tuple[str, tuple[float, float]]]:
        if self.reference_2d is None or not self.project.images:
            return []

        if self.project.reference_crs_epsg is not None:
            transformed_markers: list[tuple[str, tuple[float, float]]] = []
            for index, image in enumerate(self.project.images):
                gps_pose = self._entry_gps_pose(image)
                if gps_pose is None:
                    continue
                reference_xy = gps_to_reference_xy(gps_pose, self.project.reference_crs_epsg)
                if reference_xy is None:
                    continue
                label = self._entry_label(image, index)
                transformed_markers.append((label, reference_xy))
            if transformed_markers:
                return transformed_markers

        origin_index = next(
            (
                index
                for index, image in enumerate(self.project.images)
                if self._entry_gps_pose(image) is not None
            ),
            None,
        )
        if origin_index is None:
            return []

        origin_pose = self._entry_gps_pose(self.project.images[origin_index])
        if origin_pose is None:
            return []

        center_x = (self.reference_2d.extents_min[0] + self.reference_2d.extents_max[0]) * 0.5
        center_y = (self.reference_2d.extents_min[1] + self.reference_2d.extents_max[1]) * 0.5
        units_per_meter = 1000.0 / max(unit_to_mm(self.project.units), 1e-6)

        markers: list[tuple[str, tuple[float, float]]] = []
        for index, image in enumerate(self.project.images):
            gps_pose = self._entry_gps_pose(image)
            if gps_pose is None:
                continue
            offset = gps_offset_meters(origin_pose, gps_pose)
            if offset is None:
                continue
            label = self._entry_label(image, index)
            markers.append(
                (
                    label,
                    (
                        center_x + offset[0] * units_per_meter,
                        center_y + offset[1] * units_per_meter,
                    ),
                )
            )
        return markers

    def _set_selected_point(self, point_id: int | None) -> None:
        self.selected_point_id = point_id
        self.point_table.select_point(point_id)
        self.image_viewer.set_points(self.project.points, point_id)
        self.reference_viewer.set_points(self.project.points, point_id)
        self.reference3d_viewer.set_control_points(
            self.project.reference_world_points,
            point_id,
        )

    def _recompute_transform(self) -> None:
        paired_points = self.project.paired_points()
        self.project.clear_solver_state()
        self.transform_result = None

        if len(paired_points) < 4:
            self.project.sync_to_active_image()
            return

        try:
            result = solve_planar_homography(
                [point.image_xy for point in paired_points if point.image_xy is not None],
                [point.reference_xy for point in paired_points if point.reference_xy is not None],
            )
        except Exception as exc:
            logger.warning("Homography recompute failed | error=%s", exc)
            self.project.warnings = [str(exc)]
            self.project.sync_to_active_image()
            return

        self.transform_result = result
        self.project.transform_matrix = result.matrix.tolist()
        self.project.warnings = list(result.warnings)
        self.project.rms_error = result.rms_error
        for point, residual, residual_vector in zip(
            paired_points,
            result.residuals,
            result.residual_vectors,
            strict=True,
        ):
            point.residual = residual
            point.residual_vector = residual_vector
        self.project.sync_to_active_image()

    def _refresh_ui(self, status: str | None = None) -> None:
        self.project.ensure_image_entries()
        self.image_viewer.set_image(self.source_image)
        self.reference_viewer.set_reference(self.reference_2d)
        self.reference_viewer.set_points(self.project.points, self.selected_point_id)
        self.reference_viewer.set_gps_markers(self._rough_gps_markers())
        self.reference3d_viewer.set_reference(self.reference_3d)
        if self.reference_3d is not None:
            self.reference3d_viewer.set_working_plane(
                self.reference_3d.working_plane,
                self._safe_plane_extents(),
            )
        self.reference3d_viewer.set_control_points(
            self.project.reference_world_points,
            self.selected_point_id,
        )
        self.reference3d_viewer.set_temporary_points(self.pending_plane_points)
        self.image_viewer.set_points(self.project.points, self.selected_point_id)
        self.image_viewer.set_clip_polygon(self.project.clip_polygon)
        self.image_viewer.set_clip_polygon_mode(self.action_image_roi.isChecked())
        self.reference_viewer.set_reference_roi(self.project.reference_roi)
        self.reference_viewer.set_reference_roi_mode(self.action_reference_roi.isChecked())
        self.point_table.set_points(self.project.points, self.selected_point_id)
        self.project_panel.set_project(self.project)
        self._refresh_project_panel_context()
        self._populate_layer_list()
        self._sync_reference_mode()

        if self.project.rms_error is None:
            self.rms_label.setText("RMS: n/a")
        else:
            self.rms_label.setText(f"RMS: {self.project.rms_error:.3f} {self.project.units}")
        self.rms_label.setStyleSheet(f"color: {color_for_rms(self.project.rms_error)};")

        warning_text = ", ".join(self.project.warnings) if self.project.warnings else "none"
        if self.plane_pick_mode:
            warning_text = f"{warning_text}; working plane pick mode active"
        self.warning_label.setText(f"\u26a0 Warnings: {warning_text}")
        self._update_window_title()
        self._update_history_actions()
        self._update_3d_actions()
        self._update_export_action()
        if status is not None:
            self.statusBar().showMessage(status, 5000)

    def _reload_assets_from_project(self) -> None:
        self.project.sync_from_active_image()
        self.source_image = None
        self.source_image_original = None
        self.reference_2d = None
        self.reference_3d = None
        image_path = self.project.resolve_active_image_path()
        if image_path is not None and image_path.exists():
            self.source_image_original = load_image(image_path)
            self._refresh_source_image()

        reference_path = self.project.resolve_reference_path()
        if reference_path and reference_path.exists():
            if self.project.reference_type == "dxf":
                self.reference_2d = load_dxf(reference_path)
                if self.reference_2d.crs_epsg is not None:
                    self.project.reference_crs_epsg = self.reference_2d.crs_epsg
                if self.reference_2d.units != "unitless":
                    self.project.units = self.reference_2d.units
            elif self.project.reference_type == "e57":
                self.reference_3d = load_e57(reference_path)
            elif self.project.reference_type == "obj":
                self.reference_3d = load_obj(reference_path)
            if self.reference_3d is not None and self.reference_3d.units != "unitless":
                self.project.units = self.reference_3d.units

        if self.reference_3d is not None:
            self.reference_3d.working_plane = working_plane_from_dict(self.project.working_plane)
        self._recompute_transform()

    def _populate_layer_list(self) -> None:
        current_states = {
            self.layer_list.item(index).text(): self.layer_list.item(index).checkState()
            == Qt.Checked
            for index in range(self.layer_list.count())
        }
        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        if self.reference_2d is not None:
            for layer in self.reference_2d.layers:
                item = QListWidgetItem(layer.name)
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
                visible = current_states.get(layer.name, layer.visible)
                item.setCheckState(Qt.Checked if visible else Qt.Unchecked)
                self.layer_list.addItem(item)
                self.reference_viewer.set_layer_visibility(layer.name, visible)
        self.layer_list.blockSignals(False)
        has_layers = self.reference_2d is not None and self.layer_list.count() > 0
        self.layer_select_all_button.setEnabled(has_layers)
        self.layer_select_none_button.setEnabled(has_layers)

    def _layer_item_changed(self, item: QListWidgetItem) -> None:
        self.reference_viewer.set_layer_visibility(item.text(), item.checkState() == Qt.Checked)

    def _set_all_layers_visible(self, visible: bool) -> None:
        self.layer_list.blockSignals(True)
        try:
            for index in range(self.layer_list.count()):
                item = self.layer_list.item(index)
                if item is not None:
                    item.setCheckState(Qt.Checked if visible else Qt.Unchecked)
                    self.reference_viewer.set_layer_visibility(item.text(), visible)
        finally:
            self.layer_list.blockSignals(False)

    def _sync_reference_mode(self) -> None:
        if self.project.reference_type == "dxf" or self.reference_3d is None:
            self.reference_stack.setCurrentWidget(self.reference_viewer)
            self.layer_box.show()
            self.action_reference_roi.setVisible(True)
            self.action_fit_reference_view.setVisible(True)
            self.action_fit_reference_roi_view.setVisible(True)
            self.action_define_plane_from_points.setVisible(False)
            self.action_define_plane_auto.setVisible(False)
            self.workflow_label.setText(
                "Workflow: click image point, then matching DXF reference point"
            )
        else:
            self.reference_stack.setCurrentWidget(self.reference3d_viewer)
            self.layer_box.hide()
            self.action_reference_roi.setVisible(False)
            self.action_fit_reference_view.setVisible(False)
            self.action_fit_reference_roi_view.setVisible(False)
            self.action_define_plane_from_points.setVisible(True)
            self.action_define_plane_auto.setVisible(True)
            if self.reference_3d.working_plane is None:
                self.workflow_label.setText(
                    "Workflow: define a working plane, then click image and 3D reference points"
                )
            else:
                self.workflow_label.setText(
                    "Workflow: click image point, then matching 3D reference point on the plane"
                )

    def _update_3d_actions(self) -> None:
        enabled = self.reference_3d is not None
        self.action_define_plane_from_points.setEnabled(enabled)
        self.action_define_plane_auto.setEnabled(enabled)
        self.action_lens_correction.setEnabled(self.source_image_original is not None)
        self.action_image_roi.setEnabled(self.source_image is not None)
        self.action_fit_image_view.setEnabled(self.source_image is not None)
        self.action_reference_roi.setEnabled(self.reference_2d is not None)
        self.action_fit_reference_view.setEnabled(self.reference_2d is not None)
        self.action_fit_reference_roi_view.setEnabled(
            self.reference_2d is not None and self.project.reference_roi is not None
        )

    def _export_action_state(self) -> tuple[bool, str]:
        self.project.ensure_image_entries()
        if not any(entry.path for entry in self.project.images):
            return False, "Export requires at least one loaded image."
        if not self.project.reference_path:
            return False, "Export requires a loaded reference."
        for entry in self.project.images:
            if not entry.path:
                continue
            paired_points = [point for point in entry.points if point.is_enabled_pair]
            if len(paired_points) < 4:
                continue
            try:
                self._homography_for_entry(entry)
            except Exception:
                continue
            image_path = self.project.resolve_image_entry_path(entry)
            if image_path is not None and image_path.exists():
                return True, "Export the rectified image or mosaic."
        return (
            False,
            "Export requires at least one image with four paired points and a solved homography.",
        )

    def _update_export_action(self) -> None:
        enabled, description = self._export_action_state()
        self.action_export.setEnabled(enabled)
        self.action_export.setStatusTip(description)
        self.action_export.setToolTip(description)

    def _show_dwg_help_dialog(self) -> None:
        QMessageBox.information(
            self,
            "DWG Format Not Supported Directly",
            "DWG files cannot be loaded directly (proprietary format).\n\n"
            "Convert your DWG to DXF first using one of these tools:\n"
            "• CloudConvert (cloudconvert.com/dwg-to-dxf) — online, no registration\n"
            "• FreeCAD (freecadweb.org) — free, cross-platform\n"
            "• AutoCAD Web (web.autocad.com) — free with Autodesk account\n\n"
            'When saving as DXF, choose "AutoCAD 2013" or newer for best compatibility.',
        )

    def _show_cursor_message(self, message: str) -> None:
        self.statusBar().showMessage(f"{message} — {self._mode_hint_text()}")

    def _mode_hint_text(self) -> str:
        mode_hints = {
            "view": "Middle-drag: pan | Scroll: zoom | Ctrl+Click: place point",
            "clip_polygon": "Click: add vertex | Double-click: close | Esc: cancel",
            "reference_roi": "Drag: define region | Esc: cancel",
        }
        return mode_hints.get(self._current_mode, mode_hints["view"])

    def _toggle_clip_polygon_mode(self, checked: bool) -> None:
        if checked and self.action_reference_roi.isChecked():
            self.action_reference_roi.setChecked(False)
        self._current_mode = "clip_polygon" if checked else "view"
        self.image_viewer.set_clip_polygon_mode(checked)
        if checked:
            self.statusBar().showMessage(self._mode_hint_text(), 5000)

    def _toggle_reference_roi_mode(self, checked: bool) -> None:
        if checked and self.action_image_roi.isChecked():
            self.action_image_roi.setChecked(False)
        self._current_mode = "reference_roi" if checked else "view"
        self.reference_viewer.set_reference_roi_mode(checked)
        if checked:
            self.statusBar().showMessage(self._mode_hint_text(), 5000)

    def _handle_clip_polygon_changed(self, polygon: object) -> None:
        if polygon is None:
            self.project.clip_polygon = None
        else:
            self.project.clip_polygon = _coerce_polygon(polygon)
        self.image_viewer.set_clip_polygon(self.project.clip_polygon)

    def _finish_clip_polygon_mode(self) -> None:
        if self.action_image_roi.isChecked():
            self.action_image_roi.setChecked(False)
        self._record_history()
        self._refresh_ui(status="Updated image ROI")

    def _handle_reference_roi_changed(self, roi: object) -> None:
        if roi is None:
            self.project.reference_roi = None
        else:
            self.project.reference_roi = _coerce_reference_roi(roi)
        self.reference_viewer.set_reference_roi(self.project.reference_roi)

    def _finish_reference_roi_mode(self) -> None:
        if self.action_reference_roi.isChecked():
            self.action_reference_roi.setChecked(False)
        self._record_history()
        self._refresh_ui(status="Updated DXF region")

    def _record_history(self) -> None:
        if self._restoring_history:
            return
        self.project.sync_to_active_image()
        snapshot = self.project.clone()
        self._history = self._history[: self._history_index + 1]
        self._history.append(snapshot)
        self._history_index += 1
        self._update_history_actions()

    def _reset_history(self) -> None:
        self._history = [self.project.clone()]
        self._history_index = 0
        self._update_history_actions()

    def _undo(self) -> None:
        if self._history_index > 0:
            self._restore_history_index(self._history_index - 1)

    def _redo(self) -> None:
        if self._history_index < len(self._history) - 1:
            self._restore_history_index(self._history_index + 1)

    def _restore_history_index(self, index: int) -> None:
        self._restoring_history = True
        try:
            self._history_index = index
            self.project = self._history[index].clone()
            self.selected_point_id = None
            self.pending_plane_points = []
            self.plane_pick_mode = False
            self._reload_assets_from_project()
            self._refresh_ui(status="Restored previous edit state")
        finally:
            self._restoring_history = False

    def _update_history_actions(self) -> None:
        self.action_undo.setEnabled(self._history_index > 0)
        self.action_redo.setEnabled(self._history_index < len(self._history) - 1)

    def _update_window_title(self) -> None:
        project_label = self.project_path.name if self.project_path else self.project.name
        self.setWindowTitle(f"ImageRect — Metric Image Rectification — {project_label}")

    def _refresh_project_panel_context(self) -> None:
        bounds = self._current_panel_bounds()
        self.project_panel.set_context(
            bounds,
            has_clip_polygon=bool(self.project.clip_polygon),
            has_reference_roi=bool(self.project.reference_roi),
            units_locked=self._locked_reference_units() is not None,
        )

    def _current_panel_bounds(self) -> tuple[Point2D, Point2D] | None:
        if (
            self.project.export_settings.use_reference_roi
            and self.project.reference_roi is not None
        ):
            x0, y0, x1, y1 = self.project.reference_roi
            return (min(x0, x1), min(y0, y1)), (max(x0, x1), max(y0, y1))
        try:
            return self._current_reference_extents()
        except ValueError:
            return None

    def _confirm_export_preview(self) -> bool:
        self.project.sync_to_active_image()
        sources, preview_warnings = self._collect_export_sources()
        total_point_count = self._total_project_point_count()

        if len(sources) > 1:
            preview = PreviewDialog(
                export_settings=self.project.export_settings,
                units=self.project.units,
                project_name=self.project.name,
                total_point_count=total_point_count,
                reference_extents=self._current_reference_extents(),
                rms_error=None,
                warnings=preview_warnings,
                reference_2d=self.reference_2d,
                reference_roi=self.project.reference_roi,
                mosaic_sources=sources,
                parent=self,
            )
            return bool(preview.exec())

        source = sources[0]
        preview = PreviewDialog(
            export_settings=self.project.export_settings,
            units=self.project.units,
            project_name=self.project.name,
            total_point_count=total_point_count,
            reference_extents=self._current_reference_extents(),
            source_image=source.source_image,
            homography_image_to_reference=source.homography_image_to_reference,
            control_points=source.control_points,
            rms_error=source.rms_error,
            warnings=list(dict.fromkeys([*preview_warnings, *source.warnings])),
            reference_2d=self.reference_2d,
            clip_polygon=source.clip_polygon,
            reference_roi=self.project.reference_roi,
            parent=self,
        )
        return bool(preview.exec())

    def _point_pick_tolerance(self) -> float:
        if self.reference_3d is None:
            return 0.0
        source_points = reference_source_points(self.reference_3d)
        if source_points is None or len(source_points) == 0:
            return 0.0
        bounds_min = source_points.min(axis=0)
        bounds_max = source_points.max(axis=0)
        span = np.linalg.norm(bounds_max - bounds_min)
        return max(float(span) * 0.02, 1e-6)

    def _current_lens_profile(self) -> LensProfile | None:
        return self._lens_profile_from_correction(self.project.lens_correction)

    def _refresh_source_image(self) -> None:
        if self.source_image_original is None:
            self.source_image = None
            return

        profile = self._current_lens_profile()
        if profile is None:
            self.source_image = self.source_image_original.copy()
            return

        corrected = apply_lens_correction(self.source_image_original, profile)
        mean_abs_delta = float(
            np.abs(corrected.astype(np.int16) - self.source_image_original.astype(np.int16)).mean()
        )
        logger.debug(
            "Refreshed source image with lens correction | profile=%s | mean_abs_delta=%.4f",
            profile.name,
            mean_abs_delta,
        )
        self.source_image = corrected

    def _safe_plane_extents(self) -> tuple[tuple[float, float], tuple[float, float]] | None:
        if self.reference_3d is None or self.reference_3d.working_plane is None:
            return None
        try:
            return reference_plane_extents(self.reference_3d)
        except Exception:
            return None

    def _current_reference_extents(self) -> tuple[tuple[float, float], tuple[float, float]]:
        if self.reference_2d is not None:
            return self.reference_2d.extents_min, self.reference_2d.extents_max
        if self.reference_3d is not None and self.reference_3d.working_plane is not None:
            try:
                return reference_plane_extents(self.reference_3d)
            except Exception as exc:
                logger.warning("Falling back to paired-point extents | error=%s", exc)
        paired_points = self.project.paired_points()
        if not paired_points:
            raise ValueError("No reference extents available for export.")
        reference_xy = np.asarray(
            [point.reference_xy for point in paired_points if point.reference_xy is not None],
            dtype=np.float64,
        )
        mins = reference_xy.min(axis=0)
        maxs = reference_xy.max(axis=0)
        return (float(mins[0]), float(mins[1])), (float(maxs[0]), float(maxs[1]))


def _coerce_polygon(raw: object) -> list[Point2D]:
    if not isinstance(raw, list | tuple):
        raise TypeError("clip polygon must be a list of 2D points")

    polygon: list[Point2D] = []
    for point in raw:
        if not isinstance(point, list | tuple) or len(point) != 2:
            raise TypeError("clip polygon points must contain exactly two coordinates")
        polygon.append((float(point[0]), float(point[1])))
    return polygon


def _coerce_reference_roi(raw: object) -> ReferenceRoi:
    if not isinstance(raw, list | tuple) or len(raw) != 4:
        raise TypeError("reference ROI must contain exactly four coordinates")
    return (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))
