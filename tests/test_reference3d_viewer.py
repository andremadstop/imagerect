from __future__ import annotations

from typing import Any

import numpy as np

from core.reference3d import Reference3D
from ui.reference3d_viewer import Reference3DViewer


def test_single_control_point_projection_uses_scene_scale(qtbot: Any) -> None:
    viewer = Reference3DViewer()
    viewer.resize(640, 480)
    qtbot.addWidget(viewer)
    viewer.show()

    reference = Reference3D(
        points=np.asarray(
            [
                [0.0, 0.0, 0.0],
                [100.0, 0.0, 0.0],
                [100.0, 100.0, 0.0],
                [0.0, 100.0, 0.0],
            ],
            dtype=np.float64,
        )
    )
    viewer.set_reference(reference)

    projected_scene, _ = viewer._project_points(viewer._display_points)
    projected_single, _ = viewer._project_points(
        np.asarray([viewer._display_points[0]], dtype=np.float64)
    )

    assert np.allclose(projected_single[0], projected_scene[0])


def test_large_meshes_are_sampled_in_viewer(qtbot: Any) -> None:
    viewer = Reference3DViewer()
    viewer.resize(640, 480)
    qtbot.addWidget(viewer)
    viewer.show()

    vertices = np.column_stack(
        (
            np.arange(60_001, dtype=np.float64),
            np.zeros(60_001, dtype=np.float64),
            np.zeros(60_001, dtype=np.float64),
        )
    )
    faces = np.asarray([[0, 1, 2]], dtype=np.int32)

    viewer.set_reference(Reference3D(vertices=vertices, faces=faces, source_type="obj"))

    assert len(viewer._display_points) == 50_000
    assert len(viewer._display_edges) == 0
