from __future__ import annotations

import json
import shutil
from pathlib import Path

import cv2
import pytest
from typer.testing import CliRunner

from cli import commands_export
from cli.main import app
from core.export import RectificationExportResult
from core.project import ProjectData
from tests.golden_case import (
    build_golden_control_points,
    build_golden_solver_result,
    build_golden_source_image,
)

runner = CliRunner()


def test_validate_accepts_solved_project(tmp_path: Path) -> None:
    project_path = _write_cli_project(tmp_path)

    result = runner.invoke(app, ["validate", str(project_path)])

    assert result.exit_code == 0
    assert "Project valid:" in result.output


def test_validate_rejects_path_traversal(tmp_path: Path) -> None:
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"x")
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_path = project_dir / "bad.imagerect.json"
    project_path.write_text(
        json.dumps(
            {
                "name": "bad",
                "image_path": "../outside.png",
                "reference_path": "reference.dxf",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["validate", str(project_path)])

    assert result.exit_code == 1
    assert "Projektpfad verlässt das Projektverzeichnis" in result.output


def test_export_command_writes_rectified_output(tmp_path: Path) -> None:
    project_path = _write_cli_project(tmp_path)
    output_root = tmp_path / "cli-export"

    result = runner.invoke(
        app,
        [
            "export",
            str(project_path),
            "--output",
            str(output_root),
            "--format",
            "png",
            "--dpi",
            "150",
        ],
    )

    assert result.exit_code == 0
    assert (tmp_path / "cli-export.png").exists()
    assert (tmp_path / "cli-export.json").exists()
    assert "Exported image:" in result.output


def test_export_command_passes_reference_segments_for_tiff_exports(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_path = _write_cli_project(tmp_path)
    project = ProjectData.load(project_path)
    project.export_settings.multi_layer = True
    project.save(project_path)

    captured: dict[str, object] = {}

    def fake_export_rectified_image(**kwargs: object) -> RectificationExportResult:
        captured.update(kwargs)
        return RectificationExportResult(
            image_path=tmp_path / "cli-export.tiff",
            metadata_path=tmp_path / "cli-export.json",
            width=100,
            height=100,
            pixel_size=1.0,
            bounds_min=(0.0, 0.0),
            bounds_max=(100.0, 100.0),
        )

    monkeypatch.setattr(commands_export, "export_rectified_image", fake_export_rectified_image)

    result = runner.invoke(
        app,
        [
            "export",
            str(project_path),
            "--output",
            str(tmp_path / "cli-export"),
            "--format",
            "tiff",
        ],
    )

    assert result.exit_code == 0
    assert captured["reference_segments"]


def test_inspect_image_reports_dimensions(tmp_path: Path) -> None:
    image_path = tmp_path / "inspect.png"
    source_image = build_golden_source_image()
    if not cv2.imwrite(str(image_path), source_image):
        raise ValueError(f"Could not write inspect image: {image_path}")

    result = runner.invoke(app, ["inspect", str(image_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["type"] == "image"
    assert payload["width"] == 760
    assert payload["height"] == 520


def test_inspect_dxf_reports_layers(tmp_path: Path) -> None:
    reference_path = tmp_path / "reference.dxf"
    shutil.copyfile(
        Path(__file__).parent / "sample_data" / "synthetic_reference.dxf", reference_path
    )

    result = runner.invoke(app, ["inspect", str(reference_path)])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["type"] == "dxf"
    assert "OUTLINE" in payload["layers"]
    assert "GRID" in payload["layers"]
    assert payload["entity_counts"]["LINE"] == 6


def _write_cli_project(tmp_path: Path) -> Path:
    project = ProjectData(name="cli-golden")
    source_path = tmp_path / "source.png"
    if not cv2.imwrite(str(source_path), build_golden_source_image()):
        raise ValueError(f"Could not write CLI source image: {source_path}")
    reference_path = tmp_path / "reference.dxf"
    shutil.copyfile(
        Path(__file__).parent / "sample_data" / "synthetic_reference.dxf", reference_path
    )

    result = build_golden_solver_result()
    project.image_path = source_path.name
    project.reference_path = reference_path.name
    project.reference_type = "dxf"
    project.units = "mm"
    project.points = build_golden_control_points()
    project.transform_matrix = result.matrix.tolist()
    project.rms_error = result.rms_error
    project.warnings = list(result.warnings)
    project.export_settings.output_format = "tiff"
    project.export_settings.dpi = 100.0
    project.export_settings.pixel_size = 1.0
    project.export_settings.bit_depth = 8
    project.export_settings.resampling = "bilinear"

    project_path = tmp_path / "project.imagerect.json"
    project.save(project_path)
    return project_path
