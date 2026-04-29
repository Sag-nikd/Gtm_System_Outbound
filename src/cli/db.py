"""gtm db — database management commands."""
from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

db_app = typer.Typer(help="Database management", no_args_is_help=True)
console = Console()


@db_app.command("init")
def db_init() -> None:
    """Create the database and run all migrations."""
    from alembic import command
    from alembic.config import Config

    from src.config.settings import get_settings

    settings = get_settings()
    console.print(f"Initialising database at [bold]{settings.db_url}[/bold]")

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    console.print("[green]Database initialised.[/green]")


@db_app.command("migrate")
def db_migrate() -> None:
    """Run pending Alembic migrations (upgrade head)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    console.print("[green]Migrations applied.[/green]")


@db_app.command("status")
def db_status() -> None:
    """Show current migration version and row counts per table."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import func, select, text

    from src.db.session import get_session

    cfg = Config("alembic.ini")
    console.print("[bold]Migration version:[/bold]")
    command.current(cfg, verbose=False)

    table_names = ["companies", "contacts", "pipeline_runs", "run_events", "vendor_calls"]

    async def _counts() -> dict[str, int]:
        counts: dict[str, int] = {}
        async with get_session() as session:
            for tbl in table_names:
                result = await session.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
                counts[tbl] = result.scalar_one()
        return counts

    counts = asyncio.run(_counts())

    tbl = Table(title="Row counts")
    tbl.add_column("Table")
    tbl.add_column("Rows", justify="right")
    for name, count in counts.items():
        tbl.add_row(name, str(count))
    console.print(tbl)


@db_app.command("reset")
def db_reset(yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation")) -> None:
    """Drop the database file and re-initialise."""
    from src.config.settings import get_settings

    settings = get_settings()
    db_path = settings.data_dir / "gtm_os.db"

    if not yes:
        typer.confirm(f"This will delete {db_path}. Continue?", abort=True)

    if db_path.exists():
        db_path.unlink()
        console.print(f"Deleted [red]{db_path}[/red]")

    db_init()
