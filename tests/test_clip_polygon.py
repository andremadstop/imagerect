from __future__ import annotations

import numpy as np

from core.export import render_rectified_image
from core.project import ControlPoint
from core.transform import solve_planar_homography


def test_clip_polygon_masks_outside_region() -> None:
    source = np.full((100, 100, 3), 255, dtype=np.uint8)
    control_points, matrix = _identity_case()

    rendered = render_rectified_image(
        source_image=source,
        homography_image_to_reference=matrix,
        control_points=control_points,
        pixel_size=1.0,
        units="mm",
        clip_polygon=[(0.0, 0.0), (49.0, 0.0), (49.0, 99.0), (0.0, 99.0)],
        reference_extents=((0.0, 0.0), (99.0, 99.0)),
    )

    assert np.any(rendered.image[:, :40] != 0)
    assert np.all(rendered.image[:, 60:] == 0)


def test_reference_roi_overrides_canvas_bounds() -> None:
    source = np.full((100, 100, 3), 255, dtype=np.uint8)
    control_points, matrix = _identity_case()

    rendered = render_rectified_image(
        source_image=source,
        homography_image_to_reference=matrix,
        control_points=control_points,
        pixel_size=1.0,
        units="mm",
        reference_roi=(25.0, 25.0, 74.0, 74.0),
        reference_extents=((0.0, 0.0), (99.0, 99.0)),
    )

    assert rendered.width == 50
    assert rendered.height == 50
    assert rendered.bounds_min == (25.0, 25.0)
    assert rendered.bounds_max == (74.0, 74.0)


def test_both_clip_and_roi_combined() -> None:
    source = np.full((100, 100, 3), 255, dtype=np.uint8)
    control_points, matrix = _identity_case()

    rendered = render_rectified_image(
        source_image=source,
        homography_image_to_reference=matrix,
        control_points=control_points,
        pixel_size=1.0,
        units="mm",
        clip_polygon=[(0.0, 0.0), (49.0, 0.0), (49.0, 99.0), (0.0, 99.0)],
        reference_roi=(25.0, 25.0, 74.0, 74.0),
        reference_extents=((0.0, 0.0), (99.0, 99.0)),
    )

    assert rendered.width == 50
    assert np.any(rendered.image[:, :20] != 0)
    assert np.all(rendered.image[:, 30:] == 0)


def _identity_case() -> tuple[list[ControlPoint], np.ndarray]:
    image_points = [(0.0, 0.0), (99.0, 0.0), (99.0, 99.0), (0.0, 99.0)]
    reference_points = image_points
    result = solve_planar_homography(image_points, reference_points)
    control_points = [
        ControlPoint(
            id=index + 1,
            label=f"P{index + 1}",
            image_xy=image_xy,
            reference_xy=reference_xy,
        )
        for index, (image_xy, reference_xy) in enumerate(
            zip(image_points, reference_points, strict=True)
        )
    ]
    return control_points, result.matrix
