"""JPEG export helpers."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def write_jpeg_image(
    path: str | Path,
    image: np.ndarray,
    quality: int = 95,
) -> None:
    """Write a JPEG image to disk."""

    if image.dtype != np.uint8:
        raise ValueError("JPEG export supports only 8-bit images")

    payload = image
    if payload.ndim == 3 and payload.shape[2] == 4:
        payload = payload[:, :, :3]

    target_path = Path(path)
    if not cv2.imwrite(
        str(target_path),
        payload,
        [cv2.IMWRITE_JPEG_QUALITY, max(1, min(int(quality), 100))],
    ):
        raise ValueError(f"Failed to write JPEG image to {target_path}")
