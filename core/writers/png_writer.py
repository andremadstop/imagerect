"""PNG export helpers."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def write_png_image(path: str | Path, image: np.ndarray) -> None:
    """Write a PNG image to disk."""

    if image.dtype not in {np.dtype(np.uint8), np.dtype(np.uint16)}:
        raise ValueError("PNG export supports only 8-bit and 16-bit images")

    target_path = Path(path)
    if not cv2.imwrite(str(target_path), image):
        raise ValueError(f"Failed to write PNG image to {target_path}")
