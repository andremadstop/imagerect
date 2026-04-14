from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtCore import Qt

from core.reference2d import LayerInfo, Reference2D, Segment
from ui.image_viewer import ImageViewer
from ui.reference2d_viewer import Reference2DViewer


def test_plain_click_does_not_place_point(qtbot: Any) -> None:
    viewer = ImageViewer()
    viewer.resize(320, 240)
    viewer.set_image(_image())
    qtbot.addWidget(viewer)
    viewer.show()

    picked: list[tuple[float, float]] = []
    viewer.point_picked.connect(lambda x, y: picked.append((x, y)))

    qtbot.mouseClick(
        viewer.viewport(),
        Qt.LeftButton,
        Qt.NoModifier,
        pos=viewer.viewport().rect().center(),
    )

    assert picked == []


def test_ctrl_click_places_point(qtbot: Any) -> None:
    viewer = ImageViewer()
    viewer.resize(320, 240)
    viewer.set_image(_image())
    qtbot.addWidget(viewer)
    viewer.show()

    picked: list[tuple[float, float]] = []
    viewer.point_picked.connect(lambda x, y: picked.append((x, y)))

    qtbot.mouseClick(
        viewer.viewport(),
        Qt.LeftButton,
        Qt.ControlModifier,
        pos=viewer.viewport().rect().center(),
    )

    assert len(picked) == 1


def test_shift_click_places_point(qtbot: Any) -> None:
    viewer = Reference2DViewer()
    viewer.resize(320, 240)
    viewer.set_reference(_reference())
    qtbot.addWidget(viewer)
    viewer.show()

    picked: list[tuple[float, float]] = []
    viewer.point_picked.connect(lambda x, y: picked.append((x, y)))

    qtbot.mouseClick(
        viewer.viewport(),
        Qt.LeftButton,
        Qt.ShiftModifier,
        pos=viewer.viewport().rect().center(),
    )

    assert len(picked) == 1


def _image() -> np.ndarray:
    return np.zeros((100, 100, 3), dtype=np.uint8)


def _reference() -> Reference2D:
    return Reference2D(
        layers=[LayerInfo(name="0", color=7)],
        segments=[
            Segment((0.0, 0.0), (100.0, 0.0)),
            Segment((100.0, 0.0), (100.0, 100.0)),
            Segment((100.0, 100.0), (0.0, 100.0)),
            Segment((0.0, 100.0), (0.0, 0.0)),
        ],
        extents_min=(0.0, 0.0),
        extents_max=(100.0, 100.0),
        vertices=[(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)],
    )
