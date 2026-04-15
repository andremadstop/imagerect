"""Offscreen smoke-test workflow for the desktop UI."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

from core.export import RectificationExportResult, export_rectified_image
from core.project import ProjectData

if TYPE_CHECKING:
    from ui.main_window import MainWindow


def run_synthetic_smoke_test(window: MainWindow, output_root: Path) -> RectificationExportResult:
    """Exercise the window, solver, and export path with synthetic data."""

    reference_path = (
        Path(__file__).resolve().parent.parent / "tests" / "sample_data" / "synthetic_reference.dxf"
    )
    output_root.mkdir(parents=True, exist_ok=True)
    source_path = output_root / "synthetic_source.png"
    plane = np.zeros((301, 401, 3), dtype=np.uint8)
    plane[:] = (238, 238, 238)
    cv2.rectangle(plane, (0, 0), (400, 300), (20, 20, 20), 3)
    cv2.line(plane, (0, 150), (400, 150), (40, 140, 220), 2)
    cv2.line(plane, (200, 0), (200, 300), (40, 140, 220), 2)
    cv2.putText(
        plane,
        "ImageRect",
        (85, 165),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        (30, 30, 30),
        2,
        cv2.LINE_AA,
    )

    reference_points = np.array(
        [[0.0, 0.0], [400.0, 0.0], [400.0, 300.0], [0.0, 300.0]],
        dtype=np.float32,
    )
    image_points = np.array(
        [[120.0, 420.0], [620.0, 360.0], [560.0, 90.0], [170.0, 120.0]],
        dtype=np.float32,
    )
    canvas = np.zeros((520, 760, 3), dtype=np.uint8)
    homography_ref_to_image = cv2.getPerspectiveTransform(reference_points, image_points)
    cv2.warpPerspective(
        plane,
        homography_ref_to_image,
        (760, 520),
        dst=canvas,
        borderMode=cv2.BORDER_TRANSPARENT,
    )
    if not cv2.imwrite(str(source_path), canvas):
        raise ValueError(f"Unable to write smoke-test source image to {source_path}")

    window.project = ProjectData(name="synthetic_smoke")
    window.project_path = None
    window.source_image_original = None
    window.source_image = None
    window.reference_2d = None
    window.reference_3d = None
    window.transform_result = None
    window.selected_point_id = None
    window.pending_plane_points = []
    window.plane_pick_mode = False
    window._reset_history()
    window.load_image_file(source_path)
    window.load_reference_file(reference_path)

    for image_xy, reference_xy in zip(
        image_points.tolist(), reference_points.tolist(), strict=True
    ):
        point = window.project.add_point()
        point.image_xy = (float(image_xy[0]), float(image_xy[1]))
        point.reference_xy = (float(reference_xy[0]), float(reference_xy[1]))

    window._record_history()
    window._recompute_transform()
    if window.transform_result is None or window.source_image is None:
        raise ValueError("Smoke test could not solve a homography.")

    return export_rectified_image(
        source_image=window.source_image,
        homography_image_to_reference=window.transform_result.matrix,
        control_points=window.project.paired_points(),
        output_path=output_root / "synthetic_rectified",
        pixel_size=1.0,
        units=window.project.units,
        output_format="png",
        resampling="bilinear",
        clip_to_hull=False,
        reference_extents=window._current_reference_extents(),
        project_name=window.project.name,
        rms_error=window.project.rms_error,
        warnings=window.project.warnings,
    )
