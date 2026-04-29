"""
Staging layer — persists inter-stage data to outputs/staging/{run_id}/ as JSON.

Each stage writes a metadata-wrapped file so the next stage can read it
independently, enabling standalone execution and crash recovery.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from typing import List, Optional

_RETENTION_DAYS = int(os.getenv("STAGING_RETENTION_DAYS", "7"))
_MAX_AGE_HOURS = int(os.getenv("STAGING_MAX_AGE_HOURS", "168"))


def _base_staging_dir(output_dir: str) -> str:
    return os.path.join(output_dir, "staging")


def staging_dir(run_id: str, output_dir: str) -> str:
    path = os.path.join(_base_staging_dir(output_dir), run_id)
    os.makedirs(path, exist_ok=True)
    return path


def get_stage_output_path(stage_name: str, run_id: str, output_dir: str) -> str:
    from src.scheduler.registry import get_stage
    filename = get_stage(stage_name).get("output_file") or f"{stage_name}_output.json"
    return os.path.join(staging_dir(run_id, output_dir), filename)


def write_stage_output(
    stage_name: str,
    data: list,
    run_id: str,
    output_dir: str,
) -> str:
    path = get_stage_output_path(stage_name, run_id, output_dir)
    payload = {
        "stage": stage_name,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "record_count": len(data),
        "data": data,
    }
    _atomic_write(path, payload)
    return path


def read_stage_output(stage_name: str, run_id: str, output_dir: str) -> List[dict]:
    path = get_stage_output_path(stage_name, run_id, output_dir)
    if not os.path.exists(path):
        from src.scheduler.registry import get_stage
        dep_key = get_stage(stage_name)["dependencies"][0] if get_stage(stage_name)["dependencies"] else stage_name
        raise FileNotFoundError(
            f"Stage {stage_name} requires {dep_key} output. "
            f"Run: python -m src.runner {dep_key} --run-id {run_id}  "
            f"or: python -m src.runner all"
        )
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    return payload.get("data", [])


def stage_output_exists(stage_name: str, run_id: str, output_dir: str) -> bool:
    path = get_stage_output_path(stage_name, run_id, output_dir)
    return os.path.exists(path)


def get_stage_output_age_hours(stage_name: str, run_id: str, output_dir: str) -> Optional[float]:
    path = get_stage_output_path(stage_name, run_id, output_dir)
    if not os.path.exists(path):
        return None
    mtime = os.path.getmtime(path)
    age_secs = datetime.now().timestamp() - mtime
    return age_secs / 3600


def cleanup_old_staging_dirs(output_dir: str) -> int:
    """Remove staging subdirs older than STAGING_RETENTION_DAYS. Returns count removed."""
    base = _base_staging_dir(output_dir)
    if not os.path.exists(base):
        return 0
    cutoff = datetime.now().timestamp() - _RETENTION_DAYS * 86400
    removed = 0
    for entry in os.scandir(base):
        if entry.is_dir() and entry.stat().st_mtime < cutoff:
            shutil.rmtree(entry.path, ignore_errors=True)
            removed += 1
    return removed


def _atomic_write(path: str, payload: dict) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    os.replace(tmp, path)
