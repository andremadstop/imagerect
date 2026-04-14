"""Application-wide logging configuration."""

from __future__ import annotations

import logging
import logging.handlers
import os
import platform
import sys
from pathlib import Path

_HANDLER_MARKER = "_imagerect_handler"
_MAX_LOG_BYTES = 2_000_000
_BACKUP_COUNT = 5


def log_directory() -> Path:
    """Return the platform-appropriate log directory, creating it if needed."""

    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        log_dir = base / "ImageRect" / "logs"
    elif sys.platform == "darwin":
        log_dir = Path.home() / "Library" / "Logs" / "ImageRect"
    else:
        log_dir = Path.home() / ".imagerect" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def configure_logging(level: int | None = None, log_dir: Path | None = None) -> Path:
    """Configure root logger with rotating file + stderr handlers."""

    resolved_level = _resolve_log_level(level)
    target_dir = log_dir if log_dir is not None else log_directory()
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / "imagerect.log"

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=_MAX_LOG_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(resolved_level)
    setattr(file_handler, _HANDLER_MARKER, True)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.WARNING)
    setattr(stream_handler, _HANDLER_MARKER, True)

    root = logging.getLogger()
    root.setLevel(resolved_level)
    _remove_imagerect_handlers(root)
    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    root.info(
        "ImageRect logging initialized | platform=%s | python=%s | log_file=%s",
        platform.platform(),
        platform.python_version(),
        log_file,
    )
    return log_file


def _resolve_log_level(level: int | None) -> int:
    if level is not None:
        return level

    raw_level = os.environ.get("IMAGERECT_LOG_LEVEL", "INFO").strip().upper()
    resolved = logging.getLevelNamesMapping().get(raw_level)
    if isinstance(resolved, int):
        return resolved
    return logging.INFO


def _remove_imagerect_handlers(root: logging.Logger) -> None:
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            root.removeHandler(handler)
            handler.close()
