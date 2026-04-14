from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

SYNTHETIC_DXF = Path(__file__).parent / "sample_data" / "synthetic_reference.dxf"


def test_modifier_click_places_control_point(main_window: Any, qtbot: Any, tmp_path: Path) -> None:
    image_path = _write_image(tmp_path / "source.png")
    main_window.load_image_file(image_path)
    main_window.load_reference_file(SYNTHETIC_DXF)

    qtbot.mouseClick(
        main_window.image_viewer.viewport(),
        Qt.LeftButton,
        Qt.ControlModifier,
        pos=main_window.image_viewer.viewport().rect().center(),
    )
    qtbot.mouseClick(
        main_window.reference_viewer.viewport(),
        Qt.LeftButton,
        Qt.ShiftModifier,
        pos=main_window.reference_viewer.viewport().rect().center(),
    )

    assert len(main_window.project.points) == 1
    assert main_window.project.points[0].image_xy is not None
    assert main_window.project.points[0].reference_xy is not None
    assert main_window.point_table.rowCount() == 1


def test_modifier_click_without_loaded_assets_does_nothing(main_window: Any, qtbot: Any) -> None:
    qtbot.mouseClick(
        main_window.image_viewer.viewport(),
        Qt.LeftButton,
        Qt.ControlModifier,
        pos=main_window.image_viewer.viewport().rect().center(),
    )
    qtbot.mouseClick(
        main_window.reference_viewer.viewport(),
        Qt.LeftButton,
        Qt.ShiftModifier,
        pos=main_window.reference_viewer.viewport().rect().center(),
    )

    assert main_window.project.points == []
    assert main_window.point_table.rowCount() == 0


def test_point_deletion_removes_from_table_and_views(
    main_window: Any,
    qtbot: Any,
    tmp_path: Path,
) -> None:
    image_path = _write_image(tmp_path / "source.png")
    main_window.load_image_file(image_path)
    main_window.load_reference_file(SYNTHETIC_DXF)
    _add_paired_point(main_window, qtbot)

    main_window.point_table.selectRow(0)
    main_window.action_delete_point.trigger()

    assert main_window.project.points == []
    assert main_window.point_table.rowCount() == 0
    assert main_window.image_viewer._points == []
    assert main_window.reference_viewer._points == []


def test_new_project_clears_state(main_window: Any, qtbot: Any, tmp_path: Path) -> None:
    image_path = _write_image(tmp_path / "source.png")
    main_window.load_image_file(image_path)
    main_window.load_reference_file(SYNTHETIC_DXF)
    _add_paired_point(main_window, qtbot)

    main_window._new_project()

    assert main_window.project.image_path == ""
    assert main_window.project.reference_path == ""
    assert main_window.project.points == []
    assert main_window.reference_2d is None
    assert main_window.source_image is None
    assert main_window.point_table.rowCount() == 0
    assert main_window.action_export.isEnabled() is False


def test_save_load_roundtrip_preserves_ui_state(
    main_window: Any,
    qtbot: Any,
    tmp_path: Path,
) -> None:
    image_path = _write_image(tmp_path / "source.png")
    main_window.load_image_file(image_path)
    main_window.load_reference_file(SYNTHETIC_DXF)
    _add_paired_point(main_window, qtbot)
    main_window.project.lens_correction = _lens_payload()
    main_window.project.export_settings.dpi = 150.0
    main_window.project.export_settings.pixel_size = 0.5

    project_path = tmp_path / "roundtrip.imagerect.json"
    main_window.save_project_file(project_path)
    main_window._new_project()
    main_window.load_project_file(project_path)

    assert main_window.project.resolve_active_image_path() == image_path
    assert main_window.project.resolve_reference_path() == SYNTHETIC_DXF.resolve()
    assert len(main_window.project.points) == 1
    assert main_window.project.points[0].image_xy is not None
    assert main_window.project.points[0].reference_xy is not None
    assert main_window.project.lens_correction == _lens_payload()
    assert main_window.project.export_settings.dpi == 150.0
    assert main_window.project.export_settings.pixel_size == 0.5


def test_export_is_blocked_without_homography(main_window: Any, tmp_path: Path) -> None:
    image_path = _write_image(tmp_path / "source.png")
    main_window.load_image_file(image_path)
    main_window.load_reference_file(SYNTHETIC_DXF)
    point = main_window.project.add_point("P1")
    point.image_xy = (20.0, 20.0)
    point.reference_xy = (0.0, 0.0)
    main_window._refresh_ui()

    assert main_window.action_export.isEnabled() is False
    assert "four paired points" in main_window.action_export.toolTip()


