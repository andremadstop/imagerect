from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from core.export import RectificationExportResult, export_rectified_image
from core.project import ControlPoint, ProjectData
from core.transform import HomographyResult, solve_planar_homography


@dataclass(frozen=True, slots=True)
class GoldenExportCase:
    stem: str
    output_format: str
    dpi: float
    tolerance: float


REFERENCE_POINTS = np.array(
    [[0.0, 0.0], [400.0, 0.0], [400.0, 300.0], [0.0, 300.0]],
    dtype=np.float32,
)
IMAGE_POINTS = np.array(
    [[120.0, 420.0], [620.0, 360.0], [560.0, 90.0], [170.0, 120.0]],
    dtype=np.float32,
)
GOLDEN_CASES = (
    GoldenExportCase(
        stem="golden_output_100dpi",
        output_format="tiff",
        dpi=100.0,
        tolerance=0.0,
    ),
    GoldenExportCase(
        stem="golden_output_300dpi",
        output_format="tiff",
        dpi=300.0,
        tolerance=0.0,
    ),
    GoldenExportCase(
        stem="golden_output_jpeg",
        output_format="jpeg",
        dpi=300.0,
        tolerance=1.0,
    ),
)


def golden_dir() -> Path:
    return Path(__file__).with_name("golden")


def golden_project_path() -> Path:
    return golden_dir() / "golden_project.imagerect.json"


def golden_source_path() -> Path:
    return golden_dir() / "golden_source.png"


def golden_reference_path() -> Path:
    return golden_dir() / "golden_reference.dxf"


def build_golden_source_image() -> np.ndarray:
    plane = np.zeros((301, 401, 3), dtype=np.uint8)
    plane[:] = (240, 240, 240)
    cv2.rectangle(plane, (0, 0), (400, 300), (20, 20, 20), 3)
    cv2.line(plane, (0, 150), (400, 150), (0, 0, 255), 2)
    cv2.circle(plane, (200, 150), 48, (255, 0, 0), 3)
    cv2.putText(plane, "IR", (155, 175), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (10, 10, 10), 3)

    source = np.zeros((520, 760, 3), dtype=np.uint8)
    homography_ref_to_image = cv2.getPerspectiveTransform(REFERENCE_POINTS, IMAGE_POINTS)
    cv2.warpPerspective(
        plane,
        homography_ref_to_image,
        (760, 520),
        dst=source,
        borderMode=cv2.BORDER_TRANSPARENT,
    )
    return source


def build_golden_solver_result() -> HomographyResult:
    return solve_planar_homography(IMAGE_POINTS.tolist(), REFERENCE_POINTS.tolist())


def build_golden_control_points() -> list[ControlPoint]:
    result = build_golden_solver_result()
    return [
        ControlPoint(
            id=index + 1,
            label=f"P{index + 1}",
            image_xy=(float(image_xy[0]), float(image_xy[1])),
            reference_xy=(float(reference_xy[0]), float(reference_xy[1])),
            residual=result.residuals[index],
            residual_vector=result.residual_vectors[index],
        )
        for index, (image_xy, reference_xy) in enumerate(
            zip(IMAGE_POINTS.tolist(), REFERENCE_POINTS.tolist(), strict=True)
        )
    ]


def build_golden_project() -> ProjectData:
    result = build_golden_solver_result()
    project = ProjectData(name="golden")
    project.image_path = "golden_source.png"
    project.reference_path = "golden_reference.dxf"
    project.reference_type = "dxf"
    project.units = "mm"
    project.points = build_golden_control_points()
    project.transform_matrix = result.matrix.tolist()
    project.rms_error = result.rms_error
    project.warnings = list(result.warnings)
    project.export_settings.output_format = "tiff"
    project.export_settings.dpi = 100.0
    project.export_settings.bit_depth = 8
    project.export_settings.resampling = "bilinear"
    return project


def export_golden_case(case: GoldenExportCase, output_dir: Path) -> RectificationExportResult:
    result = build_golden_solver_result()
    output_dir.mkdir(parents=True, exist_ok=True)
    return export_rectified_image(
        source_image=build_golden_source_image(),
        homography_image_to_reference=result.matrix,
        control_points=build_golden_control_points(),
        output_path=output_dir / case.stem,
        pixel_size=1.0,
        units="mm",
        output_format=case.output_format,
        dpi=case.dpi,
        bit_depth=8,
        resampling="bilinear",
        reference_extents=((0.0, 0.0), (400.0, 300.0)),
        project_name="golden",
        rms_error=result.rms_error,
        warnings=result.warnings,
    )
