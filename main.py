"""Application entry point for ImageRect."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui.theme import apply_theme


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ImageRect Phase-2 MVP")
    parser.add_argument("--project", type=Path, help="Open a saved .imagerect.json project")
    parser.add_argument("--image", type=Path, help="Open an image on startup")
    parser.add_argument(
        "--reference",
        type=Path,
        help="Open a DXF, E57, or OBJ reference on startup",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Run an offscreen synthetic export smoke test and exit",
    )
    parser.add_argument(
        "--smoke-output",
        type=Path,
        default=Path("build/smoke"),
        help="Output directory for the smoke test",
    )
    args = parser.parse_args(argv)

    if args.smoke_test:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
    apply_theme(app)
    window = MainWindow()

    try:
        if args.project:
            window.load_project_file(args.project)
        if args.image:
            window.load_image_file(args.image)
        if args.reference:
            if args.reference.suffix.lower() in {".e57", ".obj"}:
                window.load_3d_reference_file(args.reference)
            else:
                window.load_reference_file(args.reference)
    except Exception as exc:
        print(f"startup error: {exc}", file=sys.stderr)
        return 1

    if args.smoke_test:
        result_holder: dict[str, str] = {}

        def _run() -> None:
            try:
                result = window.run_synthetic_smoke_test(args.smoke_output)
                result_holder["result"] = (
                    f"smoke-test export={result.image_path} metadata={result.metadata_path}"
                )
                app.exit(0)
            except Exception as exc:  # pragma: no cover - exercised by manual verification
                result_holder["error"] = str(exc)
                app.exit(1)

        QTimer.singleShot(0, _run)
        exit_code = app.exec()
        if "result" in result_holder:
            print(result_holder["result"])
        if "error" in result_holder:
            print(f"smoke-test failed: {result_holder['error']}", file=sys.stderr)
        return int(exit_code)

    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
