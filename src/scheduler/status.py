"""
Stage status tracker — reads and writes outputs/stage_status.json.

Updated atomically at start (running) and end (completed/failed) of each stage.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

_STATUS_FILE = "stage_status.json"

_STATUS_COLORS = {
    "completed": "\033[32m",   # green
    "failed":    "\033[31m",   # red
    "running":   "\033[33m",   # yellow
    "not_run":   "\033[90m",   # gray
}
_RESET = "\033[0m"


def _status_path(output_dir: str) -> str:
    return os.path.join(output_dir, _STATUS_FILE)


def load_status(output_dir: str) -> dict:
    path = _status_path(output_dir)
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_status(status: dict, output_dir: str) -> None:
    os.makedirs(output_dir, exist_ok=True)
    path = _status_path(output_dir)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)
    os.replace(tmp, path)


def update_stage_status(stage_name: str, update: dict, output_dir: str) -> None:
    status = load_status(output_dir)
    existing = status.get(stage_name, {})
    existing.update(update)
    status[stage_name] = existing
    save_status(status, output_dir)


def mark_running(stage_name: str, run_id: str, output_dir: str) -> None:
    update_stage_status(stage_name, {
        "last_run_id": run_id,
        "last_run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "running",
        "record_count": 0,
        "duration_seconds": None,
        "error": None,
    }, output_dir)


def mark_completed(
    stage_name: str,
    run_id: str,
    record_count: int,
    duration_seconds: float,
    output_dir: str,
) -> None:
    update_stage_status(stage_name, {
        "last_run_id": run_id,
        "last_run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "completed",
        "record_count": record_count,
        "duration_seconds": round(duration_seconds, 1),
        "error": None,
    }, output_dir)


def mark_failed(
    stage_name: str,
    run_id: str,
    error_msg: str,
    duration_seconds: float,
    output_dir: str,
    attempt: int = 1,
) -> None:
    status = load_status(output_dir)
    existing = status.get(stage_name, {})
    retries = existing.get("retry_attempts", [])
    retries.append({
        "attempt": attempt,
        "failed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "error": error_msg,
    })
    existing.update({
        "last_run_id": run_id,
        "last_run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "failed",
        "record_count": 0,
        "duration_seconds": round(duration_seconds, 1),
        "error": error_msg,
        "retry_attempts": retries[-10:],  # keep last 10
    })
    status[stage_name] = existing
    save_status(status, output_dir)


def print_status_table(status: dict, use_color: bool = True) -> None:
    from src.scheduler.registry import STAGES
    header = f"{'Stage':<22} {'Status':<12} {'Last run':<22} {'Records':>8}  {'Duration':>9}"
    divider = "─" * 78
    print(f"\n{divider}")
    print(header)
    print(divider)
    for stage_name, info in STAGES.items():
        s = status.get(stage_name, {})
        st = s.get("status", "not_run")
        color = _STATUS_COLORS.get(st, "") if use_color else ""
        reset = _RESET if use_color else ""
        run_at = s.get("last_run_at", "—")
        if run_at and run_at != "—":
            run_at = run_at.replace("T", " ").replace("Z", "")[:16]
        rec = str(s.get("record_count", "—")) if st != "not_run" else "—"
        dur = f"{s.get('duration_seconds', '—')}s" if s.get("duration_seconds") else "—"
        label = f"{stage_name} ({info['display_name'][:12]})"
        print(f"  {label:<22} {color}{st:<12}{reset} {run_at:<22} {rec:>8}  {dur:>9}")
        if st == "failed" and s.get("error"):
            print(f"    {'':>22}  Error: {s['error'][:70]}")
    print(f"{divider}\n")
