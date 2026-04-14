from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from hypothesis import assume, given, seed, settings
from hypothesis import strategies as st

from core.transform import project_points, solve_planar_homography

POINT_COORD = st.floats(
    min_value=-60.0,
    max_value=60.0,
    allow_nan=False,
    allow_infinity=False,
    width=32,
)
SCALE_FACTOR = st.floats(
    min_value=0.25,
    max_value=4.0,
    allow_nan=False,
    allow_infinity=False,
    width=32,
)


def _quad_from_offsets(offsets: tuple[float, ...]) -> np.ndarray:
    tl_dx, tl_dy, tr_dx, tr_dy, br_dx, br_dy, bl_dx, bl_dy = offsets
    quad = np.array(
        [
            [0.0 + tl_dx, 0.0 + tl_dy],
            [400.0 + tr_dx, 0.0 + tr_dy],
            [400.0 + br_dx, 300.0 + br_dy],
            [0.0 + bl_dx, 300.0 + bl_dy],
        ],
        dtype=np.float64,
    )
    return quad


@st.composite
def non_degenerate_quad(draw: Any) -> np.ndarray:
    offsets = draw(st.tuples(*(POINT_COORD for _ in range(8))))
    quad = _quad_from_offsets(offsets)
    hull = cv2.convexHull(quad.astype(np.float32))
    assume(abs(float(cv2.contourArea(hull))) >= 10_000.0)
    return quad


NON_DEGENERATE_QUAD = non_degenerate_quad()


def _normalize_matrix(matrix: np.ndarray) -> np.ndarray:
    scale = float(matrix[2, 2]) if abs(float(matrix[2, 2])) > 1e-9 else 1.0
    return matrix / scale


def _probe_points(quad: np.ndarray) -> np.ndarray:
    center = quad.mean(axis=0, keepdims=True)
    edge_midpoints = (quad + np.roll(quad, -1, axis=0)) * 0.5
    return np.vstack([quad, center, edge_midpoints])


@seed(20260414)
@settings(max_examples=100, deadline=2000)
@given(NON_DEGENERATE_QUAD)
def test_identity_homography_preserves_points(quad: np.ndarray) -> None:
    result = solve_planar_homography(quad.tolist(), quad.tolist())

    projected = project_points(quad, result.matrix)

    assert np.allclose(projected, quad, atol=1e-6)
    assert np.allclose(_normalize_matrix(result.matrix), np.eye(3), atol=1e-5)


@seed(20260414)
@settings(max_examples=100, deadline=2000)
@given(NON_DEGENERATE_QUAD, NON_DEGENERATE_QUAD)
def test_homography_inverse_round_trip(source_quad: np.ndarray, dest_quad: np.ndarray) -> None:
    result = solve_planar_homography(source_quad.tolist(), dest_quad.tolist())
    inverse = np.linalg.inv(result.matrix)
    probe_points = _probe_points(source_quad)

    projected = project_points(probe_points, result.matrix)
    round_trip = project_points(projected, inverse)

    assert np.allclose(round_trip, probe_points, atol=1e-4)


@seed(20260414)
@settings(max_examples=100, deadline=2000)
@given(NON_DEGENERATE_QUAD, NON_DEGENERATE_QUAD)
def test_homography_rank_3(source_quad: np.ndarray, dest_quad: np.ndarray) -> None:
    result = solve_planar_homography(source_quad.tolist(), dest_quad.tolist())

    assert np.linalg.matrix_rank(result.matrix) == 3


@seed(20260414)
@settings(max_examples=60, deadline=2000)
@given(
    st.floats(min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False, width=32),
    st.floats(min_value=-500.0, max_value=500.0, allow_nan=False, allow_infinity=False, width=32),
    st.floats(min_value=10.0, max_value=250.0, allow_nan=False, allow_infinity=False, width=32),
)
def test_homography_flags_degenerate_input(
    start_x: float,
    start_y: float,
    step: float,
) -> None:
    image_points = [
        (start_x + step * offset, start_y + step * offset) for offset in (0.0, 1.0, 2.0, 3.0)
    ]
    reference_points = [
        (start_x + step * offset * 2.0, start_y + step * offset * 2.0)
        for offset in (0.0, 1.0, 2.0, 3.0)
    ]

    try:
        result = solve_planar_homography(image_points, reference_points)
    except ValueError:
        return

    assert any("collinear" in warning.lower() for warning in result.warnings)


@seed(20260414)
@settings(max_examples=100, deadline=2000)
@given(NON_DEGENERATE_QUAD, NON_DEGENERATE_QUAD, SCALE_FACTOR)
def test_homography_invariant_under_uniform_scale(
    source_quad: np.ndarray,
    dest_quad: np.ndarray,
    scale_factor: float,
) -> None:
    result = solve_planar_homography(source_quad.tolist(), dest_quad.tolist())
    scaled_result = solve_planar_homography(
        (source_quad * scale_factor).tolist(),
        (dest_quad * scale_factor).tolist(),
    )
    probe_points = _probe_points(source_quad)

    projected = project_points(probe_points, result.matrix)
    projected_scaled = project_points(probe_points * scale_factor, scaled_result.matrix)

    assert np.allclose(projected_scaled, projected * scale_factor, atol=1e-4)
