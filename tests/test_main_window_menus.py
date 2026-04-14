from __future__ import annotations

from typing import Any

from core.reference2d import LayerInfo, Reference2D, Segment
from ui.main_window import MainWindow


def test_help_menu_contains_diagnose_actions(qtbot: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    menu_titles = [action.text() for action in window.menuBar().actions()]

    assert "Hilfe" in menu_titles
    assert window.action_open_log_directory.text() == "Log-Ordner öffnen"
    assert window.action_export_diagnose_package.text() == "Diagnose-Paket exportieren..."


def test_view_menu_contains_fit_actions(qtbot: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    menu_titles = [action.text() for action in window.menuBar().actions()]

    assert "Ansicht" in menu_titles
    assert window.action_fit_reference_view.text() == "An DXF anpassen"
    assert window.action_fit_reference_view.shortcut().toString() == "Ctrl+0"
    assert window.action_fit_reference_roi_view.text() == "An ROI anpassen"
    assert window.action_fit_reference_roi_view.shortcut().toString() == "Ctrl+Shift+0"
    assert window.action_fit_image_view.text() == "Bild anpassen"
    assert window.action_fit_image_view.shortcut().toString() == "Ctrl+1"


def test_fit_to_dxf_calls_viewer_method(monkeypatch: Any, qtbot: Any) -> None:
    fit_calls: list[str] = []
    monkeypatch.setattr(
        "ui.reference2d_viewer.Reference2DViewer.fit_reference_to_view",
        lambda self: fit_calls.append("dxf"),
    )

    window = MainWindow()
    qtbot.addWidget(window)
    window.reference_2d = _reference()
    window._refresh_ui()
    window.action_fit_reference_view.trigger()

    assert fit_calls == ["dxf"]


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
