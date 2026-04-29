"""gtm runs — pipeline run inspection commands."""
from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console
from rich.table import Table

runs_app = typer.Typer(help="Inspect pipeline runs", no_args_is_help=True)
console = Console()


@runs_app.command("list")
def runs_list(limit: int = typer.Option(20, "--limit", "-n")) -> None:
    """List recent pipeline runs."""
    from src.db.repository.runs import PipelineRunRepository
    from src.db.session import get_session

    async def _list() -> None:
        async with get_session() as session:
            repo = PipelineRunRepository(session)
            runs = await repo.list_recent(limit=limit)

        tbl = Table(title=f"Last {limit} pipeline runs")
        tbl.add_column("ID", style="dim")
        tbl.add_column("Status")
        tbl.add_column("Started")
        tbl.add_column("Completed")

        for run in runs:
            status_style = {"completed": "green", "failed": "red", "running": "yellow"}.get(
                run.status.value, ""
            )
            tbl.add_row(
                run.id[:8],
                f"[{status_style}]{run.status.value}[/{status_style}]",
                str(run.started_at)[:19],
                str(run.completed_at)[:19] if run.completed_at else "—",
            )
        console.print(tbl)

    asyncio.run(_list())


@runs_app.command("show")
def runs_show(run_id: str = typer.Argument(..., help="Pipeline run ID (full or prefix)")) -> None:
    """Show details for a specific pipeline run."""
    from src.db.repository.runs import PipelineRunRepository
    from src.db.session import get_session

    async def _show() -> None:
        async with get_session() as session:
            repo = PipelineRunRepository(session)
            # Support prefix lookup
            all_runs = await repo.list_recent(limit=1000)
            matches = [r for r in all_runs if r.id.startswith(run_id)]
            if not matches:
                console.print(f"[red]No run found matching '{run_id}'[/red]")
                raise typer.Exit(1)
            run = matches[0]
            events = await repo.events_for_run(run.id)

        console.print(f"[bold]Run {run.id}[/bold]")
        console.print(f"  Status:    {run.status.value}")
        console.print(f"  Started:   {run.started_at}")
        console.print(f"  Completed: {run.completed_at or '—'}")

        if run.summary:
            summary = json.loads(run.summary)
            console.print("\n[bold]Summary:[/bold]")
            console.print_json(json.dumps(summary))

        if events:
            console.print(f"\n[bold]Events ({len(events)}):[/bold]")
            for ev in events:
                console.print(f"  [{ev.created_at!s:.19}] {ev.stage or '—'} / {ev.event_type}")

    asyncio.run(_show())
