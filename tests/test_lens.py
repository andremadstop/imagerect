from __future__ import annotations

import cv2
import numpy as np
import pytest

from core.lens import (
    LensProfile,
    apply_lens_correction,
    build_camera_matrix,
    build_distortion_coefficients,
    load_presets,
    match_preset,
)


def test_build_camera_matrix_correctness() -> None:
    matrix = build_camera_matrix(
        focal_length_mm=24.0,
        sensor_width_mm=36.0,
        image_width_px=6000,
        image_height_px=4000,
    )

    assert matrix.shape == (3, 3)
    assert matrix[0, 0] == pytest.approx(4000.0)
    assert matrix[1, 1] == pytest.approx(4000.0)
    assert matrix[0, 2] == pytest.approx(3000.0)
    assert matrix[1, 2] == pytest.approx(2000.0)


def test_apply_lens_correction_roundtrip() -> None:
    profile = LensProfile(
        name="roundtrip",
        focal_length_mm=24.0,
        sensor_width_mm=36.0,
        k1=0.02,
    )
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.rectangle(image, (30, 30), (290, 210), (255, 255, 255), 3)
    cv2.line(image, (0, 120), (319, 120), (0, 255, 0), 2)
    cv2.line(image, (160, 0), (160, 239), (0, 0, 255), 2)

    camera_matrix = build_camera_matrix(24.0, 36.0, 320, 240)
    distortion = build_distortion_coefficients(profile)
    distorted = cv2.undistort(image, camera_matrix, -distortion, None, camera_matrix)
    corrected = apply_lens_correction(distorted, profile)

    difference = np.abs(corrected.astype(np.int16) - image.astype(np.int16))
    assert float(difference.mean()) < 12.0
    assert float(difference[120, :, 1].mean()) < 1.0
    assert float(difference[:, 160, 2].mean()) < 1.0


def test_load_presets_all_valid() -> None:
    presets = load_presets()

    assert presets
    assert len({preset.name for preset in presets}) == len(presets)
    assert all(preset.focal_length_mm > 0.0 for preset in presets)
    assert all(preset.sensor_width_mm > 0.0 for preset in presets)


def test_exif_match_preset_by_make_model() -> None:
    presets = load_presets()
    exif = {"Make": "DJI", "Model": "Mavic 3"}

    preset = match_preset(exif, presets)

    assert preset is not None
    assert preset.name == "DJI Mavic 3"
