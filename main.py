"""Application entry point for ImageRect."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from core.logging_setup import configure_logging
from ui.main_window import MainWindow
from ui.theme import apply_theme
from ui.workspace_controller import WorkspaceController

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    if (
        os.environ.get("QT_QPA_PLATFORM") is None
        and os.environ.get("DISPLAY") is None
        and os.environ.get("WAYLAND_DISPLAY") is None
    ):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

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

    smoke_log_dir: tempfile.TemporaryDirectory[str] | None = None
    try:
        log_dir = None
        if args.smoke_test:
            smoke_log_dir = tempfile.TemporaryDirectory(prefix="imagerect-smoke-logs-")
            log_dir = Path(smoke_log_dir.name)
        log_file = configure_logging(log_dir=log_dir)
        logger.info("Application start | smoke_test=%s | log_file=%s", args.smoke_test, log_file)

        app = QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
        app_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        icon_path = app_root / "assets" / "icon.png"
        if icon_path.exists():
            app.setWindowIcon(QIcon(str(icon_path)))
        apply_theme(app)
        window = MainWindow() if args.smoke_test else None
        controller = None if args.smoke_test else WorkspaceController()

        if args.smoke_test and window is not None:
            if args.project:
                window.load_project_file(args.project)
            if args.image:
                window.load_image_file(args.image)
            if args.reference:
                if args.reference.suffix.lower() in {".e57", ".obj"}:
                    window.load_3d_reference_file(args.reference)
                else:
                    window.load_reference_file(args.reference)
        elif controller is not None:
            if args.project:
                controller.load_project_file(args.project)
            if args.image:
                controller.show_rectify_workspace()
                controller.rectify_window.load_image_file(args.image)
            if args.reference:
                if args.reference.suffix.lower() in {".e57", ".obj"}:
                    controller.rectify_window.load_3d_reference_file(args.reference)
                    controller.show_three_d_workspace()
                else:
                    controller.rectify_window.load_reference_file(args.reference)
                    controller.show_rectify_workspace()
    except Exception as exc:
        logger.exception("Application startup failed")
        print(f"startup error: {exc}", file=sys.stderr)
        return 1

    try:
        if args.smoke_test:
            result_holder: dict[str, str] = {}

            def _run() -> None:
                try:
                    assert window is not None
                    result = window.run_synthetic_smoke_test(args.smoke_output)
                    result_holder["result"] = (
                        f"smoke-test export={result.image_path} metadata={result.metadata_path}"
                    )
                    logger.info(
                        "Smoke test finished | export=%s | metadata=%s",
                        result.image_path,
                        result.metadata_path,
                    )
                    app.exit(0)
                except Exception as exc:  # pragma: no cover - exercised by manual verification
                    result_holder["error"] = str(exc)
                    logger.exception("Smoke test failed")
                    app.exit(1)

            QTimer.singleShot(0, _run)
            smoke_exit_code = int(app.exec())
            if "result" in result_holder:
                print(result_holder["result"])
            if "error" in result_holder:
                print(f"smoke-test failed: {result_holder['error']}", file=sys.stderr)
            return smoke_exit_code

        assert controller is not None
        controller.show_initial_ui()
        if args.project or args.image or args.reference:
            controller.show_rectify_workspace()
        ui_exit_code = int(app.exec())
        logger.info("Application exit | code=%s", ui_exit_code)
        return ui_exit_code
    finally:
        logging.shutdown()
        if smoke_log_dir is not None:
            smoke_log_dir.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
