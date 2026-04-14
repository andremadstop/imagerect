"""Lens distortion correction using Brown-Conrady parameters."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np


@dataclass(slots=True)
class LensProfile:
    name: str
    focal_length_mm: float
    sensor_width_mm: float
    k1: float = 0.0
    k2: float = 0.0
    p1: float = 0.0
    p2: float = 0.0
    k3: float = 0.0

    def to_dict(self) -> dict[str, float | str]:
        return asdict(self)


def lens_profile_from_dict(payload: dict[str, Any]) -> LensProfile:
    return LensProfile(
        name=str(payload.get("name", "Custom")),
        focal_length_mm=float(payload["focal_length_mm"]),
        sensor_width_mm=float(payload["sensor_width_mm"]),
        k1=float(payload.get("k1", 0.0)),
        k2=float(payload.get("k2", 0.0)),
        p1=float(payload.get("p1", 0.0)),
        p2=float(payload.get("p2", 0.0)),
        k3=float(payload.get("k3", 0.0)),
    )


def build_camera_matrix(
    focal_length_mm: float,
    sensor_width_mm: float,
    image_width_px: int,
    image_height_px: int,
) -> np.ndarray:
    """Build a 3x3 intrinsic matrix from physical camera parameters."""

    if sensor_width_mm <= 0.0:
        raise ValueError("Sensor width must be greater than zero")
    fx = (focal_length_mm / sensor_width_mm) * image_width_px
    fy = fx
    cx = image_width_px / 2.0
    cy = image_height_px / 2.0
    return np.array([[fx, 0.0, cx], [0.0, fy, cy], [0.0, 0.0, 1.0]], dtype=np.float64)


def build_distortion_coefficients(profile: LensProfile) -> np.ndarray:
    return np.array(
        [profile.k1, profile.k2, profile.p1, profile.p2, profile.k3],
        dtype=np.float64,
    )


def apply_lens_correction(
    image: np.ndarray,
    profile: LensProfile,
) -> np.ndarray:
    """Undistort an image using the given lens profile."""

    height, width = image.shape[:2]
    camera_matrix = build_camera_matrix(
        profile.focal_length_mm,
        profile.sensor_width_mm,
        width,
        height,
    )
    distortion = build_distortion_coefficients(profile)
    new_camera_matrix, _roi = cv2.getOptimalNewCameraMatrix(
        camera_matrix,
        distortion,
        (width, height),
        0.0,
        (width, height),
    )
    return cv2.undistort(image, camera_matrix, distortion, None, new_camera_matrix)


def load_presets() -> list[LensProfile]:
    """Load built-in camera presets."""

    path = Path(__file__).with_name("lens_presets.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [lens_profile_from_dict(entry) for entry in payload]


def read_exif(image_path: Path) -> dict[str, Any]:
    """Extract a flat EXIF mapping from an image file."""

    from PIL import Image
    from PIL.ExifTags import TAGS

    with Image.open(image_path) as image:
        raw = image.getexif()
        if not raw:
            return {}
        exif: dict[str, Any] = {}
        for tag_id, value in raw.items():
            exif[TAGS.get(tag_id, str(tag_id))] = value
    return exif


def match_preset(exif: dict[str, Any], presets: list[LensProfile]) -> LensProfile | None:
    """Match EXIF camera information to the closest preset by loose substring."""

    make = str(exif.get("Make", "")).strip().lower()
    model = str(exif.get("Model", "")).strip().lower()
    combined = f"{make} {model}".strip()
    if not combined:
        return None

    for preset in presets:
        preset_key = preset.name.lower()
        words = [word for word in preset_key.split() if len(word) > 2]
        if words and any(word in combined for word in words):
            return preset
    return None


def exif_float(exif: dict[str, Any], key: str) -> float | None:
    """Best-effort float conversion for EXIF numeric values."""

    if key not in exif:
        return None
    return _to_float(exif[key])


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, tuple) and len(value) == 2:
        numerator = _to_float(value[0])
        denominator = _to_float(value[1])
        if numerator is None or denominator is None or denominator == 0.0:
            return None
        return numerator / denominator
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
