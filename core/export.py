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

from core.project import ControlPoint, unit_to_mm
from core.writers.jpeg_writer import write_jpeg_image
from core.writers.png_writer import write_png_image
from core.writers.tiff_writer import write_tiff_image

Point2D = tuple[float, float]

INTERPOLATION_FLAGS = {
    "nearest": cv2.INTER_NEAREST,
    "bilinear": cv2.INTER_LINEAR,
    "bicubic": cv2.INTER_CUBIC,
    "lanczos": cv2.INTER_LANCZOS4,
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


@dataclass(slots=True)
class RectifiedImageRenderResult:
    image: np.ndarray
    width: int
    height: int
    pixel_size: float
    pixel_size_reference_units: float
    bounds_min: Point2D
    bounds_max: Point2D
    reference_to_canvas: np.ndarray


def export_rectified_image(
    source_image: np.ndarray,
    homography_image_to_reference: np.ndarray,
    control_points: Sequence[ControlPoint],
    output_path: str | Path,
    pixel_size: float,
    units: str,
    output_format: str = "tiff",
    dpi: float = 300.0,
    bit_depth: int = 8,
    resampling: str = "bilinear",
    compression: str = "none",
    clip_to_hull: bool = False,
    clip_polygon: Sequence[Point2D] | None = None,
    reference_roi: tuple[float, float, float, float] | None = None,
    write_metadata_json: bool = True,
    embed_in_tiff: bool = True,
    bigtiff_threshold_bytes: int = 4 * 1024**3,
    reference_extents: tuple[Point2D, Point2D] | None = None,
    project_name: str = "Untitled",
    rms_error: float | None = None,
    warnings: Sequence[str] | None = None,
) -> RectificationExportResult:
    """Warp the source image into the metric reference plane and save metadata."""

    rendered = render_rectified_image(
        source_image=source_image,
        homography_image_to_reference=homography_image_to_reference,
        control_points=control_points,
        pixel_size=pixel_size,
        units=units,
        bit_depth=bit_depth,
        resampling=resampling,
        clip_to_hull=clip_to_hull,
        clip_polygon=clip_polygon,
        reference_roi=reference_roi,
        reference_extents=reference_extents,
    )

    target_path = Path(output_path)
    if output_format == "png":
        image_path = target_path.with_suffix(".png")
    elif output_format == "jpeg":
        image_path = target_path.with_suffix(".jpg")
    else:
        image_path = target_path.with_suffix(".tiff")
    metadata_path = target_path.with_suffix(".json")
    image_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = {
        "project_name": project_name,
        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "units": units,
        "pixel_size": pixel_size,
        "dpi": dpi,
        "output_format": output_format,
        "bit_depth": bit_depth,
        "compression": compression,
        "pixel_size_reference_units": rendered.pixel_size_reference_units,
        "canvas": {
            "width": rendered.width,
            "height": rendered.height,
            "bounds_min": [float(rendered.bounds_min[0]), float(rendered.bounds_min[1])],
            "bounds_max": [float(rendered.bounds_max[0]), float(rendered.bounds_max[1])],
        },
        "transform_matrix": homography_image_to_reference.tolist(),
        "reference_to_canvas_matrix": rendered.reference_to_canvas.tolist(),
        "rms_error": rms_error,
        "warnings": list(warnings or []),
        "bigtiff": False,
        "clip_polygon": [[float(x), float(y)] for x, y in clip_polygon] if clip_polygon else None,
        "reference_roi": list(reference_roi) if reference_roi is not None else None,
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
    _write_output_image(
        image_path,
        rendered.image,
        output_format=output_format,
        dpi=dpi,
        compression=compression,
        embed_in_tiff=embed_in_tiff,
        metadata=metadata,
        bigtiff_threshold_bytes=bigtiff_threshold_bytes,
    )
    if write_metadata_json:
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    return RectificationExportResult(
        image_path=image_path,
        metadata_path=metadata_path,
        width=rendered.width,
        height=rendered.height,
        pixel_size=pixel_size,
        bounds_min=rendered.bounds_min,
        bounds_max=rendered.bounds_max,
    )


def render_rectified_image(
    source_image: np.ndarray,
    homography_image_to_reference: np.ndarray,
    control_points: Sequence[ControlPoint],
    pixel_size: float,
    units: str,
    bit_depth: int = 8,
    resampling: str = "bilinear",
    clip_to_hull: bool = False,
    clip_polygon: Sequence[Point2D] | None = None,
    reference_roi: tuple[float, float, float, float] | None = None,
    reference_extents: tuple[Point2D, Point2D] | None = None,
) -> RectifiedImageRenderResult:
    """Warp the source image into the reference plane without writing to disk."""

    source_for_warp = _convert_image_bit_depth(source_image, bit_depth)
    if clip_polygon:
        source_for_warp = _apply_source_polygon_mask(source_for_warp, clip_polygon)

    if reference_roi is not None:
        bounds_min, bounds_max = _roi_bounds(reference_roi)
    else:
        bounds_min, bounds_max = reference_extents or _bounds_from_points(
            [point.reference_xy for point in control_points if point.reference_xy is not None]
        )

    pixel_size_units = pixel_size / unit_to_mm(units)
    width, height, reference_to_canvas = build_canvas(bounds_min, bounds_max, pixel_size_units)
    transform_to_canvas = reference_to_canvas @ homography_image_to_reference
    interpolation = INTERPOLATION_FLAGS.get(resampling, cv2.INTER_LINEAR)
    warped = cv2.warpPerspective(
        source_for_warp,
        transform_to_canvas,
        (width, height),
        flags=interpolation,
    )

    if clip_to_hull:
        warped = _apply_hull_mask(warped, control_points, reference_to_canvas)

    return RectifiedImageRenderResult(
        image=warped,
        width=width,
        height=height,
        pixel_size=pixel_size,
        pixel_size_reference_units=pixel_size_units,
        bounds_min=bounds_min,
        bounds_max=bounds_max,
        reference_to_canvas=reference_to_canvas,
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


def estimate_output_size_bytes(
    width: int,
    height: int,
    bit_depth: int,
    layer_count: int = 1,
    channel_count: int = 3,
) -> int:
    bytes_per_channel = 4 if bit_depth == 32 else max(1, bit_depth // 8)
    return width * height * channel_count * bytes_per_channel * max(layer_count, 1)


def _write_output_image(
    image_path: Path,
    image: np.ndarray,
    *,
    output_format: str,
    dpi: float,
    compression: str,
    embed_in_tiff: bool,
    metadata: dict[str, object],
    bigtiff_threshold_bytes: int,
) -> None:
    if output_format in {"tiff", "bigtiff"}:
        estimated_size = estimate_output_size_bytes(
            image.shape[1],
            image.shape[0],
            _bit_depth_from_dtype(image.dtype),
        )
        use_bigtiff = output_format == "bigtiff" or estimated_size > bigtiff_threshold_bytes
        metadata["bigtiff"] = use_bigtiff
        write_tiff_image(
            image_path,
            image,
            dpi=dpi,
            compression=compression,
            metadata=metadata,
            bigtiff=use_bigtiff,
            embed_metadata=embed_in_tiff,
        )
        return

    if output_format == "png":
        write_png_image(image_path, image)
        return

    if output_format == "jpeg":
        write_jpeg_image(image_path, image)
        return

    raise ValueError(f"Unsupported export format: {output_format}")


def _convert_image_bit_depth(image: np.ndarray, bit_depth: int) -> np.ndarray:
    if bit_depth not in {8, 16, 32}:
        raise ValueError("Bit depth must be 8, 16, or 32")

    if bit_depth == _bit_depth_from_dtype(image.dtype):
        return image.copy()

    normalized = _normalize_image(image)
    if bit_depth == 8:
        return np.round(normalized * 255.0).astype(np.uint8)
    if bit_depth == 16:
        return np.round(normalized * 65535.0).astype(np.uint16)
    return normalized.astype(np.float32)


def _normalize_image(image: np.ndarray) -> np.ndarray:
    if image.dtype == np.uint8:
        return image.astype(np.float32) / 255.0
    if image.dtype == np.uint16:
        return image.astype(np.float32) / 65535.0
    if np.issubdtype(image.dtype, np.floating):
        normalized = image.astype(np.float32)
        max_value = float(np.nanmax(normalized)) if normalized.size else 0.0
        if max_value > 1.0:
            divisor = 65535.0 if max_value > 255.0 else 255.0
            normalized = normalized / divisor
        return np.asarray(np.clip(normalized, 0.0, 1.0), dtype=np.float32)
    return np.asarray(np.clip(image.astype(np.float32) / 255.0, 0.0, 1.0), dtype=np.float32)


def _bit_depth_from_dtype(dtype: np.dtype[np.generic]) -> int:
    if dtype == np.dtype(np.uint8):
        return 8
    if dtype == np.dtype(np.uint16):
        return 16
    if dtype in {np.dtype(np.float32), np.dtype(np.float64)}:
        return 32
    raise ValueError(f"Unsupported image dtype for export: {dtype}")


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


def _apply_source_polygon_mask(
    source_image: np.ndarray,
    clip_polygon: Sequence[Point2D],
) -> np.ndarray:
    polygon = np.asarray(clip_polygon, dtype=np.float32)
    if len(polygon) < 3:
        return source_image

    mask = np.zeros(source_image.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [np.round(polygon).astype(np.int32)], 255)
    masked = source_image.copy()
    if masked.ndim == 2:
        masked[mask == 0] = 0
    else:
        masked[mask == 0] = (0,) * masked.shape[2]
    return masked


def _roi_bounds(reference_roi: tuple[float, float, float, float]) -> tuple[Point2D, Point2D]:
    x0, y0, x1, y1 = reference_roi
    return (min(x0, x1), min(y0, y1)), (max(x0, x1), max(y0, y1))


def _bounds_from_points(points: Iterable[Point2D | None]) -> tuple[Point2D, Point2D]:
    valid_points = [point for point in points if point is not None]
    if not valid_points:
        raise ValueError("No reference points available to derive export bounds.")
    xs = [point[0] for point in valid_points]
    ys = [point[1] for point in valid_points]
    return (min(xs), min(ys)), (max(xs), max(ys))
