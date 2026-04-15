"""GPS and camera pose helpers for rough geospatial alignment."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS

from core.lens import LensProfile, build_camera_matrix

Point2D = tuple[float, float]
TransformerFactory = Callable[[int], Any]
METERS_PER_DEG_LAT = 111_320.0


def extract_gps_pose(image_path: str | Path) -> dict[str, Any] | None:
    """Extract GPS and orientation hints from image EXIF/XMP metadata."""

    path = Path(image_path)
    if not path.exists():
        return None

    with Image.open(path) as image:
        exif = image.getexif()
        if not exif:
            return _read_xmp_pose(path)

        exif_map = {TAGS.get(tag_id, str(tag_id)): value for tag_id, value in exif.items()}
        gps_info_raw = exif_map.get("GPSInfo")
        gps_info = (
            {GPSTAGS.get(key, str(key)): value for key, value in gps_info_raw.items()}
            if isinstance(gps_info_raw, dict)
            else {}
        )

    latitude = _gps_to_decimal(
        gps_info.get("GPSLatitude"),
        gps_info.get("GPSLatitudeRef"),
    )
    longitude = _gps_to_decimal(
        gps_info.get("GPSLongitude"),
        gps_info.get("GPSLongitudeRef"),
    )
    altitude = _to_float(gps_info.get("GPSAltitude"))
    heading = _to_float(gps_info.get("GPSImgDirection"))
    timestamp = str(exif_map.get("DateTimeOriginal") or exif_map.get("DateTime") or "")

    pose = {
        "latitude": latitude,
        "longitude": longitude,
        "altitude": altitude,
        "heading_deg": heading,
        "timestamp": timestamp or None,
    }
    xmp_pose = _read_xmp_pose(path)
    if xmp_pose is not None:
        pose.update({key: value for key, value in xmp_pose.items() if value is not None})

    if pose["latitude"] is None or pose["longitude"] is None:
        return xmp_pose
    return pose


def gps_offset_meters(origin_pose: dict[str, Any], target_pose: dict[str, Any]) -> Point2D | None:
    """Compute a rough local XY offset in meters between two GPS poses."""

    lat0 = _to_float(origin_pose.get("latitude"))
    lon0 = _to_float(origin_pose.get("longitude"))
    lat1 = _to_float(target_pose.get("latitude"))
    lon1 = _to_float(target_pose.get("longitude"))
    if None in {lat0, lon0, lat1, lon1}:
        return None
    assert lat0 is not None and lon0 is not None and lat1 is not None and lon1 is not None

    mean_lat_rad = np.deg2rad((lat0 + lat1) * 0.5)
    meters_per_deg_lat = METERS_PER_DEG_LAT
    meters_per_deg_lon = METERS_PER_DEG_LAT * float(np.cos(mean_lat_rad))
    dx = (lon1 - lon0) * meters_per_deg_lon
    dy = (lat1 - lat0) * meters_per_deg_lat
    return (float(dx), float(dy))


def decompose_homography_pose(
    homography_image_to_reference: np.ndarray,
    image_size: tuple[int, int],
    profile: LensProfile,
) -> dict[str, Any] | None:
    """
    Approximate camera pose from a homography and known intrinsics.

    Uses OpenCV decomposeHomographyMat to extract possible rotation and translation
    solutions, then selects the most plausible one based on geometric heuristics.
    """

    width, height = image_size
    camera_matrix = build_camera_matrix(
        profile.focal_length_mm,
        profile.sensor_width_mm,
        width,
        height,
    )
    try:
        # cv2.decomposeHomographyMat returns (count, rotations, translations, normals)
        # where rotations, translations, normals are sequences of arrays.
        res = cv2.decomposeHomographyMat(
            np.linalg.inv(homography_image_to_reference),
            camera_matrix,
        )
        if res is None or res[0] <= 0:
            return None
        _count, rotations, translations, normals = res
    except Exception:
        return None

    rotation, translation = _select_pose_solution(
        list(rotations), list(translations), list(normals)
    )
    yaw, pitch, roll = _rotation_matrix_to_euler(rotation)
    fov = 2.0 * np.degrees(np.arctan(profile.sensor_width_mm / (2.0 * profile.focal_length_mm)))
    return {
        "position_3d": [float(translation[0]), float(translation[1]), float(translation[2])],
        "rotation_matrix": rotation.tolist(),
        "yaw_deg": float(yaw),
        "pitch_deg": float(pitch),
        "roll_deg": float(roll),
        "field_of_view_deg": float(fov),
    }


def gps_to_reference_xy(
    gps_pose: dict[str, Any],
    reference_crs_epsg: int | None,
    transformer_factory: TransformerFactory | None = None,
) -> Point2D | None:
    """Transform WGS84 GPS metadata into reference XY coordinates."""

    latitude = _to_float(gps_pose.get("latitude"))
    longitude = _to_float(gps_pose.get("longitude"))
    if latitude is None or longitude is None or reference_crs_epsg is None:
        return None

    transformer = _transformer_for_epsg(reference_crs_epsg, transformer_factory)
    if transformer is None:
        return None

    x, y = transformer.transform(longitude, latitude)
    return (float(x), float(y))


def gps_to_reference_transform(
    gps_pose: dict[str, Any],
    reference_crs_epsg: int | None,
    transformer_factory: TransformerFactory | None = None,
) -> Point2D | None:
    """Backward-compatible alias used by tests and callers."""

    return gps_to_reference_xy(gps_pose, reference_crs_epsg, transformer_factory)


def build_camera_pose(
    homography_image_to_reference: np.ndarray,
    image_size: tuple[int, int],
    profile: LensProfile,
    gps_pose: dict[str, Any] | None = None,
    reference_crs_epsg: int | None = None,
    transformer_factory: TransformerFactory | None = None,
) -> dict[str, Any] | None:
    """Combine homography decomposition with optional GPS-derived position."""

    pose = decompose_homography_pose(
        homography_image_to_reference=homography_image_to_reference,
        image_size=image_size,
        profile=profile,
    )
    if pose is None:
        return None

    if gps_pose is None:
        return pose

    reference_xy = gps_to_reference_xy(gps_pose, reference_crs_epsg, transformer_factory)
    altitude = _to_float(gps_pose.get("altitude"))
    if reference_xy is not None:
        pose["position_3d"] = [
            float(reference_xy[0]),
            float(reference_xy[1]),
            float(altitude if altitude is not None else pose["position_3d"][2]),
        ]
    elif altitude is not None:
        pose["position_3d"][2] = float(altitude)

    pose["gps_pose"] = dict(gps_pose)
    return pose


def _read_xmp_pose(path: Path) -> dict[str, Any] | None:
    try:
        payload = path.read_bytes()
    except OSError:
        return None

    text = payload.decode("utf-8", errors="ignore")
    if "<x:xmpmeta" not in text:
        return None

    yaw = _regex_float(text, r'drone-dji:GimbalYawDegree="([^"]+)"')
    pitch = _regex_float(text, r'drone-dji:GimbalPitchDegree="([^"]+)"')
    roll = _regex_float(text, r'drone-dji:GimbalRollDegree="([^"]+)"')
    latitude = _regex_float(text, r'drone-dji:Latitude="([^"]+)"')
    longitude = _regex_float(text, r'drone-dji:Longitude="([^"]+)"')
    altitude = _regex_float(text, r'drone-dji:AbsoluteAltitude="([^"]+)"')
    if all(value is None for value in (yaw, pitch, roll, latitude, longitude, altitude)):
        return None
    return {
        "latitude": latitude,
        "longitude": longitude,
        "altitude": altitude,
        "heading_deg": yaw,
        "gimbal_pitch_deg": pitch,
        "gimbal_roll_deg": roll,
    }


def _gps_to_decimal(value: Any, ref: Any) -> float | None:
    if value is None:
        return None
    if not isinstance(value, tuple) or len(value) != 3:
        return None
    degrees = _to_float(value[0])
    minutes = _to_float(value[1])
    seconds = _to_float(value[2])
    if None in {degrees, minutes, seconds}:
        return None
    assert degrees is not None and minutes is not None and seconds is not None
    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    if str(ref).upper() in {"S", "W"}:
        decimal *= -1.0
    return float(decimal)


def _regex_float(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text)
    if match is None:
        return None
    return _to_float(match.group(1))


def _rotation_matrix_to_euler(rotation: np.ndarray) -> tuple[float, float, float]:
    sy = float(np.sqrt(rotation[0, 0] ** 2 + rotation[1, 0] ** 2))
    singular = sy < 1e-6
    if not singular:
        x = float(np.arctan2(rotation[2, 1], rotation[2, 2]))
        y = float(np.arctan2(-rotation[2, 0], sy))
        z = float(np.arctan2(rotation[1, 0], rotation[0, 0]))
    else:
        x = float(np.arctan2(-rotation[1, 2], rotation[1, 1]))
        y = float(np.arctan2(-rotation[2, 0], sy))
        z = 0.0
    return (np.degrees(z), np.degrees(y), np.degrees(x))


def _select_pose_solution(
    rotations: Sequence[np.ndarray],
    translations: Sequence[np.ndarray],
    normals: Sequence[np.ndarray],
) -> tuple[np.ndarray, np.ndarray]:
    best_index = 0
    best_score = float("-inf")
    for index, (rotation, translation, normal) in enumerate(
        zip(rotations, translations, normals, strict=False)
    ):
        translation_vec = np.asarray(translation, dtype=np.float64).reshape(-1)
        normal_vec = np.asarray(normal, dtype=np.float64).reshape(-1)
        _yaw, pitch, roll = _rotation_matrix_to_euler(rotation)
        score = 0.0
        if np.isfinite(rotation).all() and np.isfinite(translation_vec).all():
            score += 100.0
        if len(translation_vec) >= 3 and translation_vec[2] > 0.0:
            score += 50.0
        if len(normal_vec) >= 3 and normal_vec[2] > 0.0:
            score += 20.0
        if (
            len(translation_vec) >= 3
            and len(normal_vec) >= 3
            and float(np.dot(translation_vec[:3], normal_vec[:3])) > 0.0
        ):
            score += 10.0
        score -= abs(float(pitch)) * 0.1
        score -= abs(float(roll)) * 0.1
        if score > best_score:
            best_score = score
            best_index = index
    return rotations[best_index], np.asarray(translations[best_index], dtype=np.float64).reshape(-1)


def crs_transform_available() -> bool:
    try:
        from pyproj import Transformer
    except ImportError:
        return False
    return Transformer is not None


def _transformer_for_epsg(
    reference_crs_epsg: int,
    transformer_factory: TransformerFactory | None,
) -> Any | None:
    if transformer_factory is not None:
        return transformer_factory(reference_crs_epsg)

    try:
        from pyproj import Transformer
    except ImportError:
        return None

    return Transformer.from_crs("EPSG:4326", f"EPSG:{reference_crs_epsg}", always_xy=True)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if hasattr(value, "numerator") and hasattr(value, "denominator"):
        denominator = float(value.denominator)
        if denominator == 0.0:
            return None
        return float(value.numerator) / denominator
    if isinstance(value, tuple) and len(value) == 2:
        numerator = _to_float(value[0])
        fraction_denominator = _to_float(value[1])
        if numerator is None or fraction_denominator is None or fraction_denominator == 0.0:
            return None
        return numerator / fraction_denominator
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
