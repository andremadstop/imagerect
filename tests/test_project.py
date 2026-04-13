from __future__ import annotations

from pathlib import Path

from core.project import ProjectData


def test_project_roundtrip(tmp_path: Path) -> None:
    project = ProjectData(name="roundtrip")
    project.image_path = "input.jpg"
    project.reference_path = "reference.dxf"
    project.working_plane = {
        "origin": [10.0, 20.0, 30.0],
        "normal": [0.0, 0.0, 1.0],
        "u_axis": [1.0, 0.0, 0.0],
        "v_axis": [0.0, 1.0, 0.0],
    }
    point = project.add_point("A")
    point.image_xy = (10.5, 20.5)
    point.reference_xy = (100.0, 200.0)
    point.locked = True
    point.residual = 0.25
    point.residual_vector = (0.1, -0.2)
    project.rms_error = 0.25
    project.transform_matrix = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    project.warnings = ["example warning"]

    path = tmp_path / "project.imagerect.json"
    project.save(path)
    loaded = ProjectData.load(path)

    assert loaded.name == "roundtrip"
    assert loaded.image_path == "input.jpg"
    assert loaded.reference_path == "reference.dxf"
    assert loaded.points[0].label == "A"
    assert loaded.points[0].locked is True
    assert loaded.points[0].image_xy == (10.5, 20.5)
    assert loaded.points[0].reference_xy == (100.0, 200.0)
    assert loaded.points[0].residual_vector == (0.1, -0.2)
    assert loaded.working_plane == project.working_plane
    assert loaded.transform_matrix is not None
