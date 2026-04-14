"""2D reference loading and snapping from DXF files via ezdxf."""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import Any

import ezdxf
import numpy as np
from ezdxf.entities import DXFGraphic

logger = logging.getLogger(__name__)
Point2D = tuple[float, float]


@dataclass(slots=True)
class LayerInfo:
    name: str
    color: int
    visible: bool = True


@dataclass(slots=True)
class Segment:
    start: Point2D
    end: Point2D
    layer: str = "0"


@dataclass(slots=True)
class Reference2D:
    layers: list[LayerInfo] = field(default_factory=list)
    segments: list[Segment] = field(default_factory=list)
    units: str = "mm"
    crs_epsg: int | None = None
    extents_min: Point2D = (0.0, 0.0)
    extents_max: Point2D = (0.0, 0.0)
    vertices: list[Point2D] = field(default_factory=list)

    @property
    def layer_names(self) -> list[str]:
        return [layer.name for layer in self.layers]


def load_dxf(path: str | Path) -> Reference2D:
    """Load a DXF file and extract line-based display geometry."""

    reference_path = Path(path)
    if not reference_path.exists():
        raise FileNotFoundError(f"Reference not found: {reference_path}")
    if reference_path.suffix.lower() == ".dwg":
        logger.warning("DWG input rejected | path=%s", reference_path)
        raise ValueError("DWG input is not supported directly in Phase 1. Convert it to DXF first.")

    logger.info("Loading 2D reference | path=%s", reference_path)
    document = ezdxf.readfile(str(reference_path))
    modelspace = document.modelspace()
    layers = [
        LayerInfo(
            name=layer.dxf.name,
            color=int(layer.color),
            visible=not layer.is_off() and not layer.is_frozen(),
        )
        for layer in document.layers
    ]

    segments: list[Segment] = []
    vertices: list[Point2D] = []
    for entity in modelspace:
        _extract_entity(entity, segments, vertices)

    extents_min, extents_max = _compute_extents(vertices)
    units = _units_from_code(int(document.header.get("$INSUNITS", 0)))
    crs_epsg = _extract_crs_epsg(document, reference_path)
    logger.info(
        "Loaded 2D reference | path=%s | layers=%d | segments=%d | units=%s | epsg=%s",
        reference_path,
        len(layers),
        len(segments),
        units,
        crs_epsg,
    )
    return Reference2D(
        layers=layers,
        segments=segments,
        units=units,
        crs_epsg=crs_epsg,
        extents_min=extents_min,
        extents_max=extents_max,
        vertices=_deduplicate_points(vertices),
    )


def snap_to_vertex(
    reference: Reference2D,
    x: float,
    y: float,
    tolerance: float = 5.0,
) -> Point2D | None:
    """Snap to the closest known vertex within a world-coordinate tolerance."""

    best_match: Point2D | None = None
    best_distance = tolerance
    for vertex_x, vertex_y in reference.vertices:
        distance = math.hypot(vertex_x - x, vertex_y - y)
        if distance <= best_distance:
            best_distance = distance
            best_match = (vertex_x, vertex_y)
    return best_match


