from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from core import diagnose, image
from core.project import ProjectData
from core.reference2d import load_dxf
from core.reference3d import load_obj


def test_image_decompression_bomb_rejected(monkeypatch: Any, tmp_path: Path) -> None:
    image_path = tmp_path / "oversized.png"
    image_path.write_bytes(b"placeholder")

    def _bomb(*_args: object, **_kwargs: object) -> object:
        raise image.PILImage.DecompressionBombError("bomb")

    monkeypatch.setattr(image.PILImage, "open", _bomb)
    monkeypatch.setattr(
        image.cv2,
        "imread",
        lambda *_args, **_kwargs: pytest.fail("OpenCV should not decode rejected images"),
    )

    with pytest.raises(ValueError, match=r"Bild zu groß\. Limit: 500 Megapixel\."):
        image.load_image(image_path)


def test_dxf_malformed_fails_gracefully(tmp_path: Path) -> None:
    path = tmp_path / "broken.dxf"
    path.write_text("0\nSECTION\n2\nENTITIES\n0\nLINE\n8\nBROKEN\n", encoding="utf-8")

    with pytest.raises(ValueError, match="DXF-Datei konnte nicht gelesen werden:"):
        load_dxf(path)


def test_obj_malformed_fails_gracefully(tmp_path: Path) -> None:
    pytest.importorskip("trimesh")
    path = tmp_path / "broken.obj"
    path.write_text("v 0 0\nf nope\n", encoding="utf-8")

    with pytest.raises(ValueError, match="OBJ-Datei konnte nicht gelesen werden:"):
        load_obj(path)


def test_project_rejects_path_traversal(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_file = project_dir / "bad.imagerect.json"
    project_file.write_text(
        json.dumps(
            {
                "name": "bad",
                "image_path": "../outside.png",
                "reference_path": "reference.dxf",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Projektpfad verlässt das Projektverzeichnis"):
        ProjectData.load(project_file)


def test_project_resolves_relative_paths_from_project_file(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    asset_dir = project_dir / "assets"
    asset_dir.mkdir(parents=True)
    (asset_dir / "input.png").write_bytes(b"png")
    (asset_dir / "reference.dxf").write_text("0\nEOF\n", encoding="utf-8")
    project_file = project_dir / "good.imagerect.json"
    project_file.write_text(
        json.dumps(
            {
                "name": "good",
                "image_path": "assets/input.png",
                "reference_path": "assets/reference.dxf",
            }
        ),
        encoding="utf-8",
    )

    project = ProjectData.load(project_file)

    assert project.resolve_active_image_path() == (asset_dir / "input.png").resolve()
    assert project.resolve_reference_path() == (asset_dir / "reference.dxf").resolve()


@pytest.mark.skipif(sys.platform.startswith("win"), reason="Unix system path guard")
def test_build_diagnose_package_rejects_system_directory(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "imagerect.log").write_text("hello\n", encoding="utf-8")
    monkeypatch.setattr(diagnose, "log_directory", lambda: log_dir)

    with pytest.raises(ValueError, match="Systemverzeichnisse"):
        diagnose.build_diagnose_package(Path("/etc/imagerect-diagnose.zip"))
