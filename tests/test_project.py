from __future__ import annotations

from pathlib import Path

from core.project import ControlPoint, ImageEntry, ProjectData


def test_project_roundtrip(tmp_path: Path) -> None:
    project = ProjectData(name="roundtrip")
    project.image_path = "input.jpg"
    project.reference_path = "reference.dxf"
    project.reference_world_points = {1: (10.0, 20.0, 30.0)}
    project.working_plane = {
        "origin": [10.0, 20.0, 30.0],
        "normal": [0.0, 0.0, 1.0],
        "u_axis": [1.0, 0.0, 0.0],
        "v_axis": [0.0, 1.0, 0.0],
    }
    point = project.add_point("A")
    point.image_xy = (10.5, 20.5)
    point.reference_xy = (100.0, 200.0)
    point.enabled = False
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
    assert loaded.points[0].enabled is False
    assert loaded.points[0].locked is True
    assert loaded.points[0].image_xy == (10.5, 20.5)
    assert loaded.points[0].reference_xy == (100.0, 200.0)
    assert loaded.points[0].residual_vector == (0.1, -0.2)
    assert loaded.reference_world_points == {1: (10.0, 20.0, 30.0)}
    assert loaded.working_plane == project.working_plane
    assert loaded.transform_matrix is not None


def test_project_roundtrip_preserves_multiple_images(tmp_path: Path) -> None:
    project = ProjectData(name="multi", reference_crs_epsg=25833)
    project.images = [
        ImageEntry(
            path="first.jpg",
            gps_pose={"latitude": 52.5, "longitude": 13.4},
            points=[
                ControlPoint(
                    id=1,
                    label="P1",
                    image_xy=(10.0, 10.0),
                    reference_xy=(100.0, 200.0),
                )
            ],
            transform_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        ),
        ImageEntry(
            path="second.jpg",
            clip_polygon=[(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)],
            points=[
                ControlPoint(
                    id=2,
                    label="P2",
                    image_xy=(20.0, 30.0),
                    reference_xy=(300.0, 400.0),
                )
            ],
            warnings=["needs review"],
        ),
    ]
    project.active_image_index = 1
    project.sync_from_active_image()

    path = tmp_path / "multi.imagerect.json"
    project.save(path)
    loaded = ProjectData.load(path)

    assert loaded.reference_crs_epsg == 25833
    assert len(loaded.images) == 2
    assert loaded.active_image_index == 1
    assert loaded.images[0].gps_pose == {"latitude": 52.5, "longitude": 13.4}
    assert loaded.images[1].clip_polygon == [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    assert loaded.images[1].warnings == ["needs review"]
    assert loaded.image_path == "second.jpg"


def test_project_save_relativizes_assets_against_target_file(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    assets_dir = project_dir / "assets"
    assets_dir.mkdir(parents=True)

    image_path = assets_dir / "source.jpg"
    reference_path = assets_dir / "reference.dxf"
    image_path.write_text("x", encoding="utf-8")
    reference_path.write_text("0", encoding="utf-8")

    project = ProjectData(name="relative-paths")
    project.image_path = str(image_path.resolve())
    project.reference_path = str(reference_path.resolve())

    target_path = project_dir / "relative.imagerect.json"
    project.save(target_path)
    loaded = ProjectData.load(target_path)

    assert loaded.image_path == "assets/source.jpg"
    assert loaded.reference_path == "assets/reference.dxf"