def _extract_entity(
    entity: DXFGraphic,
    segments: list[Segment],
    vertices: list[Point2D],
) -> None:
    dxftype = entity.dxftype()
    layer = str(entity.dxf.get("layer", "0"))

    if dxftype == "LINE":
        start = (float(entity.dxf.start.x), float(entity.dxf.start.y))
        end = (float(entity.dxf.end.x), float(entity.dxf.end.y))
        segments.append(Segment(start=start, end=end, layer=layer))
        vertices.extend([start, end])
        return

    if dxftype in {"LWPOLYLINE", "POLYLINE"}:
        if dxftype == "LWPOLYLINE":
            points = [(float(x), float(y)) for x, y, *_ in entity.get_points("xyseb")]
            is_closed = bool(entity.closed)
        else:
            points = [
                (float(vertex.dxf.location.x), float(vertex.dxf.location.y))
                for vertex in entity.vertices
            ]
            is_closed = bool(entity.is_closed)

        for start, end in pairwise(points):
            segments.append(Segment(start=start, end=end, layer=layer))
        if is_closed and len(points) > 1:
            segments.append(Segment(start=points[-1], end=points[0], layer=layer))
        vertices.extend(points)
        return

    if dxftype == "CIRCLE":
        center = np.array((float(entity.dxf.center.x), float(entity.dxf.center.y)))
        radius = float(entity.dxf.radius)
        _append_arc_segments(
            segments,
            vertices,
            center,
            radius,
            0.0,
            360.0,
            layer,
        )
        return

    if dxftype == "ARC":
        center = np.array((float(entity.dxf.center.x), float(entity.dxf.center.y)))
        radius = float(entity.dxf.radius)
        start_angle = float(entity.dxf.start_angle)
        end_angle = float(entity.dxf.end_angle)
        _append_arc_segments(
            segments,
            vertices,
            center,
            radius,
            start_angle,
            end_angle,
            layer,
        )
        return

    if dxftype == "INSERT":
        try:
            for virtual_entity in entity.virtual_entities():
                _extract_entity(virtual_entity, segments, vertices)
        except Exception:
            return


def _append_arc_segments(
    segments: list[Segment],
    vertices: list[Point2D],
    center: np.ndarray,
    radius: float,
    start_angle: float,
    end_angle: float,
    layer: str,
    sample_count: int = 32,
) -> None:
    normalized_end = end_angle
    if normalized_end <= start_angle:
        normalized_end += 360.0
    angles = np.linspace(math.radians(start_angle), math.radians(normalized_end), sample_count)
    arc_points: list[Point2D] = []
    for angle in angles:
        point = center + radius * np.array((math.cos(angle), math.sin(angle)))
        arc_points.append((float(point[0]), float(point[1])))
    for start, end in pairwise(arc_points):
        segments.append(Segment(start=start, end=end, layer=layer))
    vertices.extend(arc_points)


def _compute_extents(vertices: Iterable[Point2D]) -> tuple[Point2D, Point2D]:
    vertex_list = list(vertices)
    if not vertex_list:
        return (0.0, 0.0), (0.0, 0.0)
    xs = [vertex[0] for vertex in vertex_list]
    ys = [vertex[1] for vertex in vertex_list]
    return (min(xs), min(ys)), (max(xs), max(ys))


def _deduplicate_points(points: Iterable[Point2D], precision: int = 6) -> list[Point2D]:
    seen: set[Point2D] = set()
    deduplicated: list[Point2D] = []
    for point in points:
        key = (round(point[0], precision), round(point[1], precision))
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append((float(key[0]), float(key[1])))
    return deduplicated


def _units_from_code(code: int) -> str:
    units_map = {
        0: "unitless",
        1: "in",
        2: "ft",
        4: "mm",
        5: "cm",
        6: "m",
    }
    return units_map.get(code, "mm")


def _extract_crs_epsg(document: Any, path: Path) -> int | None:
    for value in _iter_document_metadata_strings(document):
        match = re.search(r"\bEPSG[:= ]+(\d{4,6})\b", value, re.IGNORECASE)
        if match is not None:
            return int(match.group(1))

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        logger.warning("Could not scan DXF text for EPSG metadata | path=%s", path)
        return None

    match = re.search(r"\bEPSG[:= ]+(\d{4,6})\b", text, re.IGNORECASE)
    if match is None:
        return None
    return int(match.group(1))


def _iter_document_metadata_strings(document: Any) -> Iterable[str]:
    for entity in document.modelspace():
        xdata = getattr(entity, "xdata", None)
        if xdata is None:
            continue
        for tags in getattr(xdata, "data", {}).values():
            for tag in tags:
                value = getattr(tag, "value", None)
                if isinstance(value, str):
                    yield value
