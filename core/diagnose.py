"""Build a diagnose ZIP for user bug reports."""

from __future__ import annotations

import importlib.metadata as metadata
import json
import logging
import os
import platform
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from core.logging_setup import log_directory

logger = logging.getLogger(__name__)


def collect_system_info() -> dict[str, object]:
    """Return a dict of system diagnostics without personal data."""

    def _version(package_name: str) -> str:
        try:
            return metadata.version(package_name)
        except metadata.PackageNotFoundError:
            return "not-installed"

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "executable": sys.executable,
        "packages": {
            name: _version(name)
            for name in (
                "PySide6",
                "opencv-python",
                "opencv-python-headless",
                "numpy",
                "ezdxf",
                "Pillow",
                "tifffile",
                "trimesh",
                "pye57",
            )
        },
    }


def build_diagnose_package(
    output_path: Path,
    project_file: Path | None = None,
) -> Path:
    """Bundle logs, system info, and an optional project JSON into a ZIP."""

    output_path = _safe_output_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_dir = log_directory()

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("system_info.json", json.dumps(collect_system_info(), indent=2))

        for log_file in sorted(log_dir.glob("imagerect.log*")):
            archive.write(log_file, arcname=f"logs/{log_file.name}")

        if project_file is not None and project_file.exists():
            archive.write(project_file, arcname=f"project/{project_file.name}")

    logger.info(
        "Built diagnose package | output=%s | project_included=%s",
        output_path,
        bool(project_file is not None and project_file.exists()),
    )
    return output_path


def _safe_output_path(output_path: Path) -> Path:
    resolved = output_path.expanduser().resolve(strict=False)
    parent = resolved.parent
    if _is_protected_directory(parent):
        raise ValueError("Diagnose-Paket darf nicht in Systemverzeichnisse geschrieben werden.")
    return resolved


def _is_protected_directory(path: Path) -> bool:
    protected_roots = _protected_roots()
    return any(path.is_relative_to(root) for root in protected_roots)


def _protected_roots() -> tuple[Path, ...]:
    if sys.platform.startswith("win"):
        return tuple(
            Path(value).resolve(strict=False)
            for variable_name in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)")
            if (value := os.environ.get(variable_name))
        )

    return (
        Path("/etc"),
        Path("/usr"),
        Path("/bin"),
        Path("/sbin"),
        Path("/lib"),
        Path("/lib64"),
        Path("/proc"),
        Path("/sys"),
        Path("/dev"),
        Path("/boot"),
        Path("/run"),
        Path("/var/lib"),
        Path("/var/run"),
    )
