from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import tifffile

from core.export import (
    MosaicSource,
    export_mosaic_image,
    export_rectified_image,
    render_rectified_image,
)
from core.project import ControlPoint
from core.transform import solve_planar_homography


def test_bigtiff_export_over_4gb_threshold(tmp_path: Path) -> None:
    source, control_points, matrix = _identity_case()

    export = export_rectified_image(
        source_image=source,
        homography_image_to_reference=matrix,
        control_points=control_points,
        output_path=tmp_path / "tiny_bigtiff",
        pixel_size=1.0,
        units="mm",
        output_format="tiff",
        bigtiff_threshold_bytes=1,
        reference_extents=((0.0, 0.0), (63.0, 63.0)),
    )

    metadata = json.loads(export.metadata_path.read_text(encoding="utf-8"))
    assert metadata["bigtiff"] is True
    assert export.image_path.exists()


def test_tiled_export_for_large_canvas(tmp_path: Path) -> None:
    source, control_points, matrix = _identity_case()

    export = export_rectified_image(
        source_image=source,
        homography_image_to_reference=matrix,
        control_points=control_points,
        output_path=tmp_path / "tiled",
        pixel_size=1.0,
        units="mm",
        output_format="tiff",
        tile_size=32,
        tile_trigger_size=32,
        reference_extents=((0.0, 0.0), (127.0, 127.0)),
    )

    metadata = json.loads(export.metadata_path.read_text(encoding="utf-8"))
    assert metadata["tiled_export"] is True
    assert export.image_path.exists()


def test_multilayer_tiff_has_expected_pages(tmp_path: Path) -> None:
    source, control_points, matrix = _identity_case()
    reference_segments = [
        ((0.0, 0.0), (63.0, 0.0)),
        ((63.0, 0.0), (63.0, 63.0)),
    ]

    export = export_rectified_image(
        source_image=source,
        homography_image_to_reference=matrix,
        control_points=control_points,
        output_path=tmp_path / "multilayer",
        pixel_size=1.0,
        units="mm",
        output_format="tiff",
        multi_layer=True,
        clip_polygon=[(0.0, 0.0), (40.0, 0.0), (40.0, 63.0), (0.0, 63.0)],
        reference_extents=((0.0, 0.0), (63.0, 63.0)),
        reference_segments=reference_segments,
    )

    with tifffile.TiffFile(export.image_path) as handle:
        assert len(handle.pages) == 4
        descriptions = [json.loads(str(page.description)) for page in handle.pages]

    assert descriptions[0]["layer_name"] == "rectified_image"
    assert descriptions[1]["layer_name"] == "dxf_overlay"
    assert descriptions[2]["layer_name"] == "control_points"
    assert descriptions[3]["layer_name"] == "clip_mask"


def test_16bit_export_preserves_precision(tmp_path: Path) -> None:
    gradient = np.linspace(0, 65535, 64, dtype=np.uint16)
    source = np.dstack(
        [
            np.tile(gradient, (64, 1)),
            np.tile(gradient, (64, 1)),
            np.tile(gradient, (64, 1)),
        ]
    )
    control_points, matrix = _identity_points_for_size(64, 64)

    export = export_rectified_image(
        source_image=source,
        homography_image_to_reference=matrix,
        control_points=control_points,
        output_path=tmp_path / "gradient16",
        pixel_size=1.0,
        units="mm",
        output_format="png",
        bit_depth=16,
        reference_extents=((0.0, 0.0), (63.0, 63.0)),
    )

    exported = cv2.imread(str(export.image_path), cv2.IMREAD_UNCHANGED)
    assert exported is not None
    assert exported.dtype == np.uint16
    assert int(exported.max()) > 255


def test_bit_depth_conversions() -> None:
    source, control_points, matrix = _identity_case()

    rendered_16 = render_rectified_image(
        source_image=source,
        homography_image_to_reference=matrix,
        control_points=control_points,
        pixel_size=1.0,
        units="mm",
        bit_depth=16,
        reference_extents=((0.0, 0.0), (63.0, 63.0)),
    )
    rendered_32 = render_rectified_image(
        source_image=source,
        homography_image_to_reference=matrix,
        control_points=control_points,
        pixel_size=1.0,
        units="mm",
        bit_depth=32,
        reference_extents=((0.0, 0.0), (63.0, 63.0)),
    )

    assert rendered_16.image.dtype == np.uint16
    assert int(rendered_16.image.max()) > 255
    assert rendered_32.image.dtype == np.float32
    assert float(rendered_32.image.max()) <= 1.0


def test_mosaic_export_cleans_up_partial_output_on_metadata_failure(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source, control_points, matrix = _identity_case()
    mosaic_source = MosaicSource(
        label="source",
        source_image=source,
        homography_image_to_reference=matrix,
        control_points=control_points,
    )

    def fail_write_text(self: Path, *args, **kwargs) -> int:
        raise OSError("metadata boom")

    monkeypatch.setattr(Path, "write_text", fail_write_text)

    with pytest.raises(OSError, match="metadata boom"):
        export_mosaic_image(
            sources=[mosaic_source],
            output_path=tmp_path / "mosaic",
            pixel_size=1.0,
            units="mm",
            output_format="png",
            reference_extents=((0.0, 0.0), (63.0, 63.0)),
        )

    assert not (tmp_path / "mosaic.png").exists()
    assert not (tmp_path / "mosaic.json").exists()


def _identity_case() -> tuple[np.ndarray, list[ControlPoint], np.ndarray]:
    source = np.zeros((64, 64, 3), dtype=np.uint8)
    source[:, :, 2] = 255
    control_points, matrix = _identity_points_for_size(64, 64)
    return source, control_points, matrix


def _identity_points_for_size(
    width: int,
    height: int,
) -> tuple[list[ControlPoint], np.ndarray]:
    max_x = float(width - 1)
    max_y = float(height - 1)
    image_points = [(0.0, 0.0), (max_x, 0.0), (max_x, max_y), (0.0, max_y)]
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
