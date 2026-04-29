"""
GTM Pipeline Runner — independent stage execution and scheduling CLI.

Usage:
  python -m src.runner stage1            Run a single stage
  python -m src.runner stage1 stage2     Run specified stages in order
  python -m src.runner all               Run all stages (current behavior)
  python -m src.runner resume            Resume from first failed/not-run stage
  python -m src.runner retry stage2      Re-run a specific stage
  python -m src.runner --list            List all stages
  python -m src.runner --status          Show stage status table
  python -m src.runner --status --json   Machine-readable status
  python -m src.runner schedule ...      Schedule management subcommands
  python -m src.runner locks ...         Lock management subcommands

Flags:
  --run-id <id>          Attach to an existing run ID
  --dry-run              Validate inputs/config without executing
  --force                Skip dependency checks
  --auto-run-deps        Auto-run missing prerequisite stages
  --input-file <path>    Override automatic staging input lookup
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Ensure project root is importable.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.config.settings import settings
from src.utils.logger import get_logger
from src.scheduler.registry import STAGES, topological_order, get_all_prerequisites
from src.scheduler import staging, status as status_mod, locking
from src.scheduler.logging_config import setup_stage_logging, teardown_stage_logging
from src.scheduler.retry import run_with_retry
from src.scheduler.notifications import send_stage_notification

log = get_logger(__name__)

_MAX_AGE_HOURS = float(os.getenv("STAGING_MAX_AGE_HOURS", "168"))


# ── Context helpers ───────────────────────────────────────────────────────────

def _build_context(
    run_id: str,
    dry_run: bool = False,
    force: bool = False,
    input_file: Optional[str] = None,
) -> dict:
    return {
        "run_id": run_id,
        "output_dir": settings.OUTPUT_DIR,
        "staging_dir": staging.staging_dir(run_id, settings.OUTPUT_DIR),
        "config_dir": settings.CONFIG_DIR,
        "data_dir": settings.DATA_DIR,
        "dry_run": dry_run,
        "force": force,
        "input_file": input_file,
        "clients": {},
        # In-memory passthrough for `all` mode (avoids disk round-trip).
        "_stage1_data": None,
        "_stage2_data": None,
    }


def _init_clients(ctx: dict) -> None:
    from src.main import _get_clients
    ap, cl, hs, zb, nb, va = _get_clients()
    ctx["clients"] = {
        "apollo": ap, "clay": cl, "hubspot": hs,
        "zerobounce": zb, "neverbounce": nb, "validity": va,
    }


def _load_scheduler_cfg() -> dict:
    from src.scheduler.config import load_scheduler_config
    return load_scheduler_config(settings.CONFIG_DIR)


# ── Dependency validation ─────────────────────────────────────────────────────

def _validate_dependencies(stage_name: str, ctx: dict, force: bool = False) -> None:
    if force or ctx.get("force", False):
        return
    run_id = ctx["run_id"]
    output_dir = ctx["output_dir"]
    max_age = _MAX_AGE_HOURS

    defn = STAGES[stage_name]
    for dep in defn["dependencies"]:
        dep_defn = STAGES[dep]
        if not dep_defn.get("output_file"):
            continue
        if not staging.stage_output_exists(dep, run_id, output_dir):
            raise RuntimeError(
                f"Stage {stage_name} requires {dep} output. "
                f"Run: python -m src.runner {dep} --run-id {run_id}\n"
                f"     or: python -m src.runner all"
            )
        age = staging.get_stage_output_age_hours(dep, run_id, output_dir)
        if age is not None and age > max_age:
            raise RuntimeError(
                f"Stage {dep} output is {age:.1f}h old (max {max_age}h). "
                f"Re-run: python -m src.runner {dep} --run-id {run_id}"
            )


def _ensure_deps(stage_name: str, ctx: dict, scheduler_cfg: dict) -> None:
    """Auto-run any missing prerequisite stages."""
    for dep in get_all_prerequisites(stage_name):
        dep_defn = STAGES[dep]
        if not dep_defn.get("output_file"):
            continue
        if not staging.stage_output_exists(dep, ctx["run_id"], ctx["output_dir"]):
            log.info("Auto-running prerequisite: %s", dep)
            _execute_stage(dep, ctx, scheduler_cfg)


# ── Stage execution wrappers ──────────────────────────────────────────────────

def _exec_stage0(ctx: dict) -> dict:
    from src.main import _run_stage_zero
    entries: list = []
    _run_stage_zero(entries)
    count = entries[0]["record_count"] if entries else 0
    return {"stage_entries": entries, "record_count": count}


def _exec_stage1(ctx: dict) -> List[dict]:
    from src.main import run_company_pipeline
    if ctx["dry_run"]:
        log.info("[dry-run] stage1: would run company pipeline")
        return []
    result = run_company_pipeline(ctx["clients"]["apollo"], ctx["clients"]["clay"])
    staging.write_stage_output("stage1", result, ctx["run_id"], ctx["output_dir"])
    ctx["_stage1_data"] = result
    return result


def _exec_stage2(ctx: dict) -> List[dict]:
    from src.main import run_contact_pipeline
    if ctx["dry_run"]:
        log.info("[dry-run] stage2: would run contact pipeline")
        return []
    # Prefer in-memory passthrough, else read from staging.
    enriched: List[dict] = ctx.get("_stage1_data") or staging.read_stage_output(
        "stage1", ctx["run_id"], ctx["output_dir"]
    )
    if ctx.get("input_file"):
        with open(ctx["input_file"], encoding="utf-8") as f:
            payload = json.load(f)
        enriched = payload.get("data", payload) if isinstance(payload, dict) else payload

    result = run_contact_pipeline(
        enriched,
        ctx["clients"]["apollo"],
        ctx["clients"]["zerobounce"],
        ctx["clients"]["neverbounce"],
    )
    staging.write_stage_output("stage2", result, ctx["run_id"], ctx["output_dir"])
    ctx["_stage2_data"] = result
    return result


def _exec_stage3(ctx: dict) -> dict:
    from src.main import run_activation_pipeline
    if ctx["dry_run"]:
        log.info("[dry-run] stage3: would run activation pipeline")
        return {}
    enriched: List[dict] = ctx.get("_stage1_data") or staging.read_stage_output(
        "stage1", ctx["run_id"], ctx["output_dir"]
    )
    validated: List[dict] = ctx.get("_stage2_data") or staging.read_stage_output(
        "stage2", ctx["run_id"], ctx["output_dir"]
    )
    run_activation_pipeline(validated, enriched, ctx["clients"]["hubspot"])
    approved_count = sum(1 for c in validated if c.get("final_validation_status") == "approved")
    result = {"companies": len(enriched), "approved_contacts": approved_count}
    staging.write_stage_output("stage3", [result], ctx["run_id"], ctx["output_dir"])
    return result


def _exec_stage4(ctx: dict) -> List[dict]:
    from src.main import run_campaign_monitoring
    if ctx["dry_run"]:
        log.info("[dry-run] stage4: would run campaign monitoring")
        return []
    run_campaign_monitoring(ctx["clients"]["validity"])
    # Read the health report back from CSV for staging persistence.
    import csv
    report_path = os.path.join(ctx["output_dir"], "11_campaign_health_report.csv")
    result = []
    if os.path.exists(report_path):
        with open(report_path, encoding="utf-8", newline="") as f:
            result = list(csv.DictReader(f))
    staging.write_stage_output("stage4", result, ctx["run_id"], ctx["output_dir"])
    return result


_STAGE_FNS = {
    "stage0": _exec_stage0,
    "stage1": _exec_stage1,
    "stage2": _exec_stage2,
    "stage3": _exec_stage3,
    "stage4": _exec_stage4,
}

_STAGE_CLIENTS = {
    "stage0": [],
    "stage1": ["apollo", "clay"],
    "stage2": ["apollo", "zerobounce", "neverbounce"],
    "stage3": ["hubspot"],
    "stage4": ["validity"],
}


# ── Single stage executor ─────────────────────────────────────────────────────

def _execute_stage(stage_name: str, ctx: dict, scheduler_cfg: dict) -> int:
    """
    Execute one stage with locking, status tracking, retry, and notifications.
    Returns record count (0 on failure).
    """
    output_dir = ctx["output_dir"]
    run_id = ctx["run_id"]
    force = ctx.get("force", False)

    # Acquire lock.
    acquired = locking.acquire_lock(stage_name, run_id, output_dir)
    if not acquired:
        info = locking.is_locked(stage_name, output_dir)
        pid = info.get("pid", "?") if info else "?"
        log.warning(
            "Stage %s is already running (PID %s). Skipping.", stage_name, pid
        )
        return 0

    # Validate dependencies.
    try:
        _validate_dependencies(stage_name, ctx, force)
    except RuntimeError as exc:
        log.error("%s", exc)
        locking.release_lock(stage_name, output_dir)
        return 0

    # Per-stage log file.
    log_level = scheduler_cfg.get(stage_name, {}).get("log_level", "INFO")
    file_handler = setup_stage_logging(stage_name, run_id, output_dir, log_level)

    status_mod.mark_running(stage_name, run_id, output_dir)
    t0 = time.monotonic()
    record_count = 0

    try:
        fn = _STAGE_FNS[stage_name]
        result = run_with_retry(fn, ctx, stage_name, scheduler_cfg)
        # Determine record count from result type.
        if isinstance(result, list):
            record_count = len(result)
        elif isinstance(result, dict):
            record_count = result.get("record_count", result.get("companies", 0))

        duration = time.monotonic() - t0
        status_mod.mark_completed(stage_name, run_id, record_count, duration, output_dir)
        log.info("Stage %s completed — %d records in %.1fs", stage_name, record_count, duration)
        send_stage_notification(
            stage_name, "completed", record_count, duration,
            scheduler_cfg=scheduler_cfg,
        )
    except Exception as exc:
        duration = time.monotonic() - t0
        status_mod.mark_failed(stage_name, run_id, str(exc), duration, output_dir)
        log.error("Stage %s failed after %.1fs: %s", stage_name, duration, exc)
        send_stage_notification(
            stage_name, "failed", 0, duration,
            error=str(exc), scheduler_cfg=scheduler_cfg,
        )
        teardown_stage_logging(file_handler)
        locking.release_lock(stage_name, output_dir)
        raise
    finally:
        teardown_stage_logging(file_handler)
        locking.release_lock(stage_name, output_dir)

    return record_count


# ── Multi-stage orchestration ─────────────────────────────────────────────────

def run_stages(
    stage_names: List[str],
    run_id: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
    auto_run_deps: bool = False,
    input_file: Optional[str] = None,
    write_manifest: bool = False,
) -> int:
    """Run the given stages in dependency order. Returns exit code."""
    run_id = run_id or str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ctx = _build_context(run_id, dry_run, force, input_file)
    _init_clients(ctx)
    scheduler_cfg = _load_scheduler_cfg()

    ordered = topological_order(stage_names)
    log.info(
        "Run ID: %s  Stages: %s", run_id[:8], " → ".join(ordered)
    )

    stage_entries = []
    for stage_name in ordered:
        # Circuit breakers — skip downstream stages when upstream has no actionable data.
        skip_reason = _check_circuit_breaker(stage_name, ctx, ordered)
        if skip_reason:
            log.warning("Circuit breaker: %s — skipping %s", skip_reason, stage_name)
            stage_entries.append({"name": stage_name, "record_count": 0, "status": "skipped"})
            continue

        if auto_run_deps:
            _ensure_deps(stage_name, ctx, scheduler_cfg)
        try:
            count = _execute_stage(stage_name, ctx, scheduler_cfg)
            stage_entries.append({"name": stage_name, "record_count": count, "status": "completed"})
        except Exception:
            log.error("Pipeline stopped at %s.", stage_name)
            stage_entries.append({"name": stage_name, "record_count": 0, "status": "failed"})
            if write_manifest:
                _write_run_manifest(run_id, started_at, stage_entries)
            return 1

    if write_manifest:
        _write_run_manifest(run_id, started_at, stage_entries)
        if settings.STORAGE_ENABLED:
            _persist_to_storage_from_ctx(run_id, started_at, stage_entries, ctx)

    staging.cleanup_old_staging_dirs(settings.OUTPUT_DIR)
    return 0


def _check_circuit_breaker(stage_name: str, ctx: dict, ordered: List[str]) -> Optional[str]:
    """Return a skip reason if stage_name should be skipped, else None."""
    # stage2 requires at least one approved company from stage1.
    if stage_name == "stage2" and "stage1" in ordered:
        data = ctx.get("_stage1_data") or []
        if data and not any(c.get("contact_discovery_approved") for c in data):
            return "no approved companies after stage1"
    # stage3 requires at least one approved contact from stage2.
    if stage_name == "stage3" and "stage2" in ordered:
        data = ctx.get("_stage2_data") or []
        if data and not any(c.get("final_validation_status") == "approved" for c in data):
            return "no approved contacts after stage2"
    return None


_STAGE_MANIFEST_NAMES = {
    "stage0": "icp_intelligence",
    "stage1": "company_pipeline",
    "stage2": "contact_pipeline",
    "stage3": "activation_pipeline",
    "stage4": "campaign_monitoring",
}


def _write_run_manifest(run_id: str, started_at: str, stage_entries: list) -> None:
    from src.main import _config_hash
    # Use legacy stage names for backward compatibility with downstream consumers.
    manifest_stages = [
        {
            "name": _STAGE_MANIFEST_NAMES.get(e["name"], e["name"]),
            "record_count": e["record_count"],
            "status": e["status"],
        }
        for e in stage_entries
    ]
    manifest = {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mock_mode": settings.MOCK_MODE,
        "stages": manifest_stages,
        "config_hash": _config_hash(),
    }
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(settings.OUTPUT_DIR, "run_manifest.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    os.replace(tmp, path)
    log.info("Run manifest written: %s", path)


def _persist_to_storage_from_ctx(
    run_id: str, started_at: str, stage_entries: list, ctx: dict
) -> None:
    from src.storage.sqlite_backend import SQLiteBackend
    try:
        db = SQLiteBackend(settings.STORAGE_DB_PATH)
        enriched = ctx.get("_stage1_data") or []
        validated = ctx.get("_stage2_data") or []
        db.save_pipeline_run({
            "run_id": run_id,
            "started_at": started_at,
            "status": "completed",
            "company_count": len(enriched),
            "contact_count": len(validated),
        })
        if enriched:
            db.save_companies(enriched, run_id)
        if validated:
            db.save_contacts(validated, run_id)
        log.info("Run %s persisted to SQLite", run_id)
    except Exception as exc:
        log.warning("Storage persistence failed: %s", exc)


def run_all(
    run_id: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
) -> int:
    """Run all pipeline stages in order. Mirrors original main() behavior."""
    all_stages = [s for s in STAGES if not STAGES[s].get("optional")]
    # Include stage0 when ICP Intelligence is enabled (mirrors old main() behavior).
    if settings.ICP_INTELLIGENCE_ENABLED and "stage0" not in all_stages:
        all_stages = ["stage0"] + all_stages
    return run_stages(
        all_stages, run_id=run_id, dry_run=dry_run, force=force,
        write_manifest=True,
    )


def resume(
    run_id: Optional[str] = None,
    specific_run_id: Optional[str] = None,
) -> int:
    """Find first failed/not-run stage and run from there."""
    output_dir = settings.OUTPUT_DIR
    current_status = status_mod.load_status(output_dir)

    stage_order = [s for s in STAGES if not STAGES[s].get("optional")]
    start_from = None
    for s in stage_order:
        st = current_status.get(s, {}).get("status", "not_run")
        if st in ("failed", "not_run"):
            start_from = s
            break

    if start_from is None:
        log.info("All stages have completed. Nothing to resume.")
        return 0

    log.info("Resuming from: %s", start_from)
    idx = stage_order.index(start_from)
    stages_to_run = stage_order[idx:]

    # Use the run_id from the last completed stage, or a new one.
    if specific_run_id:
        effective_run_id = specific_run_id
    else:
        for s in reversed(stage_order[:idx]):
            last = current_status.get(s, {}).get("last_run_id", "")
            if last:
                effective_run_id = last
                break
        else:
            effective_run_id = str(uuid.uuid4())

    log.info("Using run_id: %s", effective_run_id[:8])
    return run_stages(stages_to_run, run_id=effective_run_id, force=True)


# ── CLI ───────────────────────────────────────────────────────────────────────

def _print_list() -> None:
    current_status = status_mod.load_status(settings.OUTPUT_DIR)
    print(f"\n  {'Stage':<22} {'Description':<45} {'Last status'}")
    print("  " + "─" * 80)
    for stage_name, defn in STAGES.items():
        s = current_status.get(stage_name, {})
        st = s.get("status", "not_run")
        last_at = s.get("last_run_at", "—")
        if last_at and last_at != "—":
            last_at = last_at.replace("T", " ").replace("Z", "")[:16]
        desc = defn["description"][:45]
        label = f"{stage_name} ({defn['display_name'][:12]})"
        print(f"  {label:<22} {desc:<45} {st} {last_at}")
    print()


def _validate_stage_args(names: List[str]) -> bool:
    for n in names:
        if n not in STAGES:
            print(f"Unknown stage: '{n}'. Valid: {list(STAGES)}")
            return False
    return True


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m src.runner",
        description="GTM Pipeline Runner",
        add_help=True,
    )
    parser.add_argument(
        "stages", nargs="*",
        help="Stage(s) to run: stage0 stage1 stage2 stage3 stage4 all resume retry schedule locks",
    )
    parser.add_argument("--run-id", default=None, help="Attach to an existing run ID")
    parser.add_argument("--dry-run", action="store_true", help="Validate without executing")
    parser.add_argument("--force", action="store_true", help="Skip dependency checks")
    parser.add_argument("--auto-run-deps", action="store_true", help="Auto-run missing deps")
    parser.add_argument("--input-file", default=None, help="Override staging input lookup")
    parser.add_argument("--list", action="store_true", help="List all stages and last status")
    parser.add_argument("--status", action="store_true", help="Show stage status table")
    parser.add_argument("--json", action="store_true", help="Machine-readable output (with --status)")

    args, remainder = parser.parse_known_args(argv)

    # ── Meta commands ─────────────────────────────────────────────────────────

    if args.list:
        _print_list()
        return 0

    if args.status:
        current_status = status_mod.load_status(settings.OUTPUT_DIR)
        if args.json:
            print(json.dumps(current_status, indent=2))
        else:
            status_mod.print_status_table(current_status)
        return 0

    stage_args = args.stages

    if not stage_args:
        parser.print_help()
        return 0

    first = stage_args[0]

    # ── schedule subcommands ──────────────────────────────────────────────────

    if first == "schedule":
        from src.scheduler.cli import handle_schedule_command
        return handle_schedule_command(stage_args[1:] + remainder)

    # ── locks subcommands ─────────────────────────────────────────────────────

    if first == "locks":
        sub = stage_args[1] if len(stage_args) > 1 else "--show"
        output_dir = settings.OUTPUT_DIR
        if sub == "--show":
            locking.show_locks(output_dir)
        elif sub == "--clear" and len(stage_args) > 2:
            confirm = input(f"Clear lock for {stage_args[2]}? [y/N] ")
            if confirm.lower() == "y":
                locking.clear_lock(stage_args[2], output_dir)
                print(f"Lock cleared for {stage_args[2]}.")
        elif sub == "--clear-all":
            confirm = input("Clear ALL locks? [y/N] ")
            if confirm.lower() == "y":
                locking.clear_all_locks(output_dir)
                print("All locks cleared.")
        else:
            print("Usage: locks [--show | --clear <stage> | --clear-all]")
        return 0

    # ── resume ────────────────────────────────────────────────────────────────

    if first == "resume":
        return resume(specific_run_id=args.run_id)

    # ── retry <stage> ─────────────────────────────────────────────────────────

    if first == "retry":
        if len(stage_args) < 2:
            print("Usage: retry <stage>"); return 1
        target = stage_args[1]
        if not _validate_stage_args([target]):
            return 1
        return run_stages(
            [target],
            run_id=args.run_id,
            dry_run=args.dry_run,
            force=True,
        )

    # ── all ───────────────────────────────────────────────────────────────────

    if first == "all":
        return run_all(run_id=args.run_id, dry_run=args.dry_run, force=args.force)

    # ── named stages ─────────────────────────────────────────────────────────

    if not _validate_stage_args(stage_args):
        return 1

    return run_stages(
        stage_args,
        run_id=args.run_id,
        dry_run=args.dry_run,
        force=args.force,
        auto_run_deps=args.auto_run_deps,
        input_file=args.input_file,
    )


if __name__ == "__main__":
    sys.exit(main())
