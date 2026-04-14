from __future__ import annotations

from typing import Any

import pytest

from core.reference2d import LayerInfo, Reference2D, Segment
from ui.reference2d_viewer import Reference2DViewer


def test_set_reference_same_object_preserves_transform(qtbot: Any) -> None:
    reference = _reference(100.0, 100.0)
    viewer = _viewer(qtbot)
    viewer.set_reference(reference)
    viewer.scale(2.0, 2.0)
    before = viewer.transform().m11()

    viewer.set_reference(reference)

    assert viewer.transform().m11() == pytest.approx(before)


def test_set_reference_different_object_resets_transform(qtbot: Any) -> None:
    viewer = _viewer(qtbot)
    viewer.set_reference(_reference(100.0, 100.0))
    viewer.scale(2.0, 2.0)
    before = viewer.transform().m11()

    updated = _reference(400.0, 100.0)
    viewer.set_reference(updated)

    fresh_viewer = _viewer(qtbot)
    fresh_viewer.set_reference(updated)

    assert viewer.transform().m11() != pytest.approx(before)
    assert viewer.transform().m11() == pytest.approx(fresh_viewer.transform().m11())


def test_set_reference_none_clears_but_keeps_view(qtbot: Any) -> None:
    viewer = _viewer(qtbot)
    viewer.set_reference(_reference(100.0, 100.0))
    viewer.scale(2.0, 2.0)
    before = viewer.transform().m11()

    viewer.set_reference(None)

    assert viewer.transform().m11() == pytest.approx(before)
    assert viewer.scene().items() == []


def test_first_roi_triggers_autozoom(monkeypatch: Any, qtbot: Any) -> None:
    reference = _reference(100.0, 100.0)
    viewer = _viewer(qtbot)
    viewer.set_reference(reference)

    fit_calls: list[object] = []

    def record_fit_in_view(self: Reference2DViewer, *args: object) -> None:
        fit_calls.append(args)

    monkeypatch.setattr(Reference2DViewer, "fitInView", record_fit_in_view)

    viewer.set_reference_roi_mode(True)
    viewer.set_reference_roi((10.0, 10.0, 60.0, 60.0))

    assert fit_calls == []

    viewer.set_reference_roi_mode(False)
    viewer.set_reference(reference)

    assert len(fit_calls) == 1

    viewer.set_reference_roi((20.0, 20.0, 50.0, 50.0))
    viewer.set_reference(reference)

    assert len(fit_calls) == 1


def _viewer(qtbot: Any) -> Reference2DViewer:
    viewer = Reference2DViewer()
    viewer.resize(640, 480)
    qtbot.addWidget(viewer)
    viewer.show()
    return viewer


def _reference(width: float, height: float) -> Reference2D:
    return Reference2D(
        layers=[LayerInfo(name="0", color=7)],
        segments=[
            Segment((0.0, 0.0), (width, 0.0)),
            Segment((width, 0.0), (width, height)),
            Segment((width, height), (0.0, height)),
            Segment((0.0, height), (0.0, 0.0)),
        ],
        extents_min=(0.0, 0.0),
        extents_max=(width, height),
        vertices=[(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)],
    )
