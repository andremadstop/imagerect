from __future__ import annotations

import numpy as np
import pytest

from core.lens import LensProfile
from core.pose import decompose_homography_pose, gps_to_reference_transform


def test_homography_decomposition_yields_plausible_pose() -> None:
    profile = LensProfile(name="pose", focal_length_mm=24.0, sensor_width_mm=36.0)

    pose = decompose_homography_pose(np.eye(3, dtype=np.float64), (4000, 3000), profile)

    assert pose is not None
    assert pose["yaw_deg"] == pytest.approx(0.0)
    assert pose["pitch_deg"] == pytest.approx(0.0)
    assert pose["roll_deg"] == pytest.approx(0.0)
    assert pose["field_of_view_deg"] == pytest.approx(73.73979529168804)


def test_gps_to_reference_transform() -> None:
    calls: list[int] = []

    class FakeTransformer:
        def transform(self, lon: float, lat: float) -> tuple[float, float]:
            return (lon * 1000.0, lat * 1000.0)

    def factory(epsg: int) -> FakeTransformer:
        calls.append(epsg)
        return FakeTransformer()

    xy = gps_to_reference_transform(
        {"latitude": 52.5, "longitude": 13.4},
        25833,
        transformer_factory=factory,
    )

    assert calls == [25833]
    assert xy == pytest.approx((13400.0, 52500.0))
