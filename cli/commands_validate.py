"""Project validation command."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from cli.common import configure_cli_logging
from cli.runtime import validate_project_file


def validate_command(
    project: Annotated[
        Path,
        typer.Argument(..., exists=True, dir_okay=False, help="Saved .imagerect.json project"),
    ],
    quiet: Annotated[bool, typer.Option("--quiet", help="Only print errors")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", help="Enable verbose logging")] = False,
) -> None:
    configure_cli_logging(quiet=quiet, verbose=verbose)
    _project_data, report = validate_project_file(project)

    if not quiet:
        for warning in report.warnings:
            typer.echo(f"warning: {warning}", err=True)

    if report.ok:
        typer.echo(f"Project valid: {project}")
        return

    for error in report.errors:
        typer.echo(f"error: {error}", err=True)
    raise typer.Exit(code=1)
