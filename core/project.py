"""Project model: save and load rectification sessions as JSON."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field, fields
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
MAX_PROJECT_FILE_BYTES = 16_777_216  # 16 MB is plenty for a control-point JSON
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return the current time in ISO 8601 format."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _coerce_point(raw: Any) -> Point2D | None:
    if raw is None:
        return None
    try:
        return (float(raw[0]), float(raw[1]))
    except (IndexError, TypeError, ValueError):
        return None


def _coerce_point_list(raw: Any) -> list[Point2D] | None:
    if not isinstance(raw, list):
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
    try:
        values = [float(value) for value in raw]
        if len(values) != 4:
            return None
        return (values[0], values[1], values[2], values[3])
    except (TypeError, ValueError):
        return None


def _coerce_point3d(raw: Any) -> Point3D | None:
    if raw is None:
        return None
    try:
        values = [float(value) for value in raw]
        if len(values) != 3:
            return None
        return (values[0], values[1], values[2])
    except (TypeError, ValueError):
        return None


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
    """Return the conversion factor from the given unit to millimeters."""
    return UNIT_TO_MM.get(units, 1.0)


@dataclass(slots=True)
class ControlPoint:
    """A single control point pair linking image coordinates to reference coordinates."""

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
        """Return True if both image and reference coordinates are set."""
        return self.image_xy is not None and self.reference_xy is not None

    @property
    def is_enabled_pair(self) -> bool:
        """Return True if the point is enabled and has both coordinates set."""
        return self.enabled and self.is_paired

    def clone(self) -> ControlPoint:
        """Return a deep copy of this control point."""
        return ControlPoint(
            id=self.id,
            label=self.label,
            image_xy=self.image_xy,
            reference_xy=self.reference_xy,
            enabled=self.enabled,
            locked=self.locked,
            residual=self.residual,
            residual_vector=self.residual_vector,
        )


@dataclass(slots=True)
class ExportSettings:
    """Settings for the rectification export process."""

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
    """Represents a single image and its specific rectification data."""

    path: str = ""
    lens_correction: dict[str, Any] | None = None
    clip_polygon: list[Point2D] | None = None
    points: list[ControlPoint] = field(default_factory=list)
    reference_world_points: dict[int, Point3D] = field(default_factory=dict)
    gps_pose: dict[str, Any] | None = None
    rms_error: float | None = None
    transform_matrix: list[list[float]] | None = None
    warnings: list[str] = field(default_factory=list)

    def clone(self) -> ImageEntry:
        """Return a deep copy of this image entry."""
        return ImageEntry(
            path=self.path,
            lens_correction=(
                dict(self.lens_correction) if self.lens_correction is not None else None
            ),
            clip_polygon=(list(self.clip_polygon) if self.clip_polygon is not None else None),
            points=[p.clone() for p in self.points],
            reference_world_points=dict(self.reference_world_points),
            gps_pose=dict(self.gps_pose) if self.gps_pose is not None else None,
            rms_error=self.rms_error,
            transform_matrix=(
                [list(row) for row in self.transform_matrix]
                if self.transform_matrix is not None
                else None
            ),
            warnings=list(self.warnings),
        )


@dataclass(slots=True)
class ProjectData:
    """
    Top-level project data for save/load and undo snapshots.
    This class acts as the central data model. Image-specific data is stored in 'images'.
    The 'active_image_index' determines which entry is currently being edited.
    """

    name: str = "Untitled"
    images: list[ImageEntry] = field(default_factory=list)
    active_image_index: int = 0
    reference_path: str = ""
    reference_type: str = "dxf"
    reference_crs_epsg: int | None = None
    export_settings: ExportSettings = field(default_factory=ExportSettings)
    units: str = "mm"
    working_plane: dict[str, Any] | None = None
    reference_roi: ReferenceRoi | None = None
    created: str = field(default_factory=_now_iso)
    modified: str = field(default_factory=_now_iso)
    _next_id: int = field(default=1, repr=False)
    _project_file: str | None = field(default=None, repr=False, compare=False)

    @property
    def active_image(self) -> ImageEntry | None:
        """Return the currently active image entry."""
        if not self.images:
            return None
        idx = max(0, min(self.active_image_index, len(self.images) - 1))
        return self.images[idx]

    def _ensure_active(self) -> ImageEntry:
        if not self.images:
            self.add_image("")
        active = self.active_image
        assert active is not None
        return active

    # Forwarding properties for backward compatibility
    @property
    def points(self) -> list[ControlPoint]:
        return self.active_image.points if self.active_image else []

    @points.setter
    def points(self, value: list[ControlPoint]) -> None:
        self._ensure_active().points = value

    @property
    def image_path(self) -> str:
        return self.active_image.path if self.active_image else ""

    @image_path.setter
    def image_path(self, value: str) -> None:
        self._ensure_active().path = value

    @property
    def lens_correction(self) -> dict[str, Any] | None:
        return self.active_image.lens_correction if self.active_image else None

    @lens_correction.setter
    def lens_correction(self, value: dict[str, Any] | None) -> None:
        self._ensure_active().lens_correction = value

    @property
    def clip_polygon(self) -> list[Point2D] | None:
        return self.active_image.clip_polygon if self.active_image else None

    @clip_polygon.setter
    def clip_polygon(self, value: list[Point2D] | None) -> None:
        self._ensure_active().clip_polygon = value

    @property
    def reference_world_points(self) -> dict[int, Point3D]:
        return self.active_image.reference_world_points if self.active_image else {}

    @reference_world_points.setter
    def reference_world_points(self, value: dict[int, Point3D]) -> None:
        self._ensure_active().reference_world_points = value

    @property
    def rms_error(self) -> float | None:
        return self.active_image.rms_error if self.active_image else None

    @rms_error.setter
    def rms_error(self, value: float | None) -> None:
        self._ensure_active().rms_error = value

    @property
    def transform_matrix(self) -> list[list[float]] | None:
        return self.active_image.transform_matrix if self.active_image else None

    @transform_matrix.setter
    def transform_matrix(self, value: list[list[float]] | None) -> None:
        self._ensure_active().transform_matrix = value

    @property
    def warnings(self) -> list[str]:
        return self.active_image.warnings if self.active_image else []

    @warnings.setter
    def warnings(self, value: list[str]) -> None:
        self._ensure_active().warnings = value

    def touch(self) -> None:
        """Update the modification timestamp."""
        self.modified = _now_iso()

    def clear_solver_state(self) -> None:
        """Reset residual values and transform matrices for all images."""
        for entry in self.images:
            entry.rms_error = None
            entry.transform_matrix = None
            entry.warnings = []
            for point in entry.points:
                point.residual = None
                point.residual_vector = None
        self.touch()

    def clear_reference_alignment(self) -> None:
        """Clear all reference coordinates and solver state for all images."""
        for entry in self.images:
            entry.reference_world_points = {}
            entry.rms_error = None
            entry.transform_matrix = None
            entry.warnings = []
            for point in entry.points:
                point.reference_xy = None
                point.residual = None
                point.residual_vector = None
        self.touch()

    def add_image(self, path: str | Path) -> ImageEntry:
        """Add a new image entry to the project, or return existing if path matches."""
        p_str = str(path)
        for entry in self.images:
            if entry.path == p_str:
                self.active_image_index = self.images.index(entry)
                return entry
        entry = ImageEntry(path=p_str)
        self.images.append(entry)
        self.active_image_index = len(self.images) - 1
        self.touch()
        return entry

    def add_point(self, label: str | None = None) -> ControlPoint:
        """Add a new control point to the active image."""
        active = self._ensure_active()
        point_id = self._next_id
        self._next_id += 1
        label = label or f"P{point_id:02d}"
        point = ControlPoint(id=point_id, label=label)
        active.points.append(point)
        self.touch()
        return point

    def get_point(self, point_id: int) -> ControlPoint | None:
        """Get a control point by ID from the active image."""
        if not self.active_image:
            return None
        return next((p for p in self.active_image.points if p.id == point_id), None)

    def remove_point(self, point_id: int) -> None:
        """Remove a point by ID from the active image."""
        active = self.active_image
        if active:
            active.points = [p for p in active.points if p.id != point_id]
            active.reference_world_points.pop(point_id, None)
            self.touch()

    def paired_points(self) -> list[ControlPoint]:
        """Return all enabled point pairs for the active image."""
        return [point for point in self.points if point.is_enabled_pair]

    def clone(self) -> ProjectData:
        """Return a deep copy of the entire project."""
        payload = self.to_dict()
        clone = self.from_dict(payload)
        clone._project_file = self._project_file
        return clone

    def to_dict(self) -> dict[str, Any]:
        """Serialize the project to a dictionary, omitting forwarded properties."""
        payload = {
            "name": self.name,
            "images": [self._image_to_dict(img) for img in self.images],
            "active_image_index": self.active_image_index,
            "reference_path": self.reference_path,
            "reference_type": self.reference_type,
            "reference_crs_epsg": self.reference_crs_epsg,
            "export_settings": asdict(self.export_settings),
            "units": self.units,
            "working_plane": self.working_plane,
            "reference_roi": self.reference_roi,
            "created": self.created,
            "modified": self.modified,
            "_next_id": self._next_id,
        }
        return payload

    def _image_to_dict(self, img: ImageEntry) -> dict[str, Any]:
        return {
            "path": img.path,
            "lens_correction": img.lens_correction,
            "clip_polygon": img.clip_polygon,
            "points": [asdict(p) for p in img.points],
            "reference_world_points": {str(k): v for k, v in img.reference_world_points.items()},
            "gps_pose": img.gps_pose,
            "rms_error": img.rms_error,
            "transform_matrix": img.transform_matrix,
            "warnings": img.warnings,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ProjectData:
        """Deserialize the project from a dictionary."""
        images: list[ImageEntry] = []
        for raw_img in payload.get("images", []):
            points = [
                ControlPoint(
                    id=int(p["id"]),
                    label=str(p.get("label", "")),
                    image_xy=_coerce_point(p.get("image_xy")),
                    reference_xy=_coerce_point(p.get("reference_xy")),
                    enabled=bool(p.get("enabled", True)),
                    locked=bool(p.get("locked", False)),
                    residual=_to_float(p.get("residual")),
                    residual_vector=_coerce_point(p.get("residual_vector")),
                )
                for p in raw_img.get("points", [])
            ]
            images.append(
                ImageEntry(
                    path=str(raw_img.get("path", "")),
                    lens_correction=_coerce_dict(raw_img.get("lens_correction")),
                    clip_polygon=_coerce_point_list(raw_img.get("clip_polygon")),
                    points=points,
                    reference_world_points=_coerce_reference_world_points(
                        raw_img.get("reference_world_points")
                    ),
                    gps_pose=_coerce_dict(raw_img.get("gps_pose")),
                    rms_error=_to_float(raw_img.get("rms_error")),
                    transform_matrix=_coerce_transform_matrix(raw_img.get("transform_matrix")),
                    warnings=[str(w) for w in raw_img.get("warnings", [])],
                )
            )

        if not images and (payload.get("points") or payload.get("image_path")):
            legacy_points = [
                ControlPoint(
                    id=int(p["id"]),
                    label=str(p.get("label", "")),
                    image_xy=_coerce_point(p.get("image_xy")),
                    reference_xy=_coerce_point(p.get("reference_xy")),
                    enabled=bool(p.get("enabled", True)),
                    locked=bool(p.get("locked", False)),
                    residual=_to_float(p.get("residual")),
                    residual_vector=_coerce_point(p.get("residual_vector")),
                )
                for p in payload.get("points", [])
            ]
            images.append(
                ImageEntry(
                    path=str(payload.get("image_path", "")),
                    lens_correction=_coerce_dict(payload.get("lens_correction")),
                    clip_polygon=_coerce_point_list(payload.get("clip_polygon")),
                    points=legacy_points,
                    reference_world_points=_coerce_reference_world_points(
                        payload.get("reference_world_points")
                    ),
                    gps_pose=_coerce_dict(payload.get("gps_pose")),
                    rms_error=_to_float(payload.get("rms_error")),
                    transform_matrix=_coerce_transform_matrix(payload.get("transform_matrix")),
                    warnings=[str(w) for w in payload.get("warnings", [])],
                )
            )

        export_settings = _coerce_export_settings(payload.get("export_settings"))
        project = cls(
            name=str(payload.get("name", "Untitled")),
            images=images,
            active_image_index=int(payload.get("active_image_index", 0)),
            reference_path=str(payload.get("reference_path", "")),
            reference_type=str(payload.get("reference_type", "dxf")),
            reference_crs_epsg=_to_optional_int(payload.get("reference_crs_epsg")),
            export_settings=export_settings,
            units=str(payload.get("units", "mm")),
            working_plane=_coerce_dict(payload.get("working_plane")),
            reference_roi=_coerce_reference_roi(payload.get("reference_roi")),
            created=str(payload.get("created", _now_iso())),
            modified=str(payload.get("modified", _now_iso())),
        )
        max_id = 0
        for img in images:
            for p in img.points:
                max_id = max(max_id, p.id)
        project._next_id = int(payload.get("_next_id", max_id + 1))
        return project

    def save(self, path: Path) -> None:
        """Save the project to a JSON file, relativizing asset paths."""
        path.parent.mkdir(parents=True, exist_ok=True)
        self.touch()
        payload = self.to_dict()
        target_dir = path.parent.resolve()

        def _rel_path(raw: str) -> str:
            if not raw:
                return raw
            resolved = self.resolve_asset_path(raw)
            try:
                return resolved.relative_to(target_dir).as_posix()
            except ValueError:
                return str(resolved)

        payload["reference_path"] = _rel_path(self.reference_path)
        for img in payload.get("images", []):
            img["path"] = _rel_path(img["path"])

        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._project_file = str(path.resolve())

    def validate_asset_paths(self, project_file: Path) -> None:
        """Validate that all asset paths are within the project directory or absolute.

        Absolute paths are permitted (desktop workflows often reference external
        storage), but are logged so the user can spot non-portable projects.
        """
        self._project_file = str(project_file.resolve())
        project_dir = project_file.parent.resolve()

        def _check(raw: str, field_name: str) -> None:
            if not raw:
                return
            candidate = Path(raw)
            if candidate.is_absolute():
                logger.info(
                    "Project references absolute asset path | field=%s | path=%s",
                    field_name,
                    raw,
                )
                return
            resolved_target = (project_dir / candidate).resolve()
            if not resolved_target.is_relative_to(project_dir):
                raise ValueError(
                    f"Projektpfad verlässt das Projektverzeichnis ({field_name}): {raw}"
                )

        _check(self.reference_path, "reference_path")
        for i, img in enumerate(self.images):
            _check(img.path, f"images[{i}].path")

    @classmethod
    def load(cls, path: Path) -> ProjectData:
        """Load a project from a JSON file and validate asset paths."""
        size = path.stat().st_size
        if size > MAX_PROJECT_FILE_BYTES:
            raise ValueError(
                f"Projektdatei ist zu groß ({size} Bytes, Limit {MAX_PROJECT_FILE_BYTES})."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Projektdatei hat kein gültiges JSON-Objekt im Wurzelelement.")
        project = cls.from_dict(data)
        project.validate_asset_paths(path)
        return project

    def resolve_asset_path(self, raw_path: str) -> Path:
        """Resolve a project asset path relative to the project file."""
        p = Path(raw_path)
        if p.is_absolute() or not self._project_file:
            return p
        return (Path(self._project_file).parent / p).resolve()

    def resolve_image_entry_path(self, entry: ImageEntry) -> Path | None:
        """Resolve the path of a specific image entry."""
        if not entry.path:
            return None
        return self.resolve_asset_path(entry.path)

    def resolve_active_image_path(self) -> Path | None:
        """Resolve the path of the currently active image."""
        if not self.active_image:
            return None
        return self.resolve_image_entry_path(self.active_image)

    def resolve_reference_path(self) -> Path | None:
        """Resolve the path of the reference file."""
        if not self.reference_path:
            return None
        return self.resolve_asset_path(self.reference_path)

    def ensure_image_entries(self) -> None:
        """Ensure at least one image entry exists."""
        if not self.images:
            self.add_image("")


def _to_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _to_optional_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _coerce_transform_matrix(raw: Any) -> list[list[float]] | None:
    if raw is None:
        return None
    if not isinstance(raw, list) or len(raw) != 3:
        return None
    rows: list[list[float]] = []
    for row in raw:
        if not isinstance(row, list) or len(row) != 3:
            return None
        try:
            rows.append([float(value) for value in row])
        except (TypeError, ValueError):
            return None
    return rows


def _coerce_dict(raw: Any) -> dict[str, Any] | None:
    return raw if isinstance(raw, dict) else None


def _coerce_export_settings(raw: Any) -> ExportSettings:
    if not isinstance(raw, dict):
        return ExportSettings()
    allowed = {f.name for f in fields(ExportSettings)}
    filtered = {key: value for key, value in raw.items() if key in allowed}
    try:
        return ExportSettings(**filtered)
    except (TypeError, ValueError) as exc:
        logger.warning("Falling back to default ExportSettings | error=%s", exc)
        return ExportSettings()
