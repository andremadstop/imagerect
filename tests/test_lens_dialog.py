from __future__ import annotations

from typing import Any

import numpy as np

from core.lens import LensProfile
from ui.lens_dialog import LensDialog


def test_preview_fires_on_spinbox_change(
    monkeypatch: Any,
    qtbot: Any,
) -> None:
    preview_calls: list[str] = []

    def fake_apply(image: np.ndarray, profile: LensProfile) -> np.ndarray:
        preview_calls.append(profile.name)
        return image.copy()

    monkeypatch.setattr("ui.lens_dialog.apply_lens_correction", fake_apply)

    dialog = LensDialog(image=_preview_image(), image_path=None)
    qtbot.addWidget(dialog)
    dialog.show()
    preview_calls.clear()

    dialog.k1.setValue(-0.2)
    qtbot.wait(150)

    assert len(preview_calls) == 1


def test_preview_debounces_rapid_changes(
    monkeypatch: Any,
    qtbot: Any,
) -> None:
    preview_calls: list[str] = []

    def fake_apply(image: np.ndarray, profile: LensProfile) -> np.ndarray:
        preview_calls.append(profile.name)
        return image.copy()

    monkeypatch.setattr("ui.lens_dialog.apply_lens_correction", fake_apply)

    dialog = LensDialog(image=_preview_image(), image_path=None)
    qtbot.addWidget(dialog)
    dialog.show()
    preview_calls.clear()

    dialog.k1.setValue(-0.02)
    dialog.k1.setValue(-0.04)
    dialog.k1.setValue(-0.06)
    dialog.k1.setValue(-0.08)
    dialog.k1.setValue(-0.10)
    qtbot.wait(150)

    assert len(preview_calls) == 1


def _preview_image() -> np.ndarray:
    image = np.zeros((120, 180, 3), dtype=np.uint8)
    image[20:100, 30:150] = (255, 255, 255)
    return image
