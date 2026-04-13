"""Planar homography solving, reprojection analysis, and quality warnings."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import cv2
import numpy as np

Point2D = tuple[float, float]


@dataclass(slots=True)
class HomographyResult:
    matrix: np.ndarray
    inlier_mask: list[bool]
    projected_reference_points: list[Point2D]
    residual_vectors: list[Point2D]
    residuals: list[float]
    rms_error: float
    warnings: list[str] = field(default_factory=list)


def solve_planar_homography(
    image_points: Sequence[Point2D],
    reference_points: Sequence[Point2D],
    ransac_threshold: float = 3.0,
    rms_warning_threshold: float = 5.0,
) -> HomographyResult:
    """Solve image -> reference plane homography and compute residuals."""

    if len(image_points) != len(reference_points):
        raise ValueError("Image/reference point counts must match.")

    image_array = _as_points_array(image_points)
    reference_array = _as_points_array(reference_points)
    warnings = build_quality_warnings(reference_array)
    if len(image_points) < 4:
        raise ValueError("Too few point pairs for homography; at least four are required.")

    method = cv2.RANSAC if len(image_points) > 4 else 0
    matrix, mask = cv2.findHomography(
        image_array,
        reference_array,
        method=method,
        ransacReprojThreshold=ransac_threshold,
    )
    if matrix is None:
        message = "OpenCV could not estimate a homography from the point pairs."
        if warnings:
            message = f"{message} {'; '.join(warnings)}."
        raise ValueError(message)

    projected = project_points(image_array, matrix)
    residual_vectors_array = projected - reference_array
    residuals_array = np.linalg.norm(residual_vectors_array, axis=1)
    rms_error = float(np.sqrt(np.mean(np.square(residuals_array))))

    if rms_error > rms_warning_threshold:
        warnings.append("High RMS reprojection error")
    if mask is not None and int(mask.sum()) < len(image_points):
        warnings.append("RANSAC rejected one or more outliers")

    mask_values = mask.ravel() if mask is not None else np.ones(len(image_points), dtype=np.uint8)
    return HomographyResult(
        matrix=matrix,
        inlier_mask=[bool(value) for value in mask_values],
        projected_reference_points=[(float(x), float(y)) for x, y in projected],
        residual_vectors=[(float(x), float(y)) for x, y in residual_vectors_array],
        residuals=[float(value) for value in residuals_array],
        rms_error=rms_error,
        warnings=warnings,
    )


def project_points(points: Sequence[Point2D] | np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Project 2D points through a homography."""

    array = _as_points_array(points)
    reshaped = array.reshape(-1, 1, 2)
    projected = cv2.perspectiveTransform(reshaped, matrix)
    return projected.reshape(-1, 2)


def build_quality_warnings(reference_points: np.ndarray) -> list[str]:
    """Infer user-facing warnings from the reference point layout."""

    warnings: list[str] = []
    if len(reference_points) < 4:
        warnings.append("Too few points for homography")
        return warnings
    if _is_nearly_collinear(reference_points):
        warnings.append("Control points are nearly collinear")
    return warnings


def _is_nearly_collinear(points: np.ndarray) -> bool:
    hull = cv2.convexHull(points.astype(np.float32))
    hull_area = abs(float(cv2.contourArea(hull)))
    x_values = points[:, 0]
    y_values = points[:, 1]
    bbox_area = max(
        (float(x_values.max()) - float(x_values.min()))
        * (float(y_values.max()) - float(y_values.min())),
        1e-9,
    )
    return hull_area / bbox_area < 0.01


def _as_points_array(points: Sequence[Point2D] | np.ndarray) -> np.ndarray:
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 2:
        raise ValueError("Expected an Nx2 point array.")
    return array
