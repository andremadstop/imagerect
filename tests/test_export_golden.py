from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest
import tifffile

from core.export import export_rectified_image
from core.image import load_image
from core.project import ProjectData
from tests.golden_case import (
    GOLDEN_CASES,
    GoldenExportCase,
    golden_dir,
    golden_project_path,
)


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=[case.stem for case in GOLDEN_CASES])
def test_export_matches_golden(case: GoldenExportCase, tmp_path: Path) -> None:
    project_path = golden_project_path()
    project = ProjectData.load(project_path)
    source_path = _resolve_fixture_path(project_path, project.image_path)
    golden_image_path = _golden_image_path(case)
    golden_metadata_path = golden_image_path.with_suffix(".json")
    source_image = load_image(source_path)
    assert project.transform_matrix is not None

    export = export_rectified_image(
        source_image=source_image,
        homography_image_to_reference=np.asarray(project.transform_matrix, dtype=np.float64),
        control_points=project.points,
        output_path=tmp_path / case.stem,
        pixel_size=project.export_settings.pixel_size,
        units=project.units,
        output_format=case.output_format,
        dpi=case.dpi,
        bit_depth=project.export_settings.bit_depth,
        resampling=project.export_settings.resampling,
        reference_extents=((0.0, 0.0), (400.0, 300.0)),
        project_name=project.name,
        rms_error=project.rms_error,
        warnings=project.warnings,
    )

    _assert_image_matches_golden(export.image_path, golden_image_path, case.tolerance)
    assert _normalized_metadata(export.metadata_path) == _normalized_metadata(golden_metadata_path)
    if export.image_path.suffix == ".tiff":
        _assert_tiff_resolution_matches(export.image_path, golden_image_path)
    assert source_image.shape == (520, 760, 3)


def _resolve_fixture_path(project_path: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    return (project_path.parent / candidate).resolve()


def _golden_image_path(case: GoldenExportCase) -> Path:
    suffix = ".jpg" if case.output_format == "jpeg" else ".tiff"
    return golden_dir() / f"{case.stem}{suffix}"


def _assert_image_matches_golden(actual: Path, golden: Path, tolerance: float) -> None:
    actual_image = cv2.imread(str(actual), cv2.IMREAD_UNCHANGED)
    golden_image = cv2.imread(str(golden), cv2.IMREAD_UNCHANGED)

    assert actual_image is not None
    assert golden_image is not None
    assert actual_image.shape == golden_image.shape
    difference = np.abs(actual_image.astype(np.float32) - golden_image.astype(np.float32)).mean()
    assert difference <= tolerance, f"Mean pixel diff {difference:.4f} exceeds {tolerance:.4f}"


def _normalized_metadata(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("timestamp", None)
    return payload


def _assert_tiff_resolution_matches(actual: Path, golden: Path) -> None:
    with tifffile.TiffFile(actual) as actual_tiff, tifffile.TiffFile(golden) as golden_tiff:
        actual_tags = actual_tiff.pages[0].tags
        golden_tags = golden_tiff.pages[0].tags
        assert actual_tags["XResolution"].value == golden_tags["XResolution"].value
        assert actual_tags["YResolution"].value == golden_tags["YResolution"].value
        assert actual_tags["ResolutionUnit"].value == golden_tags["ResolutionUnit"].value
