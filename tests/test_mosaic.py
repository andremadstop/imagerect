from __future__ import annotations

import numpy as np

from core.export import MosaicSource, render_mosaic_image
from core.project import ControlPoint
from core.transform import solve_planar_homography


def test_mosaic_two_images_union_bounds() -> None:
    left = _mosaic_source(
        color=(0, 0, 255),
        reference_points=[(0.0, 0.0), (99.0, 0.0), (99.0, 99.0), (0.0, 99.0)],
    )
    right = _mosaic_source(
        color=(0, 255, 0),
        reference_points=[(100.0, 0.0), (199.0, 0.0), (199.0, 99.0), (100.0, 99.0)],
    )

    rendered = render_mosaic_image(
        sources=[left, right],
        pixel_size=1.0,
        units="mm",
    )

    assert rendered.width == 200
    assert rendered.height == 100
    assert tuple(rendered.image[50, 20]) == (0, 0, 255)
    assert tuple(rendered.image[50, 180]) == (0, 255, 0)


def test_mosaic_feather_blend_at_seam() -> None:
    left = _mosaic_source(
        color=(0, 0, 255),
        reference_points=[(0.0, 0.0), (119.0, 0.0), (119.0, 99.0), (0.0, 99.0)],
    )
    right = _mosaic_source(
        color=(0, 255, 0),
        reference_points=[(80.0, 0.0), (199.0, 0.0), (199.0, 99.0), (80.0, 99.0)],
    )

    rendered = render_mosaic_image(
        sources=[left, right],
        pixel_size=1.0,
        units="mm",
        blend_radius_px=24,
    )

    seam_pixel = rendered.image[50, 100]
    assert seam_pixel[1] > 0
    assert seam_pixel[2] > 0
    assert tuple(rendered.image[50, 20]) == (0, 0, 255)
    assert tuple(rendered.image[50, 180]) == (0, 255, 0)


def _mosaic_source(
    color: tuple[int, int, int],
    reference_points: list[tuple[float, float]],
) -> MosaicSource:
    image_points = [(0.0, 0.0), (99.0, 0.0), (99.0, 99.0), (0.0, 99.0)]
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
    source_image = np.zeros((100, 100, 3), dtype=np.uint8)
    source_image[:, :] = color
    return MosaicSource(
        label="source",
        source_image=source_image,
        homography_image_to_reference=result.matrix,
        control_points=control_points,
    )
