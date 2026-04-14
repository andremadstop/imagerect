#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import cv2

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.golden_case import (  # noqa: E402
    GOLDEN_CASES,
    build_golden_project,
    build_golden_source_image,
    export_golden_case,
    golden_dir,
    golden_project_path,
    golden_reference_path,
    golden_source_path,
)


def main() -> None:
    output_dir = golden_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        REPO_ROOT / "tests" / "sample_data" / "synthetic_reference.dxf", golden_reference_path()
    )

    source_image = build_golden_source_image()
    if not cv2.imwrite(str(golden_source_path()), source_image):
        raise ValueError(f"Failed to write golden source image to {golden_source_path()}")

    project = build_golden_project()
    project.save(golden_project_path())

    for case in GOLDEN_CASES:
        export_golden_case(case, output_dir)

    print(f"Regenerated golden fixtures in {output_dir}")


if __name__ == "__main__":
    main()
