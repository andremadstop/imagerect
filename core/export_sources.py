"""Shared helpers for building export inputs from a project."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from core.export import MosaicSource
from core.image import load_image
from core.lens import LensProfile, apply_lens_correction, lens_profile_from_dict
from core.pose import build_camera_pose, extract_gps_pose
from core.project import ControlPoint, ImageEntry, Point2D, ProjectData
from core.reference2d import load_dxf
from core.reference3d import load_e57, load_obj, reference_plane_extents, working_plane_from_dict
from core.transform import HomographyResult, solve_planar_homography


def image_label(project: ProjectData, entry: ImageEntry, index: int) -> str:
    """Return a descriptive label for an image entry."""
    image_path = project.resolve_image_entry_path(entry)
    if image_path is not None:
        return image_path.stem or f"Image {index + 1}"
    return Path(entry.path).stem or f"Image {index + 1}"


def ensure_entry_gps_pose(project: ProjectData, entry: ImageEntry) -> dict[str, Any] | None:
    """Extract GPS pose from image if not already present."""
    if entry.gps_pose is not None:
        return entry.gps_pose
    image_path = project.resolve_image_entry_path(entry)
    if image_path is None:
        return None
    entry.gps_pose = extract_gps_pose(image_path)
    return entry.gps_pose


def lens_profile_from_correction(correction: dict[str, object] | None) -> LensProfile | None:
    """Extract LensProfile from a correction dictionary."""
    if not correction or not correction.get("applied"):
        return None

    payload = correction.get("profile")
    if not isinstance(payload, dict):
        return None

    try:
        return lens_profile_from_dict(payload)
    except (KeyError, TypeError, ValueError):
        return None


def load_image_entry_source(project: ProjectData, entry: ImageEntry) -> np.ndarray:
    """Load and optionally correct the source image for an entry."""
    image_path = project.resolve_image_entry_path(entry)
    if image_path is None:
        raise ValueError("Image entry has no source path.")
    image = load_image(image_path)
    profile = lens_profile_from_correction(entry.lens_correction)
    if profile is None:
        return image
    return apply_lens_correction(image, profile)


def homography_for_entry(entry: ImageEntry) -> tuple[np.ndarray, list[str]]:
    """Compute or return the stored homography for an entry."""
    entry_points = paired_points(entry)
    if len(entry_points) < 4:
        raise ValueError("at least four paired points are required")
    if entry.transform_matrix is not None:
        return np.asarray(entry.transform_matrix, dtype=np.float64), list(entry.warnings)

    result = _solve_entry_homography(entry)
    warnings = list(dict.fromkeys([*entry.warnings, *result.warnings]))
    return result.matrix, warnings


def build_entry_camera_pose(
    project: ProjectData,
    entry: ImageEntry,
    source_image: np.ndarray,
    homography_image_to_reference: np.ndarray,
    gps_pose: dict[str, Any] | None = None,
) -> dict[str, object] | None:
    """Build a camera pose for an entry."""
    profile = lens_profile_from_correction(entry.lens_correction)
    if profile is None:
        return None
    return build_camera_pose(
        homography_image_to_reference=homography_image_to_reference,
        image_size=(source_image.shape[1], source_image.shape[0]),
        profile=profile,
        gps_pose=gps_pose,
        reference_crs_epsg=project.reference_crs_epsg,
    )


def collect_project_export_sources(project: ProjectData) -> tuple[list[MosaicSource], list[str]]:
    """Collect all valid export sources from the project."""
    sources: list[MosaicSource] = []
    warnings: list[str] = []
    for index, entry in enumerate(project.images):
        if not entry.path:
            continue

        label = image_label(project, entry, index)
        entry_points = paired_points(entry)
        if len(entry_points) < 4:
            warnings.append(f"Skipped {label}: needs at least four paired points")
            continue

        image_path = project.resolve_image_entry_path(entry)
        if image_path is None or not image_path.exists():
            warnings.append(f"Skipped {label}: source image not found")
            continue

        try:
            homography, solve_warnings = homography_for_entry(entry)
        except Exception as exc:
            warnings.append(f"Skipped {label}: homography invalid ({exc})")
            continue

        gps_pose = ensure_entry_gps_pose(project, entry)
        source_image = load_image_entry_source(project, entry)
        entry_warnings = list(dict.fromkeys([*entry.warnings, *solve_warnings]))
        sources.append(
            MosaicSource(
                label=label,
                source_image=source_image,
                homography_image_to_reference=homography,
                control_points=entry_points,
                clip_polygon=entry.clip_polygon,
                gps_pose=gps_pose,
                camera_pose=build_entry_camera_pose(
                    project,
                    entry,
                    source_image,
                    homography,
                    gps_pose,
                ),
                rms_error=entry.rms_error,
                warnings=tuple(entry_warnings),
            )
        )
        warnings.extend(entry_warnings)

    if not sources:
        raise ValueError("At least one image with four valid point pairs is required.")
    return sources, list(dict.fromkeys(warnings))


def project_reference_extents(project: ProjectData) -> tuple[Point2D, Point2D]:
    """Compute the extents of the reference data."""
    reference_path = project.resolve_reference_path()
    if reference_path is not None and reference_path.exists():
        if project.reference_type == "dxf":
            reference = load_dxf(reference_path)
            return reference.extents_min, reference.extents_max
        # 3D references
        reference_3d = None
        if project.reference_type == "e57":
            reference_3d = load_e57(reference_path)
        elif project.reference_type == "obj":
            reference_3d = load_obj(reference_path)
        if reference_3d is not None:
            reference_3d.working_plane = working_plane_from_dict(project.working_plane)
            if reference_3d.working_plane is None:
                raise ValueError(
                    "3D-Projekte benötigen eine gespeicherte Working Plane für CLI-Export."
                )
            return reference_plane_extents(reference_3d)

    # Fallback to control points
    reference_xy = np.asarray(
        [
            point.reference_xy
            for entry in project.images
            for point in entry.points
            if point.reference_xy
        ],
        dtype=np.float64,
    )
    if reference_xy.size == 0:
        raise ValueError("No reference extents available for export.")
    mins = reference_xy.min(axis=0)
    maxs = reference_xy.max(axis=0)
    return (float(mins[0]), float(mins[1])), (float(maxs[0]), float(maxs[1]))


def project_reference_segments(
    project: ProjectData,
) -> list[tuple[Point2D, Point2D]] | None:
    """Collect DXF segments for export overlay."""
    reference_path = project.resolve_reference_path()
    if project.reference_type != "dxf" or reference_path is None or not reference_path.exists():
        return None
    reference = load_dxf(reference_path)
    return [(segment.start, segment.end) for segment in reference.segments]


def paired_points(entry: ImageEntry) -> list[ControlPoint]:
    """Return all enabled point pairs for an entry."""
    return [point for point in entry.points if point.is_enabled_pair]


def _solve_entry_homography(entry: ImageEntry) -> HomographyResult:
    entry_points = paired_points(entry)
    return solve_planar_homography(
        [point.image_xy for point in entry_points if point.image_xy is not None],
        [point.reference_xy for point in entry_points if point.reference_xy is not None],
    )
