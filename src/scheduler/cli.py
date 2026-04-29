"""
Schedule management CLI — invoked via `python -m src.runner schedule <subcommand>`.
Updates config/scheduler.json in place; signals the daemon to reload if running.
"""
from __future__ import annotations

import json
import os
from typing import List, Optional

from src.utils.logger import get_logger
from src.config.settings import settings
from src.scheduler.config import (
    load_scheduler_config,
    save_scheduler_config,
    validate_cron_expression,
    get_next_run_time,
    print_schedule_table,
    apply_preset,
    PRESETS,
)
from src.scheduler.registry import STAGES
from src.scheduler.status import load_status

log = get_logger(__name__)


def handle_schedule_command(args: List[str]) -> int:
    """
    Entry point from runner. args is everything after 'schedule'.
    Returns exit code.
    """
    if not args:
        print_schedule_table(load_scheduler_config(settings.CONFIG_DIR))
        return 0

    sub = args[0]
    rest = args[1:]

    cfg = load_scheduler_config(settings.CONFIG_DIR)

    if sub == "show":
        print_schedule_table(cfg)
        return 0

    elif sub == "enable":
        if not rest:
            print("Usage: schedule enable <stage>"); return 1
        return _enable(rest[0], cfg, enabled=True)

    elif sub == "disable":
        if not rest:
            print("Usage: schedule disable <stage>"); return 1
        return _enable(rest[0], cfg, enabled=False)

    elif sub == "set":
        if len(rest) < 2:
            print("Usage: schedule set <stage> '<cron>'"); return 1
        return _set_cron(rest[0], rest[1], cfg)

    elif sub == "preset":
        if not rest:
            print(f"Usage: schedule preset <name>  (options: {', '.join(PRESETS)})"); return 1
        return _apply_preset(rest[0], cfg)

    elif sub == "next":
        return _show_next(cfg)

    elif sub == "history":
        n = int(rest[0]) if rest else 10
        return _show_history(n)

    elif sub == "run":
        if not rest:
            print("Usage: schedule run <stage> --now"); return 1
        stage = rest[0]
        if "--now" not in rest:
            print("Add --now to immediately trigger a stage."); return 1
        return _run_now(stage)

    else:
        print(f"Unknown schedule subcommand '{sub}'. Options: show, enable, disable, set, preset, next, history, run")
        return 1


def _enable(stage_name: str, cfg: dict, enabled: bool) -> int:
    if stage_name not in STAGES:
        print(f"Unknown stage '{stage_name}'."); return 1
    schedules = cfg.setdefault("schedules", {})
    schedules.setdefault(stage_name, {})["enabled"] = enabled
    save_scheduler_config(cfg, settings.CONFIG_DIR)
    state = "enabled" if enabled else "disabled"
    print(f"Stage {stage_name} {state}.")
    _signal_daemon_reload()
    return 0


def _set_cron(stage_name: str, cron_expr: str, cfg: dict) -> int:
    if stage_name not in STAGES:
        print(f"Unknown stage '{stage_name}'."); return 1
    if not validate_cron_expression(cron_expr):
        print(f"Invalid cron expression: '{cron_expr}'"); return 1
    schedules = cfg.setdefault("schedules", {})
    schedules.setdefault(stage_name, {})["cron"] = cron_expr
    save_scheduler_config(cfg, settings.CONFIG_DIR)
    print(f"Stage {stage_name} cron set to: {cron_expr}")
    _signal_daemon_reload()
    return 0


def _apply_preset(preset_name: str, cfg: dict) -> int:
    try:
        cfg = apply_preset(preset_name, cfg)
    except ValueError as exc:
        print(str(exc)); return 1
    save_scheduler_config(cfg, settings.CONFIG_DIR)
    print(f"Preset '{preset_name}' applied.")
    print_schedule_table(cfg)
    _signal_daemon_reload()
    return 0


def _show_next(cfg: dict) -> int:
    schedules = cfg.get("schedules", {})
    tz = cfg.get("defaults", {}).get("timezone", "America/New_York")
    rows = []
    for stage_name in STAGES:
        s = schedules.get(stage_name, {})
        if not s.get("enabled"):
            continue
        cron = s.get("cron", "")
        nxt = get_next_run_time(cron, tz)
        if nxt:
            rows.append((nxt, stage_name, cron))
    rows.sort(key=lambda r: r[0])
    if not rows:
        print("No enabled schedules.")
        return 0
    print(f"\n  {'Stage':<12} {'Next run':<25} Cron")
    print("  " + "─" * 55)
    for nxt, stage, cron in rows:
        print(f"  {stage:<12} {nxt.strftime('%Y-%m-%d %H:%M %Z'):<25} {cron}")
    print()
    return 0


def _show_history(n: int) -> int:
    status = load_status(settings.OUTPUT_DIR)
    print(f"\n  Stage execution history (last {n} per stage)")
    print("  " + "─" * 70)
    for stage_name in STAGES:
        s = status.get(stage_name, {})
        if not s:
            continue
        attempts = s.get("retry_attempts", [])
        last_at = s.get("last_run_at", "—")
        last_status = s.get("status", "—")
        rec = s.get("record_count", "—")
        dur = s.get("duration_seconds", "—")
        print(f"  {stage_name}: {last_status}  {last_at}  {rec} records  {dur}s")
        for attempt in attempts[-n:]:
            print(f"    attempt {attempt.get('attempt')}: {attempt.get('error','')[:60]}")
    print()
    return 0


def _run_now(stage_name: str) -> int:
    if stage_name not in STAGES:
        print(f"Unknown stage '{stage_name}'."); return 1
    print(f"Triggering {stage_name} immediately...")
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "-m", "src.runner", stage_name],
        cwd=settings.BASE_DIR,
    )
    return result.returncode


def _signal_daemon_reload() -> None:
    """Send SIGHUP to daemon if running, so it reloads config."""
    pid_file = os.path.join(settings.OUTPUT_DIR, ".scheduler.pid")
    if not os.path.exists(pid_file):
        return
    try:
        with open(pid_file) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGHUP)
        log.debug("Sent SIGHUP to daemon PID %d", pid)
    except (OSError, ValueError):
        pass


try:
    import signal as signal  # noqa: F811
except ImportError:
    pass