def test_export_enables_after_four_point_homography(main_window: Any, tmp_path: Path) -> None:
    image_path = _write_image(tmp_path / "source.png")
    main_window.load_image_file(image_path)
    main_window.load_reference_file(SYNTHETIC_DXF)
    for index, (image_xy, reference_xy) in enumerate(
        [
            ((20.0, 20.0), (0.0, 0.0)),
            ((180.0, 20.0), (400.0, 0.0)),
            ((180.0, 140.0), (400.0, 300.0)),
            ((20.0, 140.0), (0.0, 300.0)),
        ],
        start=1,
    ):
        point = main_window.project.add_point(f"P{index}")
        point.image_xy = image_xy
        point.reference_xy = reference_xy

    main_window._recompute_transform()
    main_window._refresh_ui()

    assert main_window.action_export.isEnabled() is True
    assert main_window.action_export.toolTip() == "Export the rectified image or mosaic."


def test_point_can_be_disabled_without_deleting(main_window: Any, tmp_path: Path) -> None:
    image_path = _write_image(tmp_path / "source.png")
    main_window.load_image_file(image_path)
    main_window.load_reference_file(SYNTHETIC_DXF)
    for index, (image_xy, reference_xy) in enumerate(
        [
            ((20.0, 20.0), (0.0, 0.0)),
            ((180.0, 20.0), (400.0, 0.0)),
            ((180.0, 140.0), (400.0, 300.0)),
            ((20.0, 140.0), (0.0, 300.0)),
        ],
        start=1,
    ):
        point = main_window.project.add_point(f"P{index}")
        point.image_xy = image_xy
        point.reference_xy = reference_xy

    main_window._recompute_transform()
    main_window._refresh_ui()
    assert main_window.action_export.isEnabled() is True

    active_item = main_window.point_table.item(0, 7)
    assert active_item is not None
    active_item.setCheckState(Qt.Unchecked)

    assert len(main_window.project.points) == 4
    assert main_window.project.points[0].enabled is False
    assert main_window.action_export.isEnabled() is False

    active_item = main_window.point_table.item(0, 7)
    assert active_item is not None
    active_item.setCheckState(Qt.Checked)

    assert main_window.project.points[0].enabled is True
    assert main_window.action_export.isEnabled() is True


def test_layer_buttons_toggle_all_visibility(main_window: Any, tmp_path: Path) -> None:
    image_path = _write_image(tmp_path / "source.png")
    main_window.load_image_file(image_path)
    main_window.load_reference_file(SYNTHETIC_DXF)

    main_window.layer_select_none_button.click()
    assert all(
        main_window.layer_list.item(index).checkState() == Qt.Unchecked
        for index in range(main_window.layer_list.count())
    )

    main_window.layer_select_all_button.click()
    assert all(
        main_window.layer_list.item(index).checkState() == Qt.Checked
        for index in range(main_window.layer_list.count())
    )


def test_all_main_actions_have_shortcuts_or_descriptions(main_window: Any) -> None:
    for action in _all_main_actions(main_window):
        assert action.shortcut().toString() or action.toolTip() or action.statusTip()


def _add_paired_point(main_window: Any, qtbot: Any) -> None:
    qtbot.mouseClick(
        main_window.image_viewer.viewport(),
        Qt.LeftButton,
        Qt.ControlModifier,
        pos=main_window.image_viewer.viewport().rect().center(),
    )
    qtbot.mouseClick(
        main_window.reference_viewer.viewport(),
        Qt.LeftButton,
        Qt.ShiftModifier,
        pos=main_window.reference_viewer.viewport().rect().center(),
    )


def _write_image(path: Path) -> Path:
    image = np.zeros((160, 200, 3), dtype=np.uint8)
    image[:] = (230, 230, 230)
    cv2.rectangle(image, (20, 20), (180, 140), (50, 50, 50), 2)
    if not cv2.imwrite(str(path), image):
        raise ValueError(f"Could not write test image: {path}")
    return path.resolve()


def _lens_payload() -> dict[str, object]:
    return {
        "applied": True,
        "profile": {
            "name": "Test Lens",
            "focal_length_mm": 24.0,
            "sensor_width_mm": 36.0,
            "k1": 0.0,
            "k2": 0.0,
            "p1": 0.0,
            "p2": 0.0,
            "k3": 0.0,
        },
    }


def _all_main_actions(main_window: Any) -> list[QAction]:
    return [
        main_window.action_new,
        main_window.action_open_project,
        main_window.action_save_project,
        main_window.action_save_project_as,
        main_window.action_load_image,
        main_window.action_lens_correction,
        main_window.action_load_reference,
        main_window.action_load_reference3d,
        main_window.action_image_roi,
        main_window.action_reference_roi,
        main_window.action_fit_reference_view,
        main_window.action_fit_reference_roi_view,
        main_window.action_fit_image_view,
        main_window.action_define_plane_from_points,
        main_window.action_define_plane_auto,
        main_window.action_export,
        main_window.action_toggle_project_panel,
        main_window.action_delete_point,
        main_window.action_move_up,
        main_window.action_move_down,
        main_window.action_undo,
        main_window.action_redo,
        main_window.action_open_log_directory,
        main_window.action_export_diagnose_package,
    ]
