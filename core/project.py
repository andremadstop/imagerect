"""Project model: save and load rectification sessions as JSON."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

Point2D = tuple[float, float]
Point3D = tuple[float, float, float]
ReferenceRoi = tuple[float, float, float, float]
UNIT_TO_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
    "ft": 304.8,
}
logger = logging.getLogger(__name__)


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


def _coerce_point3d(raw: Any) -> Point3D | None:
    if raw is None:
        return None
    values = [float(value) for value in raw]
    if len(values) != 3:
        raise ValueError("reference_world_point must contain exactly three values")
    return (values[0], values[1], values[2])


def _coerce_reference_world_points(raw: Any) -> dict[int, Point3D]:
    if not isinstance(raw, dict):
        return {}
    points: dict[int, Point3D] = {}
    for key, value in raw.items():
        point = _coerce_point3d(value)
        if point is not None:
            points[int(key)] = point
    return points


def unit_to_mm(units: str) -> float:
    return UNIT_TO_MM.get(units, 1.0)


def _copy_control_point(point: ControlPoint) -> ControlPoint:
    return ControlPoint(
        id=point.id,
        label=point.label,
        image_xy=point.image_xy,
        reference_xy=point.reference_xy,
        enabled=point.enabled,
        locked=point.locked,
        residual=point.residual,
        residual_vector=point.residual_vector,
    )


@dataclass(slots=True)
class ControlPoint:
    """A single control point pair row."""

    id: int
    label: str = ""
    image_xy: Point2D | None = None
    reference_xy: Point2D | None = None
    enabled: bool = True
    locked: bool = False
    residual: float | None = None
    residual_vector: Point2D | None = None

    @property
    def is_paired(self) -> bool:
        return self.image_xy is not None and self.reference_xy is not None

    @property
    def is_enabled_pair(self) -> bool:
        return self.enabled and self.is_paired


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
    mosaic_feather_radius_px: int = 0


@dataclass(slots=True)
class ImageEntry:
    path: str = ""
    lens_correction: dict[str, Any] | None = None
    clip_polygon: list[Point2D] | None = None
    points: list[ControlPoint] = field(default_factory=list)
    reference_world_points: dict[int, Point3D] = field(default_factory=dict)
    gps_pose: dict[str, Any] | None = None
    rms_error: float | None = None
    transform_matrix: list[list[float]] | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ProjectData:
    """Top-level project data for save/load and undo snapshots."""

    name: str = "Untitled"
    image_path: str = ""
    images: list[ImageEntry] = field(default_factory=list)
    active_image_index: int = 0
    reference_path: str = ""
    reference_type: str = "dxf"
    reference_crs_epsg: int | None = None
    points: list[ControlPoint] = field(default_factory=list)
    export_settings: ExportSettings = field(default_factory=ExportSettings)
    units: str = "mm"
    working_plane: dict[str, Any] | None = None
    lens_correction: dict[str, Any] | None = None
    clip_polygon: list[Point2D] | None = None
    reference_world_points: dict[int, Point3D] = field(default_factory=dict)
    reference_roi: ReferenceRoi | None = None
    rms_error: float | None = None
    transform_matrix: list[list[float]] | None = None
    warnings: list[str] = field(default_factory=list)
    created: str = field(default_factory=_now_iso)
    modified: str = field(default_factory=_now_iso)
    _next_id: int = field(default=1, repr=False)
    _project_file: str | None = field(default=None, repr=False, compare=False)

    def touch(self) -> None:
        self.modified = _now_iso()

    def clear_solver_state(self) -> None:
        self.rms_error = None
        self.transform_matrix = None
        self.warnings = []
        for point in self.points:
            point.residual = None
            point.residual_vector = None
        self.sync_to_active_image()

    def clear_reference_alignment(self) -> None:
        self.ensure_image_entries()
        if self.images:
            for entry in self.images:
                entry.reference_world_points = {}
                entry.rms_error = None
                entry.transform_matrix = None
                entry.warnings = []
                for point in entry.points:
                    point.reference_xy = None
                    point.residual = None
                    point.residual_vector = None
            self.sync_from_active_image()
        else:
            self.reference_world_points = {}
            self.clear_solver_state()
            for point in self.points:
                point.reference_xy = None
        self.touch()

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
        self.reference_world_points.pop(point_id, None)
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
        return [point for point in self.points if point.is_enabled_pair]

    @property
    def project_file(self) -> Path | None:
        if self._project_file is None:
            return None
        return Path(self._project_file)

    @property
    def project_dir(self) -> Path | None:
        project_file = self.project_file
        if project_file is None:
            return None
        return project_file.parent

    def set_project_file(self, path: Path | None) -> None:
        self._project_file = str(path.resolve()) if path is not None else None

    def validate_asset_paths(self, project_file: Path) -> None:
        self.set_project_file(project_file)
        for field_name, raw_path in [
            ("image_path", self.image_path),
            ("reference_path", self.reference_path),
            *[(f"images[{index}].path", entry.path) for index, entry in enumerate(self.images)],
        ]:
            _validate_project_asset_path(raw_path, project_file, field_name)

    def resolve_asset_path(self, raw_path: str) -> Path:
        return _resolve_project_asset_path(raw_path, self.project_file)

    def resolve_active_image_path(self) -> Path | None:
        if not self.image_path:
            return None
        return self.resolve_asset_path(self.image_path)

    def resolve_reference_path(self) -> Path | None:
        if not self.reference_path:
            return None
        return self.resolve_asset_path(self.reference_path)

    def resolve_image_entry_path(self, entry: ImageEntry) -> Path | None:
        if not entry.path:
            return None
        return self.resolve_asset_path(entry.path)

    def clone(self) -> ProjectData:
        self.sync_to_active_image()
        clone = self.from_dict(self.to_dict())
        clone._project_file = self._project_file
        return clone

    def ensure_image_entries(self) -> None:
        if self.images:
            self.active_image_index = max(0, min(self.active_image_index, len(self.images) - 1))
            return
        if (
            self.image_path
            or self.points
            or self.lens_correction is not None
            or self.clip_polygon is not None
        ):
            self.images = [
                ImageEntry(
                    path=self.image_path,
                    lens_correction=self.lens_correction,
                    clip_polygon=list(self.clip_polygon) if self.clip_polygon is not None else None,
                    points=[_copy_control_point(point) for point in self.points],
                    reference_world_points=dict(self.reference_world_points),
                    rms_error=self.rms_error,
                    transform_matrix=self.transform_matrix,
                    warnings=list(self.warnings),
                )
            ]
            self.active_image_index = 0

    def sync_to_active_image(self) -> None:
        self.ensure_image_entries()
        if not self.images:
            return
        entry = self.images[self.active_image_index]
        entry.path = self.image_path
        entry.lens_correction = self.lens_correction
        entry.clip_polygon = list(self.clip_polygon) if self.clip_polygon is not None else None
        entry.points = [_copy_control_point(point) for point in self.points]
        entry.reference_world_points = dict(self.reference_world_points)
        entry.rms_error = self.rms_error
        entry.transform_matrix = self.transform_matrix
        entry.warnings = list(self.warnings)

    def sync_from_active_image(self) -> None:
        self.ensure_image_entries()
        if not self.images:
            return
        self.active_image_index = max(0, min(self.active_image_index, len(self.images) - 1))
        entry = self.images[self.active_image_index]
        self.image_path = entry.path
        self.lens_correction = entry.lens_correction
        self.clip_polygon = list(entry.clip_polygon) if entry.clip_polygon is not None else None
        self.points = [_copy_control_point(point) for point in entry.points]
        self.reference_world_points = dict(entry.reference_world_points)
        self.rms_error = entry.rms_error
        self.transform_matrix = entry.transform_matrix
        self.warnings = list(entry.warnings)

    def to_dict(self) -> dict[str, Any]:
        self.sync_to_active_image()
        payload = asdict(self)
        payload["_next_id"] = self._next_id
        payload.pop("_project_file", None)
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
                    enabled=bool(raw_point.get("enabled", True)),
                    locked=bool(raw_point.get("locked", False)),
                    residual=(
                        float(raw_point["residual"])
                        if raw_point.get("residual") is not None
                        else None
                    ),
                    residual_vector=_coerce_point(raw_point.get("residual_vector")),
                )
            )

        images: list[ImageEntry] = []
        for raw_image in payload.get("images", []):
            image_points: list[ControlPoint] = []
            for raw_point in raw_image.get("points", []):
                image_points.append(
                    ControlPoint(
                        id=int(raw_point["id"]),
                        label=str(raw_point.get("label", "")),
                        image_xy=_coerce_point(raw_point.get("image_xy")),
                        reference_xy=_coerce_point(raw_point.get("reference_xy")),
                        enabled=bool(raw_point.get("enabled", True)),
                        locked=bool(raw_point.get("locked", False)),
                        residual=(
                            float(raw_point["residual"])
                            if raw_point.get("residual") is not None
                            else None
                        ),
                        residual_vector=_coerce_point(raw_point.get("residual_vector")),
                    )
                )
            images.append(
                ImageEntry(
                    path=str(raw_image.get("path", "")),
                    lens_correction=raw_image.get("lens_correction"),
                    clip_polygon=_coerce_point_list(raw_image.get("clip_polygon")),
                    points=image_points,
                    reference_world_points=_coerce_reference_world_points(
                        raw_image.get("reference_world_points")
                    ),
                    gps_pose=raw_image.get("gps_pose"),
                    rms_error=(
                        float(raw_image["rms_error"])
                        if raw_image.get("rms_error") is not None
                        else None
                    ),
                    transform_matrix=raw_image.get("transform_matrix"),
                    warnings=[str(value) for value in raw_image.get("warnings", [])],
                )
            )

        export_settings = ExportSettings(**payload.get("export_settings", {}))
        project = cls(
            name=str(payload.get("name", "Untitled")),
            image_path=str(payload.get("image_path", "")),
            images=images,
            active_image_index=int(payload.get("active_image_index", 0)),
            reference_path=str(payload.get("reference_path", "")),
            reference_type=str(payload.get("reference_type", "dxf")),
            reference_crs_epsg=(
                int(payload["reference_crs_epsg"])
                if payload.get("reference_crs_epsg") is not None
                else None
            ),
            points=points,
            export_settings=export_settings,
            units=str(payload.get("units", "mm")),
            working_plane=payload.get("working_plane"),
            lens_correction=payload.get("lens_correction"),
            clip_polygon=_coerce_point_list(payload.get("clip_polygon")),
            reference_world_points=_coerce_reference_world_points(
                payload.get("reference_world_points")
            ),
            reference_roi=_coerce_reference_roi(payload.get("reference_roi")),
            rms_error=(
                float(payload["rms_error"]) if payload.get("rms_error") is not None else None
            ),
            transform_matrix=payload.get("transform_matrix"),
            warnings=[str(value) for value in payload.get("warnings", [])],
            created=str(payload.get("created", _now_iso())),
            modified=str(payload.get("modified", _now_iso())),
        )
        if project.images:
            project.sync_from_active_image()
        else:
            project.ensure_image_entries()
        max_point_id = max(
            (
                point.id
                for point in [*points, *(point for image in images for point in image.points)]
            ),
            default=0,
        )
        project._next_id = int(payload.get("_next_id", max_point_id + 1))
        return project

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.sync_to_active_image()
        self.touch()
        payload = self.to_dict()
        _relativize_project_asset_paths(payload, self, path)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        self.set_project_file(path)

    @classmethod
    def load(cls, path: Path) -> ProjectData:
        project = cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        project.validate_asset_paths(path)
        return project


def _resolve_project_asset_path(raw_path: str, project_file: Path | None) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute() or project_file is None:
        return candidate
    return (project_file.parent / candidate).resolve()


def _validate_project_asset_path(raw_path: str, project_file: Path, field_name: str) -> None:
    if not raw_path:
        return

    candidate = Path(raw_path)
    if candidate.is_absolute():
        logger.warning(
            "Absolute path retained in project file | project=%s | field=%s | path=%s",
            project_file,
            field_name,
            candidate,
        )
        return

    project_dir = project_file.parent.resolve()
    resolved_parent = (project_dir / candidate.parent).resolve(strict=False)
    resolved_target = (project_dir / candidate).resolve(strict=False)
    if not resolved_parent.is_relative_to(project_dir) or not resolved_target.is_relative_to(
        project_dir
    ):
        raise ValueError(f"Projektpfad verlässt das Projektverzeichnis ({field_name}): {raw_path}")


def _relativize_project_asset_paths(
    payload: dict[str, Any],
    project: ProjectData,
    target_project_file: Path,
) -> None:
    payload["image_path"] = _serialized_asset_path(
        project.image_path,
        project_file=project.project_file,
        target_project_file=target_project_file,
    )
    payload["reference_path"] = _serialized_asset_path(
        project.reference_path,
        project_file=project.project_file,
        target_project_file=target_project_file,
    )
    for raw_image, entry in zip(payload.get("images", []), project.images, strict=False):
        raw_image["path"] = _serialized_asset_path(
            entry.path,
            project_file=project.project_file,
            target_project_file=target_project_file,
        )


def _serialized_asset_path(
    raw_path: str,
    *,
    project_file: Path | None,
    target_project_file: Path,
) -> str:
    if not raw_path:
        return raw_path

    resolved = _resolve_project_asset_path(raw_path, project_file)
    if not resolved.is_absolute():
        return raw_path

    target_dir = target_project_file.parent.resolve()
    try:
        return resolved.relative_to(target_dir).as_posix()
    except ValueError:
        return str(resolved)
