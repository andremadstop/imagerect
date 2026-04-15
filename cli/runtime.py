"""Shared CLI runtime helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.export_sources import (
    homography_for_entry,
    image_label,
    paired_points,
    project_reference_extents,
)
from core.pose import crs_transform_available
from core.project import ProjectData


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
    if project.reference_crs_epsg is not None and not crs_transform_available():
        report.warnings.append(
            "CRS-Transformationen sind ohne das optionale Paket 'pyproj' deaktiviert."
        )

    exportable_sources = 0
    image_entries = [entry for entry in project.images if entry.path]
    if not image_entries:
        report.errors.append("Projekt hat keine Bilddateien.")

    for index, entry in enumerate(project.images):
        if not entry.path:
            continue

        label = image_label(project, entry, index)
        image_path = project.resolve_image_entry_path(entry)
        if image_path is None or not image_path.exists():
            report.errors.append(f"{label}: Bilddatei nicht gefunden: {image_path}")
            continue
        if Path(entry.path).is_absolute():
            report.warnings.append(
                f"{label}: absoluter Bildpfad; das Projekt ist dadurch schlechter portierbar."
            )

        entry_points = paired_points(entry)
        if not entry_points:
            report.warnings.append(f"{label}: keine gepaarten Kontrollpunkte.")
            continue
        if len(entry_points) < 4:
            report.errors.append(f"{label}: mindestens vier Punktpaare erforderlich.")
            continue

        try:
            _homography, solve_warnings = homography_for_entry(entry)
        except Exception as exc:
            report.errors.append(f"{label}: Homographie ungültig ({exc})")
            continue

        exportable_sources += 1
        report.warnings.extend(
            f"{label}: {warning}" for warning in solve_warnings if warning not in entry.warnings
        )

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
