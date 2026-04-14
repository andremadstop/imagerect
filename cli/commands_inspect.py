"""File inspection command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import ezdxf
import typer
from PIL import Image

from cli.common import configure_cli_logging, echo_json
from core.lens import read_exif
from core.pose import extract_gps_pose
from core.reference2d import load_dxf
from core.reference3d import load_e57, load_obj


def inspect_command(
    path: Annotated[
        Path,
        typer.Argument(..., exists=True, dir_okay=False, help="Image, DXF, E57, or OBJ file"),
    ],
    quiet: Annotated[bool, typer.Option("--quiet", help="Reduce log output")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", help="Enable verbose logging")] = False,
) -> None:
    configure_cli_logging(quiet=quiet, verbose=verbose)
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".ppm"}:
        echo_json(_inspect_image(path))
        return
    if suffix == ".dxf":
        echo_json(_inspect_dxf(path))
        return
    if suffix == ".e57":
        echo_json(_inspect_e57(path))
        return
    if suffix == ".obj":
        echo_json(_inspect_obj(path))
        return
    typer.echo(f"error: Unsupported inspect target: {path.suffix}", err=True)
    raise typer.Exit(code=1)


def _inspect_image(path: Path) -> dict[str, Any]:
    exif = read_exif(path)
    with Image.open(path) as image:
        width, height = image.size
        color_mode = image.mode
    return {
        "type": "image",
        "path": str(path.resolve()),
        "width": width,
        "height": height,
        "color_mode": color_mode,
        "camera": {
            "make": exif.get("Make"),
            "model": exif.get("Model"),
            "datetime": exif.get("DateTimeOriginal") or exif.get("DateTime"),
        },
        "gps_pose": extract_gps_pose(path),
        "exif_keys": sorted(exif.keys()),
    }


def _inspect_dxf(path: Path) -> dict[str, Any]:
    reference = load_dxf(path)
    return {
        "type": "dxf",
        "path": str(path.resolve()),
        "units": reference.units,
        "crs_epsg": reference.crs_epsg,
        "layers": [layer.name for layer in reference.layers],
        "entity_counts": _dxf_entity_counts(path),
        "segment_count": len(reference.segments),
        "vertex_count": len(reference.vertices),
        "bounds_min": [reference.extents_min[0], reference.extents_min[1]],
        "bounds_max": [reference.extents_max[0], reference.extents_max[1]],
    }


def _inspect_e57(path: Path) -> dict[str, Any]:
    reference = load_e57(path)
    point_count = 0 if reference.points is None else len(reference.points)
    return {
        "type": "e57",
        "path": str(path.resolve()),
        "units": reference.units,
        "point_count": point_count,
        "bounds_min": None
        if reference.bounds_min is None
        else reference.bounds_min.astype(float).tolist(),
        "bounds_max": None
        if reference.bounds_max is None
        else reference.bounds_max.astype(float).tolist(),
    }


def _inspect_obj(path: Path) -> dict[str, Any]:
    reference = load_obj(path)
    vertex_count = 0 if reference.vertices is None else len(reference.vertices)
    face_count = 0 if reference.faces is None else len(reference.faces)
    return {
        "type": "obj",
        "path": str(path.resolve()),
        "units": reference.units,
        "vertex_count": vertex_count,
        "face_count": face_count,
        "bounds_min": None
        if reference.bounds_min is None
        else reference.bounds_min.astype(float).tolist(),
        "bounds_max": None
        if reference.bounds_max is None
        else reference.bounds_max.astype(float).tolist(),
    }


def _dxf_entity_counts(path: Path) -> dict[str, int]:
    document = ezdxf.readfile(str(path))
    counts: dict[str, int] = {}
    for entity in document.modelspace():
        dxftype = entity.dxftype()
        counts[dxftype] = counts.get(dxftype, 0) + 1
    return counts
