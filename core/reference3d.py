"""3D reference loading, plane definition, and 3D->2D projection helpers."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import numpy as np

logger = logging.getLogger(__name__)
Point2D = tuple[float, float]

try:
    import pye57 as _pye57
except Exception:  # pragma: no cover - optional dependency
    pye57: Any | None = None
else:  # pragma: no cover - imported when dependency is installed
    pye57 = _pye57

try:
    import trimesh as _trimesh
except Exception:  # pragma: no cover - optional dependency
    trimesh: Any | None = None
else:  # pragma: no cover - imported when dependency is installed
    trimesh = _trimesh

try:
    import open3d as _o3d
except Exception:  # pragma: no cover - optional dependency
    o3d: Any | None = None
else:  # pragma: no cover - imported when dependency is installed
    o3d = _o3d


@dataclass(slots=True)
class WorkingPlane:
    """A 2D coordinate system on a plane in 3D space."""

    origin: np.ndarray
    normal: np.ndarray
    u_axis: np.ndarray
    v_axis: np.ndarray


@dataclass(slots=True)
class Reference3D:
    """Loaded 3D reference geometry."""

    points: np.ndarray | None = None
    vertices: np.ndarray | None = None
    faces: np.ndarray | None = None
    source_type: str = "e57"
    units: str = "mm"
    bounds_min: np.ndarray | None = None
    bounds_max: np.ndarray | None = None
    working_plane: WorkingPlane | None = None
    _kdtree: Any = field(default=None, repr=False)


def load_e57(path: str | Path) -> Reference3D:
    reference_path = Path(path)
    if not reference_path.exists():
        raise FileNotFoundError(f"3D reference not found: {reference_path}")
    if pye57 is None:
        raise ImportError("pye57 is not installed. Install imagerect[3d] to load E57 files.")

    document = pye57.E57(str(reference_path))
    try:
        if document.scan_count == 0:
            raise ValueError(f"E57 file contains no scans: {reference_path}")
        data = document.read_scan(0, ignore_missing_fields=True, transform=True)
    finally:
        document.close()

    points = np.column_stack((data["cartesianX"], data["cartesianY"], data["cartesianZ"])).astype(
        np.float64
    )
    points = _downsample_points(points, target_count=2_000_000)
    bounds_min, bounds_max = _compute_bounds(points)
    logger.info("Loaded E57 reference | path=%s | points=%d", reference_path, len(points))
    return Reference3D(
        points=points,
        source_type="e57",
        units="m",
        bounds_min=bounds_min,
        bounds_max=bounds_max,
    )


def load_obj(path: str | Path) -> Reference3D:
    reference_path = Path(path)
    if not reference_path.exists():
        raise FileNotFoundError(f"3D reference not found: {reference_path}")
    if trimesh is None:
        raise ImportError("trimesh is not installed. Install imagerect[3d] to load OBJ files.")

    mesh = cast(Any, trimesh.load(str(reference_path), force="mesh", process=False))
    if isinstance(mesh, trimesh.Scene):
        geometry = tuple(mesh.geometry.values())
        if not geometry:
            raise ValueError(f"OBJ scene is empty: {reference_path}")
        mesh = trimesh.util.concatenate(geometry)

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int32)
    bounds_min, bounds_max = _compute_bounds(vertices)
    logger.info(
        "Loaded OBJ reference | path=%s | vertices=%d | faces=%d",
        reference_path,
        len(vertices),
        len(faces),
    )
    return Reference3D(
        vertices=vertices,
        faces=faces,
        source_type="obj",
        units=str(getattr(mesh, "units", None) or "unitless"),
        bounds_min=bounds_min,
        bounds_max=bounds_max,
    )


def define_plane_from_3_points(
    p1: Iterable[float],
    p2: Iterable[float],
    p3: Iterable[float],
) -> WorkingPlane:
    point1 = _as_vector(p1)
    point2 = _as_vector(p2)
    point3 = _as_vector(p3)

    u_axis = _normalize(point2 - point1)
    normal = np.cross(point2 - point1, point3 - point1)
    normal = _normalize(normal)
    v_axis = _normalize(np.cross(normal, u_axis))
    return WorkingPlane(origin=point1, normal=normal, u_axis=u_axis, v_axis=v_axis)


def define_plane_ransac(
    points: np.ndarray,
    distance_threshold: float = 0.01,
) -> WorkingPlane:
    if len(points) < 3:
        raise ValueError("At least three 3D points are required to define a plane.")

    points = np.asarray(points, dtype=np.float64)
    if o3d is not None:
        cloud = o3d.geometry.PointCloud()
        cloud.points = o3d.utility.Vector3dVector(points)
        plane_model, inliers = cloud.segment_plane(
            distance_threshold=distance_threshold,
            ransac_n=3,
            num_iterations=1000,
        )
        a, b, c, _d = plane_model
        normal = _normalize(np.array([a, b, c], dtype=np.float64))
        inlier_points = points[np.asarray(inliers, dtype=np.int64)]
        origin = inlier_points.mean(axis=0) if len(inlier_points) else points.mean(axis=0)
    else:
        centroid = points.mean(axis=0)
        centered = points - centroid
        _, _, vh = np.linalg.svd(centered, full_matrices=False)
        normal = _normalize(vh[-1])
        origin = centroid
        logger.warning("Open3D unavailable; falling back to SVD plane fit")

    helper_axis = np.array([1.0, 0.0, 0.0], dtype=np.float64)
    if abs(float(np.dot(helper_axis, normal))) > 0.9:
        helper_axis = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    u_axis = _normalize(np.cross(helper_axis, normal))
    v_axis = _normalize(np.cross(normal, u_axis))
    return WorkingPlane(origin=origin, normal=normal, u_axis=u_axis, v_axis=v_axis)


def project_3d_to_plane(points_3d: np.ndarray, plane: WorkingPlane) -> np.ndarray:
    points = np.asarray(points_3d, dtype=np.float64)
    offsets = points - plane.origin
    u_values = offsets @ plane.u_axis
    v_values = offsets @ plane.v_axis
    return np.column_stack((u_values, v_values))


def pick_nearest_point(
    reference: Reference3D,
    query_3d: np.ndarray,
    tolerance: float,
) -> np.ndarray | None:
    candidates = reference_source_points(reference)
    if candidates is None or len(candidates) == 0:
        return None

    query = _as_vector(query_3d)
    if len(candidates) > 10_000 and o3d is not None:
        if reference._kdtree is None:
            cloud = o3d.geometry.PointCloud()
            cloud.points = o3d.utility.Vector3dVector(candidates)
            reference._kdtree = {
                "cloud": cloud,
                "tree": o3d.geometry.KDTreeFlann(cloud),
            }
        search = reference._kdtree["tree"].search_knn_vector_3d(query, 1)
        if search[0] == 0:
            return None
        index = int(search[1][0])
        distance = float(np.sqrt(search[2][0]))
        if distance > tolerance:
            return None
        return np.asarray(candidates[index], dtype=np.float64)

    deltas = candidates - query
    distances = np.linalg.norm(deltas, axis=1)
    index = int(np.argmin(distances))
    if float(distances[index]) > tolerance:
        return None
    return np.asarray(candidates[index], dtype=np.float64)


def reference_source_points(reference: Reference3D) -> np.ndarray | None:
    if reference.points is not None:
        return cast(np.ndarray, reference.points)
    if reference.vertices is not None:
        return cast(np.ndarray, reference.vertices)
    return None


def reference_plane_extents(
    reference: Reference3D,
    max_samples: int = 50_000,
) -> tuple[Point2D, Point2D]:
    if reference.working_plane is None:
        raise ValueError("A working plane is required to compute 3D reference extents.")

    source_points = reference_source_points(reference)
    if source_points is None or len(source_points) == 0:
        raise ValueError("3D reference contains no geometry.")
    if len(source_points) > max_samples:
        step = max(len(source_points) // max_samples, 1)
        source_points = source_points[::step]
    uv = project_3d_to_plane(source_points, reference.working_plane)
    mins = uv.min(axis=0)
    maxs = uv.max(axis=0)
    return (float(mins[0]), float(mins[1])), (float(maxs[0]), float(maxs[1]))


def plane_corners_from_extents(
    plane: WorkingPlane,
    extents: tuple[Point2D, Point2D],
) -> np.ndarray:
    (min_u, min_v), (max_u, max_v) = extents
    corners_2d = np.array(
        [[min_u, min_v], [max_u, min_v], [max_u, max_v], [min_u, max_v]],
        dtype=np.float64,
    )
    return np.asarray(
        plane.origin[None, :]
        + corners_2d[:, [0]] * plane.u_axis[None, :]
        + corners_2d[:, [1]] * plane.v_axis[None, :],
        dtype=np.float64,
    )


def working_plane_to_dict(plane: WorkingPlane | None) -> dict[str, list[float]] | None:
    if plane is None:
        return None
    return {
        "origin": plane.origin.astype(float).tolist(),
        "normal": plane.normal.astype(float).tolist(),
        "u_axis": plane.u_axis.astype(float).tolist(),
        "v_axis": plane.v_axis.astype(float).tolist(),
    }


def working_plane_from_dict(data: dict[str, Any] | None) -> WorkingPlane | None:
    if not data:
        return None
    return WorkingPlane(
        origin=_as_vector(data["origin"]),
        normal=_normalize(_as_vector(data["normal"])),
        u_axis=_normalize(_as_vector(data["u_axis"])),
        v_axis=_normalize(_as_vector(data["v_axis"])),
    )


def _compute_bounds(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    points = np.asarray(points, dtype=np.float64)
    return points.min(axis=0), points.max(axis=0)


def _downsample_points(points: np.ndarray, target_count: int) -> np.ndarray:
    if len(points) <= target_count:
        return points
    if o3d is not None:
        cloud = o3d.geometry.PointCloud()
        cloud.points = o3d.utility.Vector3dVector(points)
        span = np.ptp(points, axis=0)
        volume = max(float(np.prod(np.maximum(span, 1e-9))), 1e-9)
        voxel_size = (volume / target_count) ** (1.0 / 3.0)
        reduced = cloud.voxel_down_sample(voxel_size=max(voxel_size, 1e-9))
        downsampled = np.asarray(reduced.points, dtype=np.float64)
        if len(downsampled) > 0:
            logger.info(
                "Downsampled point cloud with Open3D | original=%d | reduced=%d",
                len(points),
                len(downsampled),
            )
            return downsampled[:target_count]
    step = max(len(points) // target_count, 1)
    logger.warning(
        "Open3D unavailable or downsampling returned no points; using stride fallback | "
        "original=%d | target=%d",
        len(points),
        target_count,
    )
    return points[::step][:target_count]


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        raise ValueError("Cannot normalize a zero-length vector.")
    return vector / norm


def _as_vector(values: Iterable[float]) -> np.ndarray:
    vector = np.asarray(list(values), dtype=np.float64)
    if vector.shape != (3,):
        raise ValueError("Expected a 3D vector.")
    return vector
