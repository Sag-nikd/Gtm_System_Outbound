"""gtm cost — cost tracking and forecasting commands."""
from __future__ import annotations

import asyncio
import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

cost_app = typer.Typer(help="Cost tracking and forecasting", no_args_is_help=True)
console = Console()


@cost_app.command("summary")
def cost_summary(
    run_id: Optional[str] = typer.Option(None, "--run-id", help="Filter to a specific run"),
) -> None:
    """Show cost summary by vendor."""
    from src.cost.tracker import VendorCallService

    async def _show() -> None:
        summary = await VendorCallService.summary(run_id=run_id)
        if not summary:
            console.print("[dim]No vendor calls recorded yet.[/dim]")
            return

        tbl = Table(title="Vendor call costs" + (f" (run {run_id[:8]})" if run_id else ""))
        tbl.add_column("Vendor")
        tbl.add_column("Calls", justify="right")
        tbl.add_column("Cost (USD)", justify="right")
        tbl.add_column("Avg latency (ms)", justify="right")

        total = 0.0
        for vendor, data in sorted(summary.items()):
            cost = data["total_cost_usd"]
            total += cost
            tbl.add_row(
                vendor,
                str(data["calls"]),
                f"${cost:.4f}",
                f"{data['avg_latency_ms']:.0f}",
            )

        console.print(tbl)
        console.print(f"\n[bold]Total: ${total:.4f} USD[/bold]")

    asyncio.run(_show())


@cost_app.command("forecast")
def cost_forecast(
    contacts: int = typer.Option(..., "--contacts", help="Number of contacts to target"),
) -> None:
    """Estimate campaign cost for N contacts."""
    from src.cost.tracker import VendorCallService

    forecast = VendorCallService.forecast(contacts)
    console.print(f"\n[bold]Cost forecast for {contacts:,} contacts:[/bold]")
    console.print_json(json.dumps(forecast, indent=2))
