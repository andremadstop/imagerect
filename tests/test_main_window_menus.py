from __future__ import annotations

from typing import Any

from ui.main_window import MainWindow


def test_help_menu_contains_diagnose_actions(qtbot: Any) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    menu_titles = [action.text() for action in window.menuBar().actions()]

    assert "Hilfe" in menu_titles
    assert window.action_open_log_directory.text() == "Log-Ordner öffnen"
    assert window.action_export_diagnose_package.text() == "Diagnose-Paket exportieren..."
