from __future__ import annotations

from pathlib import Path
from typing import Any

from core.project import ImageEntry
from ui.workspace_controller import WorkspaceController


def test_project_hub_updates_from_shared_project_state(qtbot: Any) -> None:
    controller = WorkspaceController()
    qtbot.addWidget(controller.project_hub)
    qtbot.addWidget(controller.rectify_window)
    qtbot.addWidget(controller.three_d_window)
    qtbot.addWidget(controller.review_window)

    controller.rectify_window.project.name = "Demo"
    controller.rectify_window.project.reference_path = "/tmp/reference.dxf"
    controller.rectify_window.project.reference_type = "dxf"
    controller.rectify_window.project.images = [ImageEntry(path="/tmp/source.png")]
    controller.rectify_window.project.active_image_index = 0
    controller.rectify_window.project.sync_from_active_image()
    controller.rectify_window._refresh_ui()

    assert controller.project_hub.project_name_label.text() == "Demo"
    assert "reference.dxf" in controller.project_hub.reference_label.text()
    assert controller.project_hub.images_list.count() == 1
    assert controller.review_window.project_label.text() == "Demo"


def test_project_hub_workspace_buttons_remain_available_without_reference(qtbot: Any) -> None:
    controller = WorkspaceController()
    qtbot.addWidget(controller.project_hub)

    controller.project_hub.update_summary(
        {
            "name": "Untitled",
            "image_count": 0,
            "active_image": "keines",
            "paired_point_count": 0,
            "dirty": False,
            "reference_name": "keine",
            "reference_type": "dxf",
            "last_export_path": "",
            "export_ready": False,
            "images": [],
        }
    )

    assert controller.project_hub.open_rectify_button.isEnabled() is True
    assert controller.project_hub.open_three_d_button.isEnabled() is True
    assert controller.project_hub.open_review_button.isEnabled() is True


def test_last_window_close_uses_shared_unsaved_changes_prompt(monkeypatch: Any, qtbot: Any) -> None:
    controller = WorkspaceController()
    qtbot.addWidget(controller.project_hub)
    qtbot.addWidget(controller.rectify_window)
    qtbot.addWidget(controller.three_d_window)
    qtbot.addWidget(controller.review_window)

    prompts: list[str] = []
    monkeypatch.setattr(
        controller.rectify_window,
        "confirm_close_with_unsaved_changes",
        lambda: prompts.append("asked") or False,
    )

    controller.project_hub.show()
    controller.rectify_window.hide()
    controller.three_d_window.hide()
    controller.review_window.hide()

    assert controller._handle_window_close(controller.project_hub) is False
    assert prompts == ["asked"]

    controller.rectify_window.show()
    assert controller._handle_window_close(controller.project_hub) is True
    assert prompts == ["asked"]


def test_recent_projects_are_listed_in_project_hub(qtbot: Any, tmp_path: Path) -> None:
    controller = WorkspaceController()
    qtbot.addWidget(controller.project_hub)

    first = tmp_path / "first.imagerect.json"
    second = tmp_path / "second.imagerect.json"
    first.write_text("{}", encoding="utf-8")
    second.write_text("{}", encoding="utf-8")

    controller.project_hub.set_recent_projects([first, second])

    assert controller.project_hub.recent_projects.count() == 2
    assert controller.project_hub.recent_projects.item(0).toolTip() == str(first)
