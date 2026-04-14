"""TIFF and BigTIFF export helpers."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import tifffile


@dataclass(slots=True)
class TiffPageSpec:
    data: np.ndarray | Iterator[np.ndarray]
    shape: tuple[int, ...]
    dtype: np.dtype[np.generic]
    description: str | None = None
    photometric: str | None = None
    tile: tuple[int, int] | None = None


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


def write_tiff_pages(
    path: str | Path,
    pages: Sequence[TiffPageSpec],
    dpi: float,
    compression: str,
    *,
    bigtiff: bool = False,
) -> None:
    """Write one or more TIFF pages, optionally using tiled iterators."""

    target_path = Path(path)
    compression_arg = None if compression == "none" else compression.lower()

    try:
        with tifffile.TiffWriter(str(target_path), bigtiff=bigtiff) as writer:
            for page in pages:
                kwargs: dict[str, Any] = {
                    "shape": page.shape,
                    "dtype": page.dtype,
                    "compression": compression_arg,
                    "resolution": (float(dpi), float(dpi)),
                    "resolutionunit": "inch",
                }
                if page.photometric is not None:
                    kwargs["photometric"] = page.photometric
                if page.description is not None:
                    kwargs["description"] = page.description
                if page.tile is not None:
                    kwargs["tile"] = page.tile
                writer.write(page.data, **kwargs)
    except Exception as exc:  # pragma: no cover - exercised in integration flows
        raise ValueError(f"Failed to write TIFF image to {target_path}: {exc}") from exc
