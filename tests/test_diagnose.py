from __future__ import annotations

import json
import zipfile
from pathlib import Path

from core import diagnose


def test_collect_system_info_has_required_keys() -> None:
    info = diagnose.collect_system_info()

    assert isinstance(info["timestamp"], str)
    assert isinstance(info["platform"], str)
    assert isinstance(info["python"], str)
    assert isinstance(info["executable"], str)
    assert isinstance(info["packages"], dict)


def test_build_diagnose_package_creates_zip_with_logs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "imagerect.log").write_text("hello\n", encoding="utf-8")
    monkeypatch.setattr(diagnose, "log_directory", lambda: log_dir)

    output_path = diagnose.build_diagnose_package(tmp_path / "diagnose.zip")

    assert output_path.exists()
    with zipfile.ZipFile(output_path) as archive:
        assert "system_info.json" in archive.namelist()
        assert "logs/imagerect.log" in archive.namelist()


def test_build_diagnose_package_includes_project_when_given(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "imagerect.log").write_text("hello\n", encoding="utf-8")
    project_file = tmp_path / "example.imagerect.json"
    project_file.write_text(json.dumps({"name": "Example"}), encoding="utf-8")
    monkeypatch.setattr(diagnose, "log_directory", lambda: log_dir)

    output_path = diagnose.build_diagnose_package(tmp_path / "diagnose.zip", project_file)

    with zipfile.ZipFile(output_path) as archive:
        assert f"project/{project_file.name}" in archive.namelist()


def test_build_diagnose_package_excludes_missing_project(
    monkeypatch,
    tmp_path: Path,
) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)
    (log_dir / "imagerect.log").write_text("hello\n", encoding="utf-8")
    missing_project = tmp_path / "missing.imagerect.json"
    monkeypatch.setattr(diagnose, "log_directory", lambda: log_dir)

    output_path = diagnose.build_diagnose_package(tmp_path / "diagnose.zip", missing_project)

    with zipfile.ZipFile(output_path) as archive:
        assert all(not name.startswith("project/") for name in archive.namelist())
