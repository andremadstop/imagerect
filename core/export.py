"""Rectification export helpers and metadata generation."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np

from core.project import ControlPoint

Point2D = tuple[float, float]

INTERPOLATION_FLAGS = {
    "nearest": cv2.INTER_NEAREST,
    "bilinear": cv2.INTER_LINEAR,
    "bicubic": cv2.INTER_CUBIC,
}


@dataclass(slots=True)
class RectificationExportResult:
    image_path: Path
    metadata_path: Path
    width: int
    height: int
    pixel_size: float
    bounds_min: Point2D
    bounds_max: Point2D


def export_rectified_image(
    source_image: np.ndarray,
    homography_image_to_reference: np.ndarray,
    control_points: Sequence[ControlPoint],
    output_path: str | Path,
    pixel_size: float,
    units: str,
    output_format: str = "tiff",
    resampling: str = "bilinear",
    clip_to_hull: bool = False,
    reference_extents: tuple[Point2D, Point2D] | None = None,
    project_name: str = "Untitled",
    rms_error: float | None = None,
    warnings: Sequence[str] | None = None,
) -> RectificationExportResult:
    """Warp the source image into the metric reference plane and save metadata."""

    bounds_min, bounds_max = reference_extents or _bounds_from_points(
        [point.reference_xy for point in control_points if point.reference_xy is not None]
    )
    width, height, reference_to_canvas = build_canvas(bounds_min, bounds_max, pixel_size)
    transform_to_canvas = reference_to_canvas @ homography_image_to_reference
    interpolation = INTERPOLATION_FLAGS.get(resampling, cv2.INTER_LINEAR)
    warped = cv2.warpPerspective(
        source_image,
        transform_to_canvas,
        (width, height),
        flags=interpolation,
    )

    if clip_to_hull:
        warped = _apply_hull_mask(warped, control_points, reference_to_canvas)

    target_path = Path(output_path)
    if output_format == "png":
        image_path = target_path.with_suffix(".png")
    else:
        image_path = target_path.with_suffix(".tiff")
    metadata_path = target_path.with_suffix(".json")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    if not cv2.imwrite(str(image_path), warped):
        raise ValueError(f"Failed to write rectified image to {image_path}")

    metadata = {
        "project_name": project_name,
        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "units": units,
        "pixel_size": pixel_size,
        "canvas": {
            "width": width,
            "height": height,
            "bounds_min": [float(bounds_min[0]), float(bounds_min[1])],
            "bounds_max": [float(bounds_max[0]), float(bounds_max[1])],
        },
        "transform_matrix": homography_image_to_reference.tolist(),
        "reference_to_canvas_matrix": reference_to_canvas.tolist(),
        "rms_error": rms_error,
        "warnings": list(warnings or []),
        "point_pairs": [
            {
                "id": point.id,
                "label": point.label,
                "image_xy": list(point.image_xy) if point.image_xy else None,
                "reference_xy": list(point.reference_xy) if point.reference_xy else None,
                "residual": point.residual,
                "residual_vector": list(point.residual_vector) if point.residual_vector else None,
            }
            for point in control_points
        ],
    }
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return RectificationExportResult(
        image_path=image_path,
        metadata_path=metadata_path,
        width=width,
        height=height,
        pixel_size=pixel_size,
        bounds_min=bounds_min,
        bounds_max=bounds_max,
    )


def build_canvas(
    bounds_min: Point2D,
    bounds_max: Point2D,
    pixel_size: float,
) -> tuple[int, int, np.ndarray]:
    """Build canvas dimensions and a reference->canvas transform matrix."""

    if pixel_size <= 0.0:
        raise ValueError("Pixel size must be greater than zero.")

    min_x, min_y = bounds_min
    max_x, max_y = bounds_max
    width = max(1, math.ceil((max_x - min_x) / pixel_size) + 1)
    height = max(1, math.ceil((max_y - min_y) / pixel_size) + 1)
    reference_to_canvas = np.array(
        [
            [1.0 / pixel_size, 0.0, -min_x / pixel_size],
            [0.0, -1.0 / pixel_size, max_y / pixel_size],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    return width, height, reference_to_canvas


def _apply_hull_mask(
    warped_image: np.ndarray,
    control_points: Sequence[ControlPoint],
    reference_to_canvas: np.ndarray,
) -> np.ndarray:
    hull_points = np.asarray(
        [point.reference_xy for point in control_points if point.reference_xy is not None],
        dtype=np.float64,
    )
    if len(hull_points) < 3:
        return warped_image

    hull = cv2.convexHull(hull_points.astype(np.float32))
    hull_canvas = cv2.perspectiveTransform(hull.reshape(-1, 1, 2), reference_to_canvas)
    hull_canvas_int = np.round(hull_canvas).astype(np.int32)
    mask = np.zeros(warped_image.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [hull_canvas_int.reshape(-1, 2)], 255)

    masked = warped_image.copy()
    if masked.ndim == 2:
        masked[mask == 0] = 0
    else:
        masked[mask == 0] = (0,) * masked.shape[2]
    return masked


def _bounds_from_points(points: Iterable[Point2D | None]) -> tuple[Point2D, Point2D]:
    valid_points = [point for point in points if point is not None]
    if not valid_points:
        raise ValueError("No reference points available to derive export bounds.")
    xs = [point[0] for point in valid_points]
    ys = [point[1] for point in valid_points]
    return (min(xs), min(ys)), (max(xs), max(ys))
