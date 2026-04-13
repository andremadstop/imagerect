from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from core.export import export_rectified_image
from core.project import ControlPoint
from core.transform import project_points, solve_planar_homography


def test_solve_planar_homography_reprojects_reference_points() -> None:
    image_points = [
        (120.0, 420.0),
        (620.0, 360.0),
        (560.0, 90.0),
        (170.0, 120.0),
    ]
    reference_points = [
        (0.0, 0.0),
        (400.0, 0.0),
        (400.0, 300.0),
        (0.0, 300.0),
    ]

    result = solve_planar_homography(image_points, reference_points)
    projected = project_points(image_points, result.matrix)

    assert result.rms_error < 1e-6
    assert np.allclose(projected, np.asarray(reference_points), atol=1e-4)


def test_export_rectified_image_writes_image_and_metadata(tmp_path: Path) -> None:
    source, _image_points, _reference_points, control_points, result = _synthetic_case()

    export = export_rectified_image(
        source_image=source,
        homography_image_to_reference=result.matrix,
        control_points=control_points,
        output_path=tmp_path / "synthetic_rectified",
        pixel_size=1.0,
        units="mm",
        output_format="png",
        resampling="bilinear",
        reference_extents=((0.0, 0.0), (400.0, 300.0)),
        project_name="synthetic",
        rms_error=result.rms_error,
        warnings=result.warnings,
    )

    assert export.image_path.exists()
    assert export.metadata_path.exists()
    exported = cv2.imread(str(export.image_path), cv2.IMREAD_UNCHANGED)
    assert exported is not None
    assert exported.shape[1] >= 401
    assert exported.shape[0] >= 301

    metadata = json.loads(export.metadata_path.read_text(encoding="utf-8"))
    assert metadata["units"] == "mm"
    assert metadata["pixel_size"] == 1.0
    assert len(metadata["point_pairs"]) == 4


def test_export_rectified_tiff_format(tmp_path: Path) -> None:
    source, _, _, control_points, result = _synthetic_case()

    export = export_rectified_image(
        source_image=source,
        homography_image_to_reference=result.matrix,
        control_points=control_points,
        output_path=tmp_path / "synthetic_rectified",
        pixel_size=1.0,
        units="mm",
        output_format="tiff",
        resampling="bilinear",
        reference_extents=((0.0, 0.0), (400.0, 300.0)),
        project_name="synthetic",
        rms_error=result.rms_error,
        warnings=result.warnings,
    )

    assert export.image_path.suffix == ".tiff"
    assert export.image_path.exists()
    assert export.metadata_path.exists()
    exported = cv2.imread(str(export.image_path), cv2.IMREAD_UNCHANGED)
    assert exported is not None

    metadata = json.loads(export.metadata_path.read_text(encoding="utf-8"))
    assert metadata["units"] == "mm"
    assert metadata["transform_matrix"]
    assert metadata["canvas"]["width"] >= 401


def test_homography_with_outlier() -> None:
    reference_points = np.array(
        [
            (0.0, 0.0),
            (400.0, 0.0),
            (400.0, 300.0),
            (0.0, 300.0),
            (80.0, 60.0),
            (320.0, 70.0),
            (120.0, 240.0),
            (290.0, 210.0),
        ],
        dtype=np.float32,
    )
    reference_corners = reference_points[:4]
    image_corners = np.array(
        [(120.0, 420.0), (620.0, 360.0), (560.0, 90.0), (170.0, 120.0)],
        dtype=np.float32,
    )
    homography_ref_to_image = cv2.getPerspectiveTransform(reference_corners, image_corners)
    image_points = cv2.perspectiveTransform(
        reference_points.reshape(-1, 1, 2),
        homography_ref_to_image,
    ).reshape(-1, 2)
    image_points[6] = (40.0, 40.0)
    image_points[7] = (700.0, 490.0)

    result = solve_planar_homography(
        image_points.tolist(),
        reference_points.tolist(),
        ransac_threshold=2.0,
        rms_warning_threshold=50.0,
    )

    assert result.inlier_mask[6] is False
    assert result.inlier_mask[7] is False
    assert any("outlier" in warning.lower() for warning in result.warnings)

    inlier_residuals = [
        residual
        for residual, is_inlier in zip(result.residuals, result.inlier_mask, strict=True)
        if is_inlier
    ]
    assert inlier_residuals
    assert max(inlier_residuals) < 1.0


def test_homography_too_few_points() -> None:
    with pytest.raises(ValueError, match=r"few|four"):
        solve_planar_homography(
            [(10.0, 10.0), (20.0, 20.0)],
            [(0.0, 0.0), (100.0, 100.0)],
        )


def test_homography_collinear_points() -> None:
    with pytest.raises(ValueError, match="collinear"):
        solve_planar_homography(
            [(0.0, 0.0), (100.0, 0.0), (200.0, 0.0), (300.0, 0.0), (400.0, 0.0)],
            [(0.0, 0.0), (50.0, 0.0), (100.0, 0.0), (150.0, 0.0), (200.0, 0.0)],
        )


def _synthetic_case() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[ControlPoint], object]:
    reference_points = np.array(
        [[0.0, 0.0], [400.0, 0.0], [400.0, 300.0], [0.0, 300.0]],
        dtype=np.float32,
    )
    image_points = np.array(
        [[120.0, 420.0], [620.0, 360.0], [560.0, 90.0], [170.0, 120.0]],
        dtype=np.float32,
    )
    plane = np.zeros((301, 401, 3), dtype=np.uint8)
    plane[:] = (240, 240, 240)
    cv2.rectangle(plane, (0, 0), (400, 300), (20, 20, 20), 3)
    cv2.line(plane, (0, 150), (400, 150), (0, 0, 255), 2)
    cv2.putText(plane, "IR", (160, 170), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (10, 10, 10), 3)

    source = np.zeros((520, 760, 3), dtype=np.uint8)
    homography_ref_to_image = cv2.getPerspectiveTransform(reference_points, image_points)
    cv2.warpPerspective(
        plane,
        homography_ref_to_image,
        (760, 520),
        dst=source,
        borderMode=cv2.BORDER_TRANSPARENT,
    )

    result = solve_planar_homography(image_points.tolist(), reference_points.tolist())
    control_points = [
        ControlPoint(
            id=index + 1,
            label=f"P{index + 1}",
            image_xy=(float(image_xy[0]), float(image_xy[1])),
            reference_xy=(float(reference_xy[0]), float(reference_xy[1])),
            residual=result.residuals[index],
            residual_vector=result.residual_vectors[index],
        )
        for index, (image_xy, reference_xy) in enumerate(
            zip(image_points.tolist(), reference_points.tolist(), strict=True)
        )
    ]
    return source, image_points, reference_points, control_points, result
