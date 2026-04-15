"""Headless export command."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from cli.common import configure_cli_logging
from cli.runtime import (
    project_reference_extents,
    validate_project_file,
)
from core.export import (
    DEFAULT_BIGTIFF_THRESHOLD_BYTES,
    export_mosaic_image,
    export_rectified_image,
)
from core.export_sources import collect_project_export_sources, project_reference_segments


class OutputFormat(StrEnum):
    tiff = "tiff"
    bigtiff = "bigtiff"
    png = "png"
    jpeg = "jpeg"


def export_command(
    project: Annotated[
        Path,
        typer.Argument(..., exists=True, dir_okay=False, help="Saved .imagerect.json project"),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            dir_okay=False,
            help="Override the export target path without suffix",
        ),
    ] = None,
    dpi: Annotated[
        float | None,
        typer.Option("--dpi", min=1.0, help="Override project DPI"),
    ] = None,
    output_format: Annotated[
        OutputFormat | None,
        typer.Option("--format", "-f", case_sensitive=False, help="Override the output format"),
    ] = None,
    quiet: Annotated[bool, typer.Option("--quiet", help="Only print errors")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", help="Enable verbose logging")] = False,
) -> None:
    configure_cli_logging(quiet=quiet, verbose=verbose)
    project_data, report = validate_project_file(project)
    for warning in report.warnings:
        if not quiet:
            typer.echo(f"warning: {warning}", err=True)
    if project_data is None or not report.ok:
        for error in report.errors:
            typer.echo(f"error: {error}", err=True)
        raise typer.Exit(code=1)

    settings = project_data.export_settings
    if dpi is not None:
        settings.dpi = dpi
    if output_format is not None:
        settings.output_format = output_format.value

    sources, export_warnings = collect_project_export_sources(project_data)
    reference_extents = project_reference_extents(project_data)
    reference_segments = project_reference_segments(project_data)
    target_path = (
        output if output is not None else project.parent / f"{project_data.name}_rectified"
    )

    if len(sources) > 1:
        result = export_mosaic_image(
            sources=sources,
            output_path=target_path,
            pixel_size=settings.pixel_size,
            units=project_data.units,
            output_format=settings.output_format,
            dpi=settings.dpi,
            bit_depth=settings.bit_depth,
            resampling=settings.resampling,
            compression=settings.compression,
            clip_to_hull=settings.clip_to_hull,
            reference_roi=project_data.reference_roi if settings.use_reference_roi else None,
            write_metadata_json=settings.include_json_sidecar,
            embed_in_tiff=settings.embed_in_tiff,
            multi_layer=settings.multi_layer,
            reference_segments=reference_segments,
            reference_extents=reference_extents,
            project_name=project_data.name,
            warnings=export_warnings,
            blend_radius_px=settings.mosaic_feather_radius_px,
        )
    else:
        source = sources[0]
        result = export_rectified_image(
            source_image=source.source_image,
            homography_image_to_reference=source.homography_image_to_reference,
            control_points=source.control_points,
            output_path=target_path,
            pixel_size=settings.pixel_size,
            units=project_data.units,
            output_format=settings.output_format,
            dpi=settings.dpi,
            bit_depth=settings.bit_depth,
            resampling=settings.resampling,
            compression=settings.compression,
            clip_to_hull=settings.clip_to_hull,
            clip_polygon=source.clip_polygon if settings.use_clip_polygon else None,
            reference_roi=project_data.reference_roi if settings.use_reference_roi else None,
            write_metadata_json=settings.include_json_sidecar,
            embed_in_tiff=settings.embed_in_tiff,
            bigtiff_threshold_bytes=DEFAULT_BIGTIFF_THRESHOLD_BYTES,
            multi_layer=settings.multi_layer,
            reference_segments=reference_segments,
            reference_extents=reference_extents,
            project_name=project_data.name,
            rms_error=source.rms_error,
            warnings=list(dict.fromkeys([*export_warnings, *source.warnings])),
            gps_pose=source.gps_pose,
            camera_pose=source.camera_pose,
        )

    if not quiet:
        typer.echo(f"Exported image: {result.image_path}")
        if result.metadata_path.exists():
            typer.echo(f"Metadata: {result.metadata_path}")
