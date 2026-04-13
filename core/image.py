"""Image loading, color conversion, and optional undistortion."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def load_image(path: str | Path) -> np.ndarray:
    """Load an image as a numpy array."""

    image_path = Path(path)
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Could not decode image: {image_path}")
    return image


def image_to_rgb(image: np.ndarray) -> np.ndarray:
    """Convert OpenCV image data into an RGB/RGBA view for Qt drawing."""

    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def image_size(image: np.ndarray) -> tuple[int, int]:
    """Return width and height in pixels."""

    height, width = image.shape[:2]
    return width, height


def undistort(
    image: np.ndarray,
    camera_matrix: np.ndarray,
    distortion_coefficients: np.ndarray,
) -> np.ndarray:
    """Apply a lens calibration and crop to the valid region."""

    height, width = image.shape[:2]
    new_matrix, roi = cv2.getOptimalNewCameraMatrix(
        camera_matrix,
        distortion_coefficients,
        (width, height),
        1.0,
        (width, height),
    )
    undistorted = cv2.undistort(
        image,
        camera_matrix,
        distortion_coefficients,
        None,
        new_matrix,
    )
    x, y, roi_width, roi_height = roi
    if roi_width > 0 and roi_height > 0:
        return undistorted[y : y + roi_height, x : x + roi_width]
    return undistorted
