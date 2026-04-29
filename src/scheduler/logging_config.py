"""
Per-stage log file configuration.
Adds a FileHandler to each stage's logger writing to outputs/logs/.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime


def setup_stage_logging(stage_name: str, run_id: str, output_dir: str, level: str = "INFO") -> logging.Handler:
    """Attach a per-stage file handler. Returns the handler (caller should remove it when done)."""
    logs_dir = os.path.join(output_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    log_path = os.path.join(logs_dir, f"{stage_name}_{run_id[:8]}.log")
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setLevel(getattr(logging, level.upper(), logging.INFO))

    fmt = logging.Formatter(
        f"[{stage_name}] %(asctime)s %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)

    # Attach to root so all child loggers write to this file too.
    root = logging.getLogger()
    root.addHandler(handler)
    return handler


def teardown_stage_logging(handler: logging.Handler) -> None:
    logging.getLogger().removeHandler(handler)
    handler.close()


def rotate_old_logs(output_dir: str, keep_days: int = 30) -> int:
    """Remove log files older than keep_days. Returns count removed."""
    logs_dir = os.path.join(output_dir, "logs")
    if not os.path.exists(logs_dir):
        return 0
    cutoff = datetime.now().timestamp() - keep_days * 86400
    removed = 0
    for entry in os.scandir(logs_dir):
        if entry.is_file() and entry.name.endswith(".log"):
            if entry.stat().st_mtime < cutoff:
                os.remove(entry.path)
                removed += 1
    return removed
