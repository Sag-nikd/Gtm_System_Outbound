"""Cost tracking — @track_vendor_call decorator + VendorCallService."""
from __future__ import annotations

import asyncio
import functools
import time
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any, TypeVar

import structlog
import yaml

from src.db.models.vendor_calls import VendorCall, VendorName
from src.db.session import get_session

log = structlog.get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Coroutine[Any, Any, Any]])

_pricing: dict[str, Any] | None = None


def _load_pricing() -> dict[str, Any]:
    global _pricing
    if _pricing is None:
        path = Path(__file__).parent.parent.parent / "config" / "vendor_pricing.yaml"
        with open(path) as f:
            _pricing = yaml.safe_load(f)
    return _pricing  # type: ignore[return-value]


def _compute_dollar_cost(vendor: str, endpoint: str, units: float | None) -> float | None:
    """Return dollar cost given vendor + endpoint + unit count, or None if unknown."""
    pricing = _load_pricing()
    vendor_cfg = pricing.get(vendor, {})
    ep_cfg = vendor_cfg.get(endpoint, {})
    rate = ep_cfg.get("rate")
    if rate is None or units is None:
        return None
    return round(units * float(rate), 6)


def track_vendor_call(
    vendor: str,
    endpoint: str,
    unit_calculator: Callable[..., float | None] | None = None,
) -> Callable[[F], F]:
    """
    Decorator for async vendor API methods.

    Logs a VendorCall row after each invocation. Never raises on logging failure
    so the main flow is never blocked.

    unit_calculator(result) -> float | None  — extract units from the return value.
    """
    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            success = True
            error_msg: str | None = None
            result: Any = None
            try:
                result = await fn(*args, **kwargs)
                return result
            except Exception as exc:
                success = False
                error_msg = str(exc)
                raise
            finally:
                latency_ms = int((time.monotonic() - start) * 1000)
                units: float | None = None
                if unit_calculator and result is not None:
                    try:
                        units = unit_calculator(result)
                    except Exception:
                        pass
                dollar_cost = _compute_dollar_cost(vendor, endpoint, units)

                # Fire-and-forget — never block caller on DB write
                asyncio.ensure_future(
                    _log_call(
                        vendor=vendor,
                        endpoint=endpoint,
                        units=units,
                        dollar_cost=dollar_cost,
                        success=success,
                        error_message=error_msg,
                        latency_ms=latency_ms,
                        run_id=kwargs.get("run_id"),
                    )
                )

        return wrapper  # type: ignore[return-value]
    return decorator


async def _log_call(
    vendor: str,
    endpoint: str,
    units: float | None,
    dollar_cost: float | None,
    success: bool,
    error_message: str | None,
    latency_ms: int,
    run_id: str | None = None,
) -> None:
    try:
        async with get_session() as session:
            call = VendorCall(
                run_id=run_id,
                vendor=VendorName(vendor),
                endpoint=endpoint,
                units_consumed=units,
                dollar_cost=dollar_cost,
                success=success,
                error_message=error_message,
                latency_ms=latency_ms,
            )
            session.add(call)
    except Exception as exc:
        log.warning("cost_tracker.log_failed", vendor=vendor, error=str(exc))


class VendorCallService:
    """Query helpers for cost reporting."""

    @staticmethod
    async def summary(run_id: str | None = None) -> dict[str, Any]:
        from sqlalchemy import func, select

        from src.db.models.vendor_calls import VendorCall as VC

        async with get_session() as session:
            q = select(
                VC.vendor,
                func.count().label("calls"),
                func.sum(VC.dollar_cost).label("total_cost"),
                func.avg(VC.latency_ms).label("avg_latency_ms"),
            ).group_by(VC.vendor)

            if run_id:
                q = q.where(VC.run_id == run_id)

            result = await session.execute(q)
            rows = result.all()

        return {
            row.vendor: {
                "calls": row.calls,
                "total_cost_usd": round(float(row.total_cost or 0), 4),
                "avg_latency_ms": round(float(row.avg_latency_ms or 0), 1),
            }
            for row in rows
        }

    @staticmethod
    def forecast(contacts: int) -> dict[str, float]:
        """Rough dollar forecast for a campaign targeting N contacts."""
        pricing = _load_pricing()
        zb_rate = pricing.get("zerobounce", {}).get("validate_email", {}).get("rate", 0.008)
        return {
            "zerobounce_validation": round(contacts * float(zb_rate), 2),
            "total_estimated_usd": round(contacts * float(zb_rate), 2),
            "note": "Excludes vendor plan costs (Apollo, HubSpot, Instantly)",
        }
