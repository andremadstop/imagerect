from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from core.reference3d import (
    WorkingPlane,
    define_plane_from_3_points,
    load_obj,
    pick_nearest_point,
    project_3d_to_plane,
)
from core.transform import project_points, solve_planar_homography


def test_define_plane_from_3_points() -> None:
    plane = define_plane_from_3_points(
        (10.0, 20.0, 30.0),
        (14.0, 20.0, 30.0),
        (10.0, 26.0, 30.0),
    )

    assert np.allclose(plane.origin, [10.0, 20.0, 30.0])
    assert np.allclose(plane.normal, [0.0, 0.0, 1.0])
    assert np.allclose(plane.u_axis, [1.0, 0.0, 0.0])
    assert np.allclose(plane.v_axis, [0.0, 1.0, 0.0])


def test_project_3d_to_plane() -> None:
    plane = WorkingPlane(
        origin=np.array([10.0, 20.0, 30.0], dtype=np.float64),
        normal=np.array([0.0, 0.0, 1.0], dtype=np.float64),
        u_axis=np.array([1.0, 0.0, 0.0], dtype=np.float64),
        v_axis=np.array([0.0, 1.0, 0.0], dtype=np.float64),
    )
    points = np.array(
        [
            [10.0, 20.0, 30.0],
            [13.0, 24.0, 34.0],
            [8.0, 22.0, 28.0],
        ],
        dtype=np.float64,
    )

    projected = project_3d_to_plane(points, plane)

    assert np.allclose(projected, [[0.0, 0.0], [3.0, 4.0], [-2.0, 2.0]])


def test_load_obj_synthetic(tmp_path: Path) -> None:
    pytest.importorskip("trimesh")

    path = tmp_path / "synthetic.obj"
    path.write_text(
        "\n".join(
            [
                "v 0 0 0",
                "v 2 0 0",
                "v 2 1 0",
                "v 0 1 0",
                "f 1 2 3",
                "f 1 3 4",
            ]
        ),
        encoding="utf-8",
    )

    reference = load_obj(path)

    assert reference.source_type == "obj"
    assert reference.vertices is not None
    assert reference.faces is not None
    assert reference.vertices.shape == (4, 3)
    assert reference.faces.shape == (2, 3)
    assert np.allclose(reference.bounds_min, [0.0, 0.0, 0.0])
    assert np.allclose(reference.bounds_max, [2.0, 1.0, 0.0])


def test_pick_nearest_point_returns_closest_geometry_point(tmp_path: Path) -> None:
    pytest.importorskip("trimesh")

    reference = load_obj(
        _write_obj_fixture(
            tmp_path / "pick_nearest.obj",
            vertices=[
                (0.0, 0.0, 0.0),
                (5.0, 0.0, 0.0),
                (5.0, 5.0, 0.0),
            ],
            faces=[(1, 2, 3)],
        )
    )

    picked = pick_nearest_point(
        reference,
        np.array([4.8, 0.1, 0.0], dtype=np.float64),
        tolerance=0.5,
    )

    assert picked is not None
    assert np.allclose(picked, [5.0, 0.0, 0.0])


def test_3d_to_2d_to_homography_pipeline() -> None:
    world_points = np.array(
        [
            [10.0, 20.0, 50.0],
            [410.0, 20.0, 50.0],
            [410.0, 320.0, 50.0],
            [10.0, 320.0, 50.0],
        ],
        dtype=np.float64,
    )
    plane = define_plane_from_3_points(world_points[0], world_points[1], world_points[3])
    plane_points = project_3d_to_plane(world_points, plane)
    image_points = np.array(
        [
            [120.0, 420.0],
            [620.0, 360.0],
            [560.0, 90.0],
            [170.0, 120.0],
        ],
        dtype=np.float64,
    )

    result = solve_planar_homography(image_points.tolist(), plane_points.tolist())
    projected = project_points(image_points, result.matrix)

    assert result.rms_error < 1e-6
    assert np.allclose(projected, plane_points, atol=1e-4)


def _write_obj_fixture(
    path: Path,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, int, int]],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"v {x} {y} {z}" for x, y, z in vertices]
    lines.extend(f"f {a} {b} {c}" for a, b, c in faces)
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
