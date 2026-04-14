"""ImageRect command-line interface."""

from __future__ import annotations

import typer

from cli.commands_export import export_command
from cli.commands_inspect import inspect_command
from cli.commands_validate import validate_command

app = typer.Typer(
    name="imagerect-cli",
    help="Metric image rectification — command line interface.",
    no_args_is_help=True,
)
app.command("export")(export_command)
app.command("validate")(validate_command)
app.command("inspect")(inspect_command)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
