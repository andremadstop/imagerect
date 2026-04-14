"""Rectification export helpers and metadata generation."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from core.project import ControlPoint, unit_to_mm
from core.writers.jpeg_writer import write_jpeg_image
from core.writers.png_writer import write_png_image
from core.writers.tiff_writer import TiffPageSpec, write_tiff_image, write_tiff_pages

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


@dataclass(slots=True)
class RectifiedImageRenderPlan:
    source_image: np.ndarray
    width: int
    height: int
    pixel_size: float
    pixel_size_reference_units: float
    bounds_min: Point2D
    bounds_max: Point2D
    reference_to_canvas: np.ndarray
    transform_to_canvas: np.ndarray
    interpolation: int


class ExportCancelledError(RuntimeError):
    """Raised when the user cancels a long-running export."""


@dataclass(slots=True)
class MosaicSource:
    label: str
    source_image: np.ndarray
    homography_image_to_reference: np.ndarray
    control_points: Sequence[ControlPoint]
    clip_polygon: Sequence[Point2D] | None = None
    gps_pose: dict[str, Any] | None = None
    camera_pose: dict[str, Any] | None = None
    rms_error: float | None = None
    warnings: Sequence[str] = ()


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
    multi_layer: bool = False,
    reference_segments: Sequence[tuple[Point2D, Point2D]] | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    cancel_checker: Callable[[], bool] | None = None,
    tile_size: int = 4096,
    tile_trigger_size: int = 20_000,
    reference_extents: tuple[Point2D, Point2D] | None = None,
    project_name: str = "Untitled",
    rms_error: float | None = None,
    warnings: Sequence[str] | None = None,
    gps_pose: dict[str, Any] | None = None,
    camera_pose: dict[str, Any] | None = None,
) -> RectificationExportResult:
    """Warp the source image into the metric reference plane and save metadata."""

    plan = _prepare_render_plan(
        source_image=source_image,
        homography_image_to_reference=homography_image_to_reference,
        control_points=control_points,
        pixel_size=pixel_size,
        units=units,
        bit_depth=bit_depth,
        resampling=resampling,
        clip_polygon=clip_polygon,
        reference_roi=reference_roi,
        reference_extents=reference_extents,
    )
    use_tiled_export = (
        output_format in {"tiff", "bigtiff"} and max(plan.width, plan.height) > tile_trigger_size
    )
    rendered = None if use_tiled_export else _render_plan(plan, control_points, clip_to_hull)

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
        "pixel_size_reference_units": plan.pixel_size_reference_units,
        "canvas": {
            "width": plan.width,
            "height": plan.height,
            "bounds_min": [float(plan.bounds_min[0]), float(plan.bounds_min[1])],
            "bounds_max": [float(plan.bounds_max[0]), float(plan.bounds_max[1])],
        },
        "transform_matrix": homography_image_to_reference.tolist(),
        "reference_to_canvas_matrix": plan.reference_to_canvas.tolist(),
        "rms_error": rms_error,
        "warnings": list(warnings or []),
        "gps_pose": gps_pose,
        "camera_pose": camera_pose,
        "bigtiff": False,
        "tiled_export": use_tiled_export,
        "clip_polygon": [[float(x), float(y)] for x, y in clip_polygon] if clip_polygon else None,
        "reference_roi": list(reference_roi) if reference_roi is not None else None,
        "point_pairs": _point_pairs_metadata(control_points),
    }
    try:
        _write_output_image(
            image_path,
            rendered=rendered,
            plan=plan,
            control_points=control_points,
            output_format=output_format,
            dpi=dpi,
            compression=compression,
            embed_in_tiff=embed_in_tiff,
            metadata=metadata,
            bit_depth=bit_depth,
            clip_to_hull=clip_to_hull,
            multi_layer=multi_layer,
            reference_segments=reference_segments,
            clip_polygon=clip_polygon,
            bigtiff_threshold_bytes=bigtiff_threshold_bytes,
            progress_callback=progress_callback,
            cancel_checker=cancel_checker,
            tile_size=tile_size,
            use_tiled_export=use_tiled_export,
        )
        if write_metadata_json:
            metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    except Exception:
        image_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
        raise

    return RectificationExportResult(
        image_path=image_path,
        metadata_path=metadata_path,
        width=plan.width,
        height=plan.height,
        pixel_size=pixel_size,
        bounds_min=plan.bounds_min,
        bounds_max=plan.bounds_max,
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

    plan = _prepare_render_plan(
        source_image=source_image,
        homography_image_to_reference=homography_image_to_reference,
        control_points=control_points,
        pixel_size=pixel_size,
        units=units,
        bit_depth=bit_depth,
        resampling=resampling,
        clip_polygon=clip_polygon,
        reference_roi=reference_roi,
        reference_extents=reference_extents,
    )
    return _render_plan(plan, control_points, clip_to_hull)


def render_mosaic_image(
    sources: Sequence[MosaicSource],
    pixel_size: float,
    units: str,
    bit_depth: int = 8,
    resampling: str = "bilinear",
    clip_to_hull: bool = False,
    reference_roi: tuple[float, float, float, float] | None = None,
    reference_extents: tuple[Point2D, Point2D] | None = None,
    blend_radius_px: int = 0,
) -> RectifiedImageRenderResult:
    """Render multiple rectified images into one shared mosaic canvas."""

    if not sources:
        raise ValueError("At least one mosaic source is required")

    if reference_roi is not None:
        bounds = _roi_bounds(reference_roi)
    else:
        bounds = reference_extents or _bounds_from_points(
            point.reference_xy for source in sources for point in source.control_points
        )
    rendered_layers = [
        render_rectified_image(
            source_image=source.source_image,
            homography_image_to_reference=source.homography_image_to_reference,
            control_points=source.control_points,
            pixel_size=pixel_size,
            units=units,
            bit_depth=bit_depth,
            resampling=resampling,
            clip_to_hull=clip_to_hull,
            clip_polygon=source.clip_polygon,
            reference_extents=bounds,
        )
        for source in sources
    ]
    mosaic = rendered_layers[0].image.copy()
    for layer in rendered_layers[1:]:
        mosaic = _composite_mosaic(mosaic, layer.image, blend_radius_px)

    first = rendered_layers[0]
    return RectifiedImageRenderResult(
        image=mosaic,
        width=first.width,
        height=first.height,
        pixel_size=first.pixel_size,
        pixel_size_reference_units=first.pixel_size_reference_units,
        bounds_min=first.bounds_min,
        bounds_max=first.bounds_max,
        reference_to_canvas=first.reference_to_canvas,
    )


def export_mosaic_image(
    sources: Sequence[MosaicSource],
    output_path: str | Path,
    pixel_size: float,
    units: str,
    output_format: str = "tiff",
    dpi: float = 300.0,
    bit_depth: int = 8,
    resampling: str = "bilinear",
    compression: str = "none",
    clip_to_hull: bool = False,
    reference_roi: tuple[float, float, float, float] | None = None,
    write_metadata_json: bool = True,
    embed_in_tiff: bool = True,
    bigtiff_threshold_bytes: int = 4 * 1024**3,
    multi_layer: bool = False,
    reference_segments: Sequence[tuple[Point2D, Point2D]] | None = None,
    reference_extents: tuple[Point2D, Point2D] | None = None,
    project_name: str = "Untitled",
    warnings: Sequence[str] | None = None,
    blend_radius_px: int = 0,
) -> RectificationExportResult:
    """Export a composed mosaic of multiple rectified images."""

    rendered = render_mosaic_image(
        sources=sources,
        pixel_size=pixel_size,
        units=units,
        bit_depth=bit_depth,
        resampling=resampling,
        clip_to_hull=clip_to_hull,
        reference_roi=reference_roi,
        reference_extents=reference_extents,
        blend_radius_px=blend_radius_px,
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

    all_control_points = [point for source in sources for point in source.control_points]
    clip_mask_present = any(source.clip_polygon for source in sources)
    metadata = {
        "project_name": project_name,
        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "units": units,
        "pixel_size": pixel_size,
        "pixel_size_reference_units": rendered.pixel_size_reference_units,
        "output_format": output_format,
        "dpi": dpi,
        "bit_depth": bit_depth,
        "compression": compression,
        "reference_to_canvas_matrix": rendered.reference_to_canvas.tolist(),
        "canvas": {
            "width": rendered.width,
            "height": rendered.height,
            "bounds_min": [float(rendered.bounds_min[0]), float(rendered.bounds_min[1])],
            "bounds_max": [float(rendered.bounds_max[0]), float(rendered.bounds_max[1])],
        },
        "warnings": list(warnings or []),
        "reference_roi": list(reference_roi) if reference_roi is not None else None,
        "point_pairs": _point_pairs_metadata(all_control_points),
        "gps_pose": sources[0].gps_pose if len(sources) == 1 else None,
        "camera_pose": sources[0].camera_pose if len(sources) == 1 else None,
        "bigtiff": False,
        "tiled_export": False,
        "mosaic": {
            "source_count": len(sources),
            "blend_radius_px": blend_radius_px,
            "sources": [
                {
                    "label": source.label,
                    "transform_matrix": source.homography_image_to_reference.tolist(),
                    "point_pairs": _point_pairs_metadata(source.control_points),
                    "rms_error": source.rms_error,
                    "warnings": list(source.warnings),
                    "gps_pose": source.gps_pose,
                    "camera_pose": source.camera_pose,
                }
                for source in sources
            ],
        },
    }

    if output_format in {"tiff", "bigtiff"}:
        estimated_size = estimate_output_size_bytes(
            rendered.width,
            rendered.height,
            bit_depth,
            layer_count=4 if multi_layer else 1,
        )
        use_bigtiff = output_format == "bigtiff" or estimated_size > bigtiff_threshold_bytes
        metadata["bigtiff"] = use_bigtiff
        if multi_layer:
            page_descriptions = _layer_descriptions(
                metadata,
                True,
                reference_segments,
                clip_mask_present,
            )
            pages = [
                TiffPageSpec(
                    data=rendered.image,
                    shape=rendered.image.shape,
                    dtype=rendered.image.dtype,
                    description=page_descriptions[0] if embed_in_tiff else None,
                    photometric=_photometric(rendered.image),
                )
            ]
            page_index = 1
            if reference_segments:
                overlay_image = _render_reference_overlay_canvas(
                    rendered.height,
                    rendered.width,
                    rendered.reference_to_canvas,
                    reference_segments,
                )
                pages.append(
                    TiffPageSpec(
                        data=overlay_image,
                        shape=overlay_image.shape,
                        dtype=overlay_image.dtype,
                        description=page_descriptions[page_index] if embed_in_tiff else None,
                        photometric="rgb",
                    )
                )
                page_index += 1
            points_image = _render_control_point_overlay_canvas(
                rendered.height,
                rendered.width,
                rendered.reference_to_canvas,
                all_control_points,
            )
            pages.append(
                TiffPageSpec(
                    data=points_image,
                    shape=points_image.shape,
                    dtype=points_image.dtype,
                    description=page_descriptions[page_index] if embed_in_tiff else None,
                    photometric="rgb",
                )
            )
            page_index += 1
            if clip_mask_present:
                mask_image = _render_mosaic_clip_mask(
                    rendered.height,
                    rendered.width,
                    rendered.reference_to_canvas,
                    sources,
                )
                pages.append(
                    TiffPageSpec(
                        data=mask_image,
                        shape=mask_image.shape,
                        dtype=mask_image.dtype,
                        description=page_descriptions[page_index] if embed_in_tiff else None,
                    )
                )
            write_tiff_pages(
                image_path,
                pages,
                dpi=dpi,
                compression=compression,
                bigtiff=use_bigtiff,
            )
        else:
            write_tiff_image(
                image_path,
                rendered.image,
                dpi=dpi,
                compression=compression,
                metadata=metadata,
                bigtiff=use_bigtiff,
                embed_metadata=embed_in_tiff,
            )
    elif output_format == "png":
        write_png_image(image_path, rendered.image)
    elif output_format == "jpeg":
        write_jpeg_image(image_path, rendered.image)
    else:
        raise ValueError(f"Unsupported export format: {output_format}")

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
    *,
    rendered: RectifiedImageRenderResult | None,
    plan: RectifiedImageRenderPlan,
    control_points: Sequence[ControlPoint],
    output_format: str,
    dpi: float,
    compression: str,
    embed_in_tiff: bool,
    metadata: dict[str, object],
    bit_depth: int,
    clip_to_hull: bool,
    multi_layer: bool,
    reference_segments: Sequence[tuple[Point2D, Point2D]] | None,
    clip_polygon: Sequence[Point2D] | None,
    bigtiff_threshold_bytes: int,
    progress_callback: Callable[[int, int, str], None] | None,
    cancel_checker: Callable[[], bool] | None,
    tile_size: int,
    use_tiled_export: bool,
) -> None:
    if output_format in {"tiff", "bigtiff"}:
        estimated_size = estimate_output_size_bytes(
            plan.width,
            plan.height,
            bit_depth,
            layer_count=4 if multi_layer else 1,
        )
        use_bigtiff = output_format == "bigtiff" or estimated_size > bigtiff_threshold_bytes
        metadata["bigtiff"] = use_bigtiff
        if use_tiled_export or multi_layer:
            _write_tiff_export(
                image_path=image_path,
                rendered=rendered,
                plan=plan,
                control_points=control_points,
                dpi=dpi,
                compression=compression,
                metadata=metadata,
                bigtiff=use_bigtiff,
                embed_metadata=embed_in_tiff,
                clip_to_hull=clip_to_hull,
                multi_layer=multi_layer,
                reference_segments=reference_segments,
                clip_polygon=clip_polygon,
                progress_callback=progress_callback,
                cancel_checker=cancel_checker,
                tile_size=tile_size,
                use_tiled_export=use_tiled_export,
            )
        else:
            if rendered is None:
                raise ValueError("Rendered image is required for non-tiled TIFF export")
            write_tiff_image(
                image_path,
                rendered.image,
                dpi=dpi,
                compression=compression,
                metadata=metadata,
                bigtiff=use_bigtiff,
                embed_metadata=embed_in_tiff,
            )
        return

    if output_format == "png":
        if rendered is None:
            rendered = _render_plan(plan, control_points, clip_to_hull)
        write_png_image(image_path, rendered.image)
        return

    if output_format == "jpeg":
        if rendered is None:
            rendered = _render_plan(plan, control_points, clip_to_hull)
        write_jpeg_image(image_path, rendered.image)
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


def _prepare_render_plan(
    source_image: np.ndarray,
    homography_image_to_reference: np.ndarray,
    control_points: Sequence[ControlPoint],
    pixel_size: float,
    units: str,
    bit_depth: int,
    resampling: str,
    clip_polygon: Sequence[Point2D] | None,
    reference_roi: tuple[float, float, float, float] | None,
    reference_extents: tuple[Point2D, Point2D] | None,
) -> RectifiedImageRenderPlan:
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
    interpolation = INTERPOLATION_FLAGS.get(resampling)
    if interpolation is None:
        raise ValueError(f"Unsupported resampling mode: {resampling}")
    return RectifiedImageRenderPlan(
        source_image=source_for_warp,
        width=width,
        height=height,
        pixel_size=pixel_size,
        pixel_size_reference_units=pixel_size_units,
        bounds_min=bounds_min,
        bounds_max=bounds_max,
        reference_to_canvas=reference_to_canvas,
        transform_to_canvas=transform_to_canvas,
        interpolation=interpolation,
    )


def _render_plan(
    plan: RectifiedImageRenderPlan,
    control_points: Sequence[ControlPoint],
    clip_to_hull: bool,
) -> RectifiedImageRenderResult:
    warped = cv2.warpPerspective(
        plan.source_image,
        plan.transform_to_canvas,
        (plan.width, plan.height),
        flags=plan.interpolation,
    )
    if clip_to_hull:
        warped = _apply_hull_mask(warped, control_points, plan.reference_to_canvas)
    return RectifiedImageRenderResult(
        image=warped,
        width=plan.width,
        height=plan.height,
        pixel_size=plan.pixel_size,
        pixel_size_reference_units=plan.pixel_size_reference_units,
        bounds_min=plan.bounds_min,
        bounds_max=plan.bounds_max,
        reference_to_canvas=plan.reference_to_canvas,
    )


def _composite_mosaic(
    base_image: np.ndarray,
    new_image: np.ndarray,
    blend_radius_px: int,
) -> np.ndarray:
    new_mask = _nonzero_mask(new_image)
    if not np.any(new_mask):
        return base_image

    composite = base_image.copy()
    if blend_radius_px <= 0:
        composite[new_mask] = new_image[new_mask]
        return composite

    base_mask = _nonzero_mask(base_image)
    if not np.any(base_mask):
        composite[new_mask] = new_image[new_mask]
        return composite

    overlap = base_mask & new_mask
    if not np.any(overlap):
        composite[new_mask] = new_image[new_mask]
        return composite

    base_distance = cv2.distanceTransform(base_mask.astype(np.uint8), cv2.DIST_L2, 3)
    new_distance = cv2.distanceTransform(new_mask.astype(np.uint8), cv2.DIST_L2, 3)
    base_weight = np.clip(base_distance / max(float(blend_radius_px), 1.0), 0.0, 1.0)
    new_weight = np.clip(new_distance / max(float(blend_radius_px), 1.0), 0.0, 1.0)

    total_weight = base_weight + new_weight
    total_weight[total_weight == 0.0] = 1.0

    base_float = base_image.astype(np.float32)
    new_float = new_image.astype(np.float32)
    if base_image.ndim == 2:
        blended = (base_float * base_weight + new_float * new_weight) / total_weight
        composite = np.where(new_mask, new_float, base_float)
        composite[overlap] = blended[overlap]
    else:
        base_weight_rgb = base_weight[:, :, None]
        new_weight_rgb = new_weight[:, :, None]
        total_weight_rgb = total_weight[:, :, None]
        blended = (base_float * base_weight_rgb + new_float * new_weight_rgb) / total_weight_rgb
        composite = np.where(new_mask[:, :, None], new_float, base_float)
        composite[overlap] = blended[overlap]

    return composite.astype(base_image.dtype)


def _write_tiff_export(
    *,
    image_path: Path,
    rendered: RectifiedImageRenderResult | None,
    plan: RectifiedImageRenderPlan,
    control_points: Sequence[ControlPoint],
    dpi: float,
    compression: str,
    metadata: dict[str, object],
    bigtiff: bool,
    embed_metadata: bool,
    clip_to_hull: bool,
    multi_layer: bool,
    reference_segments: Sequence[tuple[Point2D, Point2D]] | None,
    clip_polygon: Sequence[Point2D] | None,
    progress_callback: Callable[[int, int, str], None] | None,
    cancel_checker: Callable[[], bool] | None,
    tile_size: int,
    use_tiled_export: bool,
) -> None:
    pages: list[TiffPageSpec] = []
    page_descriptions = _layer_descriptions(
        metadata,
        multi_layer,
        reference_segments,
        clip_polygon is not None,
    )

    if use_tiled_export:
        page_count = len(page_descriptions)
        progress = _TileProgress(
            total=_tile_count(plan.width, plan.height, tile_size) * page_count,
            callback=progress_callback,
            cancel_checker=cancel_checker,
        )
        pages.append(
            TiffPageSpec(
                data=_iter_primary_tiles(plan, control_points, clip_to_hull, tile_size, progress),
                shape=_page_shape(plan.height, plan.width, plan.source_image),
                dtype=plan.source_image.dtype,
                description=page_descriptions[0] if embed_metadata else None,
                photometric=_photometric(plan.source_image),
                tile=(tile_size, tile_size),
            )
        )
        page_index = 1
        if multi_layer:
            if reference_segments:
                pages.append(
                    TiffPageSpec(
                        data=_iter_reference_overlay_tiles(
                            plan,
                            reference_segments,
                            tile_size,
                            progress,
                        ),
                        shape=(plan.height, plan.width, 3),
                        dtype=np.dtype(np.uint8),
                        description=page_descriptions[page_index] if embed_metadata else None,
                        photometric="rgb",
                        tile=(tile_size, tile_size),
                    )
                )
                page_index += 1
            pages.append(
                TiffPageSpec(
                    data=_iter_control_point_tiles(plan, control_points, tile_size, progress),
                    shape=(plan.height, plan.width, 3),
                    dtype=np.dtype(np.uint8),
                    description=page_descriptions[page_index] if embed_metadata else None,
                    photometric="rgb",
                    tile=(tile_size, tile_size),
                )
            )
            page_index += 1
            if clip_polygon:
                pages.append(
                    TiffPageSpec(
                        data=_iter_clip_mask_tiles(plan, clip_polygon, tile_size, progress),
                        shape=(plan.height, plan.width),
                        dtype=np.dtype(np.uint8),
                        description=page_descriptions[page_index] if embed_metadata else None,
                        tile=(tile_size, tile_size),
                    )
                )
        write_tiff_pages(image_path, pages, dpi=dpi, compression=compression, bigtiff=bigtiff)
        return

    if rendered is None:
        rendered = _render_plan(plan, control_points, clip_to_hull)
    pages.append(
        TiffPageSpec(
            data=rendered.image,
            shape=rendered.image.shape,
            dtype=rendered.image.dtype,
            description=page_descriptions[0] if embed_metadata else None,
            photometric=_photometric(rendered.image),
        )
    )
    page_index = 1
    if multi_layer:
        if reference_segments:
            overlay_image = _render_reference_overlay_image(plan, reference_segments)
            pages.append(
                TiffPageSpec(
                    data=overlay_image,
                    shape=overlay_image.shape,
                    dtype=overlay_image.dtype,
                    description=page_descriptions[page_index] if embed_metadata else None,
                    photometric="rgb",
                )
            )
            page_index += 1
        points_image = _render_control_point_overlay_image(plan, control_points)
        pages.append(
            TiffPageSpec(
                data=points_image,
                shape=points_image.shape,
                dtype=points_image.dtype,
                description=page_descriptions[page_index] if embed_metadata else None,
                photometric="rgb",
            )
        )
        page_index += 1
        if clip_polygon:
            mask_image = _render_clip_mask_image(plan, clip_polygon)
            pages.append(
                TiffPageSpec(
                    data=mask_image,
                    shape=mask_image.shape,
                    dtype=mask_image.dtype,
                    description=page_descriptions[page_index] if embed_metadata else None,
                )
            )
    write_tiff_pages(image_path, pages, dpi=dpi, compression=compression, bigtiff=bigtiff)


def _iter_primary_tiles(
    plan: RectifiedImageRenderPlan,
    control_points: Sequence[ControlPoint],
    clip_to_hull: bool,
    tile_size: int,
    progress: _TileProgress,
) -> Iterator[np.ndarray]:
    for tile_x, tile_y in _tile_origins(plan.width, plan.height, tile_size):
        progress.step("Rectified image")
        yield _render_primary_tile(plan, control_points, clip_to_hull, tile_x, tile_y, tile_size)


def _iter_reference_overlay_tiles(
    plan: RectifiedImageRenderPlan,
    reference_segments: Sequence[tuple[Point2D, Point2D]],
    tile_size: int,
    progress: _TileProgress,
) -> Iterator[np.ndarray]:
    for tile_x, tile_y in _tile_origins(plan.width, plan.height, tile_size):
        progress.step("DXF overlay")
        yield _render_reference_overlay_tile(plan, reference_segments, tile_x, tile_y, tile_size)


def _iter_control_point_tiles(
    plan: RectifiedImageRenderPlan,
    control_points: Sequence[ControlPoint],
    tile_size: int,
    progress: _TileProgress,
) -> Iterator[np.ndarray]:
    for tile_x, tile_y in _tile_origins(plan.width, plan.height, tile_size):
        progress.step("Control points")
        yield _render_control_point_tile(plan, control_points, tile_x, tile_y, tile_size)


def _iter_clip_mask_tiles(
    plan: RectifiedImageRenderPlan,
    clip_polygon: Sequence[Point2D],
    tile_size: int,
    progress: _TileProgress,
) -> Iterator[np.ndarray]:
    for tile_x, tile_y in _tile_origins(plan.width, plan.height, tile_size):
        progress.step("Clip mask")
        yield _render_clip_mask_tile(plan, clip_polygon, tile_x, tile_y, tile_size)


def _render_primary_tile(
    plan: RectifiedImageRenderPlan,
    control_points: Sequence[ControlPoint],
    clip_to_hull: bool,
    tile_x: int,
    tile_y: int,
    tile_size: int,
) -> np.ndarray:
    tile_width = min(tile_size, plan.width - tile_x)
    tile_height = min(tile_size, plan.height - tile_y)
    translate = np.array(
        [[1.0, 0.0, -tile_x], [0.0, 1.0, -tile_y], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    warped = cv2.warpPerspective(
        plan.source_image,
        translate @ plan.transform_to_canvas,
        (tile_width, tile_height),
        flags=plan.interpolation,
    )
    if clip_to_hull:
        warped = _apply_hull_mask(warped, control_points, translate @ plan.reference_to_canvas)
    return _pad_tile(warped, tile_size)


def _render_reference_overlay_image(
    plan: RectifiedImageRenderPlan,
    reference_segments: Sequence[tuple[Point2D, Point2D]],
) -> np.ndarray:
    return _render_reference_overlay_canvas(
        plan.height,
        plan.width,
        plan.reference_to_canvas,
        reference_segments,
    )


def _render_reference_overlay_tile(
    plan: RectifiedImageRenderPlan,
    reference_segments: Sequence[tuple[Point2D, Point2D]],
    tile_x: int,
    tile_y: int,
    tile_size: int,
) -> np.ndarray:
    tile = np.zeros((tile_size, tile_size, 3), dtype=np.uint8)
    translate = np.array(
        [[1.0, 0.0, -tile_x], [0.0, 1.0, -tile_y], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    _draw_reference_segments(tile, reference_segments, translate @ plan.reference_to_canvas)
    return tile


def _render_control_point_overlay_image(
    plan: RectifiedImageRenderPlan,
    control_points: Sequence[ControlPoint],
) -> np.ndarray:
    return _render_control_point_overlay_canvas(
        plan.height,
        plan.width,
        plan.reference_to_canvas,
        control_points,
    )


def _render_control_point_tile(
    plan: RectifiedImageRenderPlan,
    control_points: Sequence[ControlPoint],
    tile_x: int,
    tile_y: int,
    tile_size: int,
) -> np.ndarray:
    tile = np.zeros((tile_size, tile_size, 3), dtype=np.uint8)
    translate = np.array(
        [[1.0, 0.0, -tile_x], [0.0, 1.0, -tile_y], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    _draw_control_points(tile, control_points, translate @ plan.reference_to_canvas)
    return tile


def _render_clip_mask_image(
    plan: RectifiedImageRenderPlan,
    clip_polygon: Sequence[Point2D],
) -> np.ndarray:
    return _render_projected_polygon_mask(
        plan.height,
        plan.width,
        plan.transform_to_canvas,
        clip_polygon,
    )


def _render_clip_mask_tile(
    plan: RectifiedImageRenderPlan,
    clip_polygon: Sequence[Point2D],
    tile_x: int,
    tile_y: int,
    tile_size: int,
) -> np.ndarray:
    mask = np.zeros((tile_size, tile_size), dtype=np.uint8)
    translate = np.array(
        [[1.0, 0.0, -tile_x], [0.0, 1.0, -tile_y], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )
    projected = cv2.perspectiveTransform(
        np.asarray(clip_polygon, dtype=np.float32).reshape(-1, 1, 2),
        (translate @ plan.transform_to_canvas).astype(np.float32),
    ).reshape(-1, 2)
    cv2.fillPoly(mask, [np.round(projected).astype(np.int32)], 255)
    return mask


def _draw_reference_segments(
    image: np.ndarray,
    reference_segments: Sequence[tuple[Point2D, Point2D]],
    reference_to_canvas: np.ndarray,
) -> None:
    for start, end in reference_segments:
        points = cv2.perspectiveTransform(
            np.asarray([start, end], dtype=np.float32).reshape(-1, 1, 2),
            reference_to_canvas.astype(np.float32),
        ).reshape(-1, 2)
        cv2.line(
            image,
            _pixel_point(points[0]),
            _pixel_point(points[1]),
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )


def _draw_control_points(
    image: np.ndarray,
    control_points: Sequence[ControlPoint],
    reference_to_canvas: np.ndarray,
) -> None:
    for point in control_points:
        if point.reference_xy is None:
            continue
        canvas_point = cv2.perspectiveTransform(
            np.asarray([point.reference_xy], dtype=np.float32).reshape(-1, 1, 2),
            reference_to_canvas.astype(np.float32),
        ).reshape(-1, 2)[0]
        x, y = _pixel_point(canvas_point)
        if x < -8 or y < -8 or x > image.shape[1] + 8 or y > image.shape[0] + 8:
            continue
        cv2.circle(image, (x, y), 5, (0, 255, 0), -1, cv2.LINE_AA)
        cv2.putText(
            image,
            point.label,
            (x + 8, y - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )


def _pad_tile(tile: np.ndarray, tile_size: int) -> np.ndarray:
    if tile.shape[0] == tile_size and tile.shape[1] == tile_size:
        return tile
    if tile.ndim == 2:
        padded = np.zeros((tile_size, tile_size), dtype=tile.dtype)
        padded[: tile.shape[0], : tile.shape[1]] = tile
        return padded
    padded = np.zeros((tile_size, tile_size, tile.shape[2]), dtype=tile.dtype)
    padded[: tile.shape[0], : tile.shape[1], :] = tile
    return padded


def _tile_origins(width: int, height: int, tile_size: int) -> Iterator[tuple[int, int]]:
    for tile_y in range(0, height, tile_size):
        for tile_x in range(0, width, tile_size):
            yield tile_x, tile_y


def _tile_count(width: int, height: int, tile_size: int) -> int:
    tiles_x = math.ceil(width / tile_size)
    tiles_y = math.ceil(height / tile_size)
    return tiles_x * tiles_y


def _page_shape(height: int, width: int, image: np.ndarray) -> tuple[int, ...]:
    if image.ndim == 2:
        return (height, width)
    return (height, width, image.shape[2])


def _photometric(image: np.ndarray) -> str | None:
    if image.ndim == 3 and image.shape[2] in {3, 4}:
        return "rgb"
    return None


def _layer_descriptions(
    metadata: dict[str, object],
    multi_layer: bool,
    reference_segments: Sequence[tuple[Point2D, Point2D]] | None,
    clip_mask_present: bool,
) -> list[str]:
    pages = [
        {**metadata, "layer_name": "rectified_image"},
    ]
    if multi_layer:
        if reference_segments:
            pages.append({"layer_name": "dxf_overlay"})
        pages.append({"layer_name": "control_points"})
        if clip_mask_present:
            pages.append({"layer_name": "clip_mask"})
    return [json.dumps(page, indent=2) for page in pages]


def _pixel_point(point: np.ndarray) -> tuple[int, int]:
    return (round(float(point[0])), round(float(point[1])))


@dataclass(slots=True)
class _TileProgress:
    total: int
    callback: Callable[[int, int, str], None] | None = None
    cancel_checker: Callable[[], bool] | None = None
    current: int = 0

    def step(self, message: str) -> None:
        if self.cancel_checker is not None and self.cancel_checker():
            raise ExportCancelledError("Export cancelled")
        self.current += 1
        if self.callback is not None:
            self.callback(self.current, self.total, message)


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


def _nonzero_mask(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return np.asarray(image > 0, dtype=bool)
    return np.asarray(np.any(image != 0, axis=2), dtype=bool)


def _point_pairs_metadata(control_points: Sequence[ControlPoint]) -> list[dict[str, Any]]:
    return [
        {
            "id": point.id,
            "label": point.label,
            "image_xy": list(point.image_xy) if point.image_xy else None,
            "reference_xy": list(point.reference_xy) if point.reference_xy else None,
            "residual": point.residual,
            "residual_vector": list(point.residual_vector) if point.residual_vector else None,
        }
        for point in control_points
    ]


def _render_reference_overlay_canvas(
    height: int,
    width: int,
    reference_to_canvas: np.ndarray,
    reference_segments: Sequence[tuple[Point2D, Point2D]],
) -> np.ndarray:
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    _draw_reference_segments(canvas, reference_segments, reference_to_canvas)
    return canvas


def _render_control_point_overlay_canvas(
    height: int,
    width: int,
    reference_to_canvas: np.ndarray,
    control_points: Sequence[ControlPoint],
) -> np.ndarray:
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    _draw_control_points(canvas, control_points, reference_to_canvas)
    return canvas


def _render_projected_polygon_mask(
    height: int,
    width: int,
    transform_to_canvas: np.ndarray,
    polygon: Sequence[Point2D],
) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    if len(polygon) < 3:
        return mask
    projected = cv2.perspectiveTransform(
        np.asarray(polygon, dtype=np.float32).reshape(-1, 1, 2),
        transform_to_canvas.astype(np.float32),
    ).reshape(-1, 2)
    cv2.fillPoly(mask, [np.round(projected).astype(np.int32)], 255)
    return mask


def _render_mosaic_clip_mask(
    height: int,
    width: int,
    reference_to_canvas: np.ndarray,
    sources: Sequence[MosaicSource],
) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    for source in sources:
        if not source.clip_polygon:
            continue
        projected_mask = _render_projected_polygon_mask(
            height,
            width,
            reference_to_canvas @ source.homography_image_to_reference,
            source.clip_polygon,
        )
        mask = np.maximum(mask, projected_mask)
    return mask
