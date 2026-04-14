from __future__ import annotations

from typing import Any

import pytest

from core.project import ProjectData
from ui.project_panel import ProjectPanel


def test_scale_dpi_pixel_size_linked(qtbot: Any) -> None:
    panel = ProjectPanel()
    qtbot.addWidget(panel)
    panel.set_project(ProjectData())

    panel.scale.setCurrentIndex(panel.scale.count() - 1)
    panel.scale_custom.setValue(100.0)
    panel.dpi.setValue(200.0)

    assert panel.pixel_size.value() == pytest.approx((100.0 * 25.4) / 200.0)

    panel.pixel_size.setValue(6.35)

    assert panel.scale_custom.value() == pytest.approx((6.35 * 200.0) / 25.4)


def test_canvas_size_computation(qtbot: Any) -> None:
    panel = ProjectPanel()
    qtbot.addWidget(panel)
    panel.set_project(ProjectData())
    panel.set_context(
        reference_bounds=((0.0, 0.0), (100.0, 50.0)),
        has_clip_polygon=False,
        has_reference_roi=False,
    )

    assert "101 x 51 px" in panel.canvas_label.text()
    assert panel.file_size_label.text().startswith("File size: ~")


def test_units_can_be_locked_by_reference_context(qtbot: Any) -> None:
    panel = ProjectPanel()
    qtbot.addWidget(panel)
    panel.set_project(ProjectData())

    panel.set_context(
        reference_bounds=((0.0, 0.0), (100.0, 50.0)),
        has_clip_polygon=False,
        has_reference_roi=False,
        units_locked=True,
    )

    assert panel.units.isEnabled() is False
