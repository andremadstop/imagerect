from __future__ import annotations

from typing import Any

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
    remap_points_between_profiles,
)
from core.transform import solve_planar_homography
from ui.main_window import MainWindow


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


def test_lens_correction_remaps_control_points(qtbot: Any) -> None:
    profile = LensProfile(
        name="remap",
        focal_length_mm=24.0,
        sensor_width_mm=36.0,
        k1=-0.08,
        k2=0.01,
        p1=0.001,
        p2=-0.001,
    )
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    distorted_points = [
        (42.0, 36.0),
        (286.0, 44.0),
        (294.0, 206.0),
        (51.0, 198.0),
    ]
    reference_points = [
        (0.0, 0.0),
        (4.0, 0.0),
        (4.0, 3.0),
        (0.0, 3.0),
    ]

    camera_matrix = build_camera_matrix(24.0, 36.0, 320, 240)
    distortion = build_distortion_coefficients(profile)
    new_camera_matrix, _roi = cv2.getOptimalNewCameraMatrix(
        camera_matrix,
        distortion,
        (320, 240),
        0.0,
        (320, 240),
    )
    expected_corrected = cv2.undistortPoints(
        np.asarray(distorted_points, dtype=np.float64).reshape(-1, 1, 2),
        camera_matrix,
        distortion,
        P=new_camera_matrix,
    ).reshape(-1, 2)

    window = MainWindow()
    qtbot.addWidget(window)
    window.source_image_original = image
    for image_xy, reference_xy in zip(distorted_points, reference_points, strict=True):
        point = window.project.add_point()
        point.image_xy = image_xy
        point.reference_xy = reference_xy

    window._remap_active_image_geometry_for_lens_change(None, profile)

    remapped_points = [
        point.image_xy for point in window.project.points if point.image_xy is not None
    ]
    np.testing.assert_allclose(np.asarray(remapped_points), expected_corrected, atol=1e-6)

    restored_points = remap_points_between_profiles(
        remapped_points,
        (320, 240),
        profile,
        None,
    )
    np.testing.assert_allclose(np.asarray(restored_points), np.asarray(distorted_points), atol=1e-5)

    window._recompute_transform()

    assert window.transform_result is not None
    expected_result = solve_planar_homography(
        [(float(x), float(y)) for x, y in expected_corrected],
        reference_points,
    )
    np.testing.assert_allclose(
        np.asarray(window.transform_result.projected_reference_points),
        np.asarray(expected_result.projected_reference_points),
        atol=1e-6,
    )


def test_apply_lens_changes_source_image_pixels() -> None:
    profile = LensProfile(
        name="visible",
        focal_length_mm=24.0,
        sensor_width_mm=17.3,
        k1=-0.08,
        k2=0.01,
    )
    window = MainWindow()
    window.source_image_original = _structured_image()
    window.project.lens_correction = {"profile": profile.to_dict(), "applied": True}

    window._refresh_source_image()

    assert window.source_image is not None
    assert window.source_image is not window.source_image_original
    difference = np.abs(
        window.source_image.astype(np.int16) - window.source_image_original.astype(np.int16)
    )
    assert float(difference.mean()) > 0.5


def test_refresh_source_image_updates_viewer(qtbot: Any) -> None:
    profile = LensProfile(
        name="visible",
        focal_length_mm=24.0,
        sensor_width_mm=17.3,
        k1=-0.08,
        k2=0.01,
    )
    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(960, 720)
    window.source_image_original = _structured_image()
    window._refresh_source_image()
    window._refresh_ui()
    window.image_viewer.scale(1.4, 1.4)
    before_transform = window.image_viewer.transform().m11()
    before_pixmap_key = window.image_viewer._pixmap_item.pixmap().cacheKey()

    window.project.lens_correction = {"profile": profile.to_dict(), "applied": True}
    window._refresh_source_image()
    window._refresh_ui()

    after_transform = window.image_viewer.transform().m11()
    after_pixmap_key = window.image_viewer._pixmap_item.pixmap().cacheKey()

    assert after_pixmap_key != before_pixmap_key
    assert after_transform == pytest.approx(before_transform)


def test_open_lens_dialog_updates_project_and_viewer(
    monkeypatch: Any,
    qtbot: Any,
) -> None:
    profile = LensProfile(
        name="DJI Mavic 3",
        focal_length_mm=24.0,
        sensor_width_mm=17.3,
        k1=-0.08,
        k2=0.01,
    )
    window = MainWindow()
    qtbot.addWidget(window)
    window.source_image_original = _structured_image()
    window._refresh_source_image()
    window._refresh_ui()
    before_pixmap_key = window.image_viewer._pixmap_item.pixmap().cacheKey()

    class FakeLensDialog:
        def __init__(
            self,
            image: np.ndarray,
            image_path: object,
            current_profile: LensProfile | None,
            parent: object,
        ) -> None:
            self._profile = profile

        def exec(self) -> int:
            return 1

        def selected_profile(self) -> LensProfile:
            return self._profile

        def lens_correction_payload(self) -> dict[str, object]:
            return {"profile": self._profile.to_dict(), "applied": True}

    monkeypatch.setattr("ui.main_window.LensDialog", FakeLensDialog)

    window._open_lens_dialog()

    assert window.project.lens_correction == {"profile": profile.to_dict(), "applied": True}
    assert window.source_image is not None
    difference = np.abs(
        window.source_image.astype(np.int16) - window.source_image_original.astype(np.int16)
    )
    assert float(difference.mean()) > 0.5
    assert window.image_viewer._pixmap_item.pixmap().cacheKey() != before_pixmap_key


def _structured_image() -> np.ndarray:
    image = np.zeros((240, 320, 3), dtype=np.uint8)
    cv2.rectangle(image, (24, 24), (296, 216), (255, 255, 255), 3)
    cv2.line(image, (0, 120), (319, 120), (0, 255, 0), 2)
    cv2.line(image, (160, 0), (160, 239), (0, 0, 255), 2)
    return image
