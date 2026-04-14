"""TIFF and BigTIFF export helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import tifffile


def write_tiff_image(
    path: str | Path,
    image: np.ndarray,
    dpi: float,
    compression: str,
    metadata: dict[str, Any],
    *,
    bigtiff: bool = False,
    embed_metadata: bool = True,
) -> None:
    """Write a TIFF or BigTIFF image to disk."""

    target_path = Path(path)
    compression_arg = None if compression == "none" else compression.lower()
    kwargs: dict[str, Any] = {
        "bigtiff": bigtiff,
        "compression": compression_arg,
        "resolution": (float(dpi), float(dpi)),
        "resolutionunit": "inch",
    }
    if image.ndim == 3 and image.shape[2] in {3, 4}:
        kwargs["photometric"] = "rgb"
    if embed_metadata:
        kwargs["description"] = json.dumps(metadata, indent=2)

    try:
        tifffile.imwrite(str(target_path), image, **kwargs)
    except Exception as exc:  # pragma: no cover - exercised in integration flows
        raise ValueError(f"Failed to write TIFF image to {target_path}: {exc}") from exc
