"""
File-based execution locking — prevents two instances of the same stage
from running simultaneously and enforces cross-stage conflict rules.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

from src.scheduler.registry import CONFLICT_PAIRS

_LOCK_TIMEOUT_MINUTES = int(os.getenv("LOCK_TIMEOUT_MINUTES", "60"))


def _locks_dir(output_dir: str) -> str:
    path = os.path.join(output_dir, ".locks")
    os.makedirs(path, exist_ok=True)
    return path


def _lock_path(stage_name: str, output_dir: str) -> str:
    return os.path.join(_locks_dir(output_dir), f"{stage_name}.lock")


def acquire_lock(stage_name: str, run_id: str, output_dir: str) -> bool:
    """
    Try to acquire the lock for stage_name.
    Returns True on success, False if already locked (non-stale).
    """
    existing = is_locked(stage_name, output_dir)
    if existing:
        started = existing.get("started_at", "")
        age_min = _age_minutes(started)
        if age_min < _LOCK_TIMEOUT_MINUTES:
            return False
        # Stale lock — take over with a warning.
        _warn_stale(stage_name, existing)

    # Check cross-stage conflict rules.
    conflict = check_conflicts(stage_name, output_dir)
    if conflict:
        raise RuntimeError(conflict)

    payload = {
        "pid": os.getpid(),
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stage": stage_name,
    }
    tmp = _lock_path(stage_name, output_dir) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.replace(tmp, _lock_path(stage_name, output_dir))
    return True


def release_lock(stage_name: str, output_dir: str) -> None:
    path = _lock_path(stage_name, output_dir)
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def is_locked(stage_name: str, output_dir: str) -> Optional[dict]:
    """Return the lock payload dict if locked, else None."""
    path = _lock_path(stage_name, output_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def check_conflicts(stage_name: str, output_dir: str) -> Optional[str]:
    """Return an error string if a conflicting stage is currently running, else None."""
    for a, b in CONFLICT_PAIRS:
        if stage_name == a and is_locked(b, output_dir):
            other = is_locked(b, output_dir)
            pid = other.get("pid", "?")
            return (
                f"Cannot run {a}: {b} is currently running (PID {pid}). "
                f"Stage {a} and {b} cannot run concurrently."
            )
    return None


def clear_lock(stage_name: str, output_dir: str) -> None:
    release_lock(stage_name, output_dir)


def clear_all_locks(output_dir: str) -> None:
    d = _locks_dir(output_dir)
    for entry in os.scandir(d):
        if entry.name.endswith(".lock"):
            os.remove(entry.path)


def show_locks(output_dir: str) -> None:
    from src.scheduler.registry import STAGES
    any_locked = False
    for stage_name in STAGES:
        info = is_locked(stage_name, output_dir)
        if info:
            any_locked = True
            age = _age_minutes(info.get("started_at", ""))
            print(
                f"  {stage_name}: PID {info.get('pid','?')}  "
                f"run={info.get('run_id','?')[:8]}  "
                f"started {age:.0f} min ago"
            )
    if not any_locked:
        print("  No active locks.")


def _age_minutes(ts: str) -> float:
    if not ts:
        return 999
    try:
        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - then
        return delta.total_seconds() / 60
    except ValueError:
        return 999


def _warn_stale(stage_name: str, lock_info: dict) -> None:
    from src.utils.logger import get_logger
    log = get_logger(__name__)
    log.warning(
        "Stale lock for %s (PID %s, started %s) — taking over.",
        stage_name, lock_info.get("pid"), lock_info.get("started_at"),
    )
