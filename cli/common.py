"""CLI shared utilities."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

import typer

from core.logging_setup import configure_logging


def configure_cli_logging(*, quiet: bool, verbose: bool) -> Path:
    if quiet and verbose:
        raise typer.BadParameter("--quiet und --verbose schließen sich gegenseitig aus.")

    try:
        log_file = configure_logging()
    except OSError:
        fallback_dir = Path(tempfile.gettempdir()) / "imagerect-cli-logs"
        log_file = configure_logging(log_dir=fallback_dir)
    level = logging.WARNING if quiet else logging.DEBUG if verbose else logging.INFO
    logging.getLogger().setLevel(level)
    return log_file


def echo_json(payload: dict[str, Any]) -> None:
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))
