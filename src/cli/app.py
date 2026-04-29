"""Typer root application — registers all subcommand groups."""
from __future__ import annotations

import typer

from src.cli.cost import cost_app
from src.cli.db import db_app
from src.cli.runs import runs_app

app = typer.Typer(
    name="gtm",
    help="GTM-OS — outbound + intelligence pipeline CLI",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)

app.add_typer(db_app, name="db")
app.add_typer(runs_app, name="runs")
app.add_typer(cost_app, name="cost")


@app.callback()
def main(
    ctx: typer.Context,
    log_level: str = typer.Option("INFO", "--log-level", envvar="LOG_LEVEL"),
    json_logs: bool = typer.Option(False, "--json-logs", envvar="JSON_LOGS"),
) -> None:
    from src.logging import configure_logging
    configure_logging(log_level=log_level, json_logs=json_logs)


if __name__ == "__main__":
    app()
