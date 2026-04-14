"""Shared CLI runtime helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from core.export import MosaicSource
from core.image import load_image
from core.lens import LensProfile, apply_lens_correction, lens_profile_from_dict
from core.pose import build_camera_pose, extract_gps_pose
from core.project import ImageEntry, Point2D, ProjectData
from core.reference2d import load_dxf
from core.reference3d import load_e57, load_obj, reference_plane_extents, working_plane_from_dict
from core.transform import HomographyResult, solve_planar_homography

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_project_file(project_path: Path) -> tuple[ProjectData | None, ValidationReport]:
    report = ValidationReport()
    try:
        project = ProjectData.load(project_path)
    except Exception as exc:
        report.errors.append(str(exc))
        return None, report

    project.ensure_image_entries()
    reference_path = project.resolve_reference_path()
    if reference_path is None:
        report.errors.append("Projekt hat keine Referenzdatei.")
    elif not reference_path.exists():
        report.errors.append(f"Referenzdatei nicht gefunden: {reference_path}")
    elif Path(project.reference_path).is_absolute():
        report.warnings.append(
            "Referenzpfad ist absolut; das Projekt ist dadurch schlechter portierbar."
        )

    exportable_sources = 0
    image_entries = [entry for entry in project.images if entry.path]
    if not image_entries:
        report.errors.append("Projekt hat keine Bilddateien.")

    for index, entry in enumerate(project.images):
        if not entry.path:
            continue

        label = image_label(entry, index)
        image_path = project.resolve_image_entry_path(entry)
        if image_path is None or not image_path.exists():
            report.errors.append(f"{label}: Bilddatei nicht gefunden: {image_path}")
            continue
        if Path(entry.path).is_absolute():
            report.warnings.append(
                f"{label}: absoluter Bildpfad; das Projekt ist dadurch schlechter portierbar."
            )

        paired_points = _paired_points(entry)
        if not paired_points:
            report.warnings.append(f"{label}: keine gepaarten Kontrollpunkte.")
            continue
        if len(paired_points) < 4:
            report.errors.append(f"{label}: mindestens vier Punktpaare erforderlich.")
            continue

        try:
            homography, solve_warnings = homography_for_entry(entry)
        except Exception as exc:
            report.errors.append(f"{label}: Homographie ungültig ({exc})")
            continue

        exportable_sources += 1
        report.warnings.extend(
            f"{label}: {warning}" for warning in solve_warnings if warning not in entry.warnings
        )
        _ = homography

    if exportable_sources == 0:
        report.errors.append("Projekt hat kein exportierbares Bild mit vier gültigen Punktpaaren.")

    if reference_path is not None and reference_path.exists():
        try:
            _ = project_reference_extents(project)
        except Exception as exc:
            report.errors.append(f"Referenz konnte nicht ausgewertet werden: {exc}")

    report.warnings = list(dict.fromkeys(report.warnings))
    report.errors = list(dict.fromkeys(report.errors))
    return project, report


def collect_project_export_sources(project: ProjectData) -> tuple[list[MosaicSource], list[str]]:
    project.ensure_image_entries()

    sources: list[MosaicSource] = []
    warnings: list[str] = []
    for index, entry in enumerate(project.images):
        if not entry.path:
            continue

        label = image_label(entry, index)
        paired_points = _paired_points(entry)
        if len(paired_points) < 4:
            warnings.append(f"Skipped {label}: needs at least four paired points")
            continue

        image_path = project.resolve_image_entry_path(entry)
        if image_path is None or not image_path.exists():
            warnings.append(f"Skipped {label}: source image not found")
            continue

        homography, solve_warnings = homography_for_entry(entry)
        gps_pose = entry.gps_pose if entry.gps_pose is not None else extract_gps_pose(image_path)
        source_image = load_image_entry_source(project, entry)
        entry_warnings = list(dict.fromkeys([*entry.warnings, *solve_warnings]))
        sources.append(
            MosaicSource(
                label=label,
                source_image=source_image,
                homography_image_to_reference=homography,
                control_points=paired_points,
                clip_polygon=entry.clip_polygon,
                gps_pose=gps_pose,
                camera_pose=build_entry_camera_pose(
                    project, entry, source_image, homography, gps_pose
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
    reference_path = project.resolve_reference_path()
    if reference_path is not None and reference_path.exists():
        if project.reference_type == "dxf":
            reference = load_dxf(reference_path)
            return reference.extents_min, reference.extents_max
        if project.reference_type == "e57":
            reference_3d = load_e57(reference_path)
        elif project.reference_type == "obj":
            reference_3d = load_obj(reference_path)
        else:
            reference_3d = None
        if reference_3d is not None:
            reference_3d.working_plane = working_plane_from_dict(project.working_plane)
            if reference_3d.working_plane is None:
                raise ValueError(
                    "3D-Projekte benötigen eine gespeicherte Working Plane für CLI-Export."
                )
            return reference_plane_extents(reference_3d)

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


def load_image_entry_source(project: ProjectData, entry: ImageEntry) -> np.ndarray:
    image_path = project.resolve_image_entry_path(entry)
    if image_path is None:
        raise ValueError("Image entry has no source path.")
    image = load_image(image_path)
    profile = lens_profile_from_correction(entry.lens_correction)
    if profile is None:
        return image
    return apply_lens_correction(image, profile)


def build_entry_camera_pose(
    project: ProjectData,
    entry: ImageEntry,
    source_image: np.ndarray,
    homography_image_to_reference: np.ndarray,
    gps_pose: dict[str, Any] | None,
) -> dict[str, object] | None:
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


def lens_profile_from_correction(correction: dict[str, object] | None) -> LensProfile | None:
    if not correction or not correction.get("applied"):
        return None

    payload = correction.get("profile")
    if not isinstance(payload, dict):
        return None

    try:
        return lens_profile_from_dict(payload)
    except (KeyError, TypeError, ValueError):
        return None


def homography_for_entry(entry: ImageEntry) -> tuple[np.ndarray, list[str]]:
    paired_points = _paired_points(entry)
    if len(paired_points) < 4:
        raise ValueError("at least four paired points are required")
    if entry.transform_matrix is not None:
        return np.asarray(entry.transform_matrix, dtype=np.float64), list(entry.warnings)

    result = _solve_entry_homography(entry)
    warnings = list(dict.fromkeys([*entry.warnings, *result.warnings]))
    if warnings == list(entry.warnings):
        warnings.append("Homography recomputed from stored control points")
    return result.matrix, warnings


def image_label(entry: ImageEntry, index: int) -> str:
    return Path(entry.path).stem or f"Image {index + 1}"


def _paired_points(entry: ImageEntry) -> list[Any]:
    return [point for point in entry.points if point.is_paired]


def _solve_entry_homography(entry: ImageEntry) -> HomographyResult:
    paired_points = _paired_points(entry)
    return solve_planar_homography(
        [point.image_xy for point in paired_points if point.image_xy is not None],
        [point.reference_xy for point in paired_points if point.reference_xy is not None],
    )
