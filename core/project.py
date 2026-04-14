"""Project model: save and load rectification sessions as JSON."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Point2D = tuple[float, float]
ReferenceRoi = tuple[float, float, float, float]
UNIT_TO_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
    "ft": 304.8,
}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _coerce_point(raw: Any) -> Point2D | None:
    if raw is None:
        return None
    return (float(raw[0]), float(raw[1]))


def _coerce_point_list(raw: Any) -> list[Point2D] | None:
    if raw is None:
        return None
    points: list[Point2D] = []
    for value in raw:
        point = _coerce_point(value)
        if point is not None:
            points.append(point)
    return points or None


def _coerce_reference_roi(raw: Any) -> ReferenceRoi | None:
    if raw is None:
        return None
    values = [float(value) for value in raw]
    if len(values) != 4:
        raise ValueError("reference_roi must contain exactly four values")
    return (values[0], values[1], values[2], values[3])


def unit_to_mm(units: str) -> float:
    return UNIT_TO_MM.get(units, 1.0)


@dataclass(slots=True)
class ControlPoint:
    """A single control point pair row."""

    id: int
    label: str = ""
    image_xy: Point2D | None = None
    reference_xy: Point2D | None = None
    locked: bool = False
    residual: float | None = None
    residual_vector: Point2D | None = None

    @property
    def is_paired(self) -> bool:
        return self.image_xy is not None and self.reference_xy is not None


@dataclass(slots=True)
class ExportSettings:
    pixel_size: float = 1.0
    scale_denominator: float = 11.811023622047244
    dpi: float = 300.0
    resampling: str = "bilinear"
    output_format: str = "tiff"
    bit_depth: int = 8
    compression: str = "none"
    multi_layer: bool = False
    use_clip_polygon: bool = True
    use_reference_roi: bool = True
    clip_to_hull: bool = False
    include_json_sidecar: bool = True
    embed_in_tiff: bool = True


@dataclass(slots=True)
class ProjectData:
    """Top-level project data for save/load and undo snapshots."""

    name: str = "Untitled"
    image_path: str = ""
    reference_path: str = ""
    reference_type: str = "dxf"
    points: list[ControlPoint] = field(default_factory=list)
    export_settings: ExportSettings = field(default_factory=ExportSettings)
    units: str = "mm"
    working_plane: dict[str, Any] | None = None
    lens_correction: dict[str, Any] | None = None
    clip_polygon: list[Point2D] | None = None
    reference_roi: ReferenceRoi | None = None
    rms_error: float | None = None
    transform_matrix: list[list[float]] | None = None
    warnings: list[str] = field(default_factory=list)
    created: str = field(default_factory=_now_iso)
    modified: str = field(default_factory=_now_iso)
    _next_id: int = field(default=1, repr=False)

    def touch(self) -> None:
        self.modified = _now_iso()

    def clear_solver_state(self) -> None:
        self.rms_error = None
        self.transform_matrix = None
        self.warnings = []
        for point in self.points:
            point.residual = None
            point.residual_vector = None

    def next_label(self) -> str:
        return f"P{self._next_id:02d}"

    def add_point(self, label: str | None = None) -> ControlPoint:
        point = ControlPoint(id=self._next_id, label=label or self.next_label())
        self._next_id += 1
        self.points.append(point)
        self.touch()
        return point

    def get_point(self, point_id: int) -> ControlPoint | None:
        return next((point for point in self.points if point.id == point_id), None)

    def remove_point(self, point_id: int) -> None:
        self.points = [point for point in self.points if point.id != point_id]
        self.touch()

    def move_point(self, point_id: int, offset: int) -> None:
        index = next(
            (idx for idx, point in enumerate(self.points) if point.id == point_id),
            None,
        )
        if index is None:
            return
        new_index = max(0, min(len(self.points) - 1, index + offset))
        if new_index == index:
            return
        point = self.points.pop(index)
        self.points.insert(new_index, point)
        self.touch()

    def paired_points(self) -> list[ControlPoint]:
        return [point for point in self.points if point.is_paired]

    def clone(self) -> ProjectData:
        return self.from_dict(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["_next_id"] = self._next_id
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProjectData:
        points: list[ControlPoint] = []
        for raw_point in payload.get("points", []):
            points.append(
                ControlPoint(
                    id=int(raw_point["id"]),
                    label=str(raw_point.get("label", "")),
                    image_xy=_coerce_point(raw_point.get("image_xy")),
                    reference_xy=_coerce_point(raw_point.get("reference_xy")),
                    locked=bool(raw_point.get("locked", False)),
                    residual=(
                        float(raw_point["residual"])
                        if raw_point.get("residual") is not None
                        else None
                    ),
                    residual_vector=_coerce_point(raw_point.get("residual_vector")),
                )
            )

        export_settings = ExportSettings(**payload.get("export_settings", {}))
        project = cls(
            name=str(payload.get("name", "Untitled")),
            image_path=str(payload.get("image_path", "")),
            reference_path=str(payload.get("reference_path", "")),
            reference_type=str(payload.get("reference_type", "dxf")),
            points=points,
            export_settings=export_settings,
            units=str(payload.get("units", "mm")),
            working_plane=payload.get("working_plane"),
            lens_correction=payload.get("lens_correction"),
            clip_polygon=_coerce_point_list(payload.get("clip_polygon")),
            reference_roi=_coerce_reference_roi(payload.get("reference_roi")),
            rms_error=(
                float(payload["rms_error"]) if payload.get("rms_error") is not None else None
            ),
            transform_matrix=payload.get("transform_matrix"),
            warnings=[str(value) for value in payload.get("warnings", [])],
            created=str(payload.get("created", _now_iso())),
            modified=str(payload.get("modified", _now_iso())),
        )
        project._next_id = int(payload.get("_next_id", max((p.id for p in points), default=0) + 1))
        return project

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.touch()
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: Path) -> ProjectData:
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
