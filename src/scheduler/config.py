"""
Schedule configuration loader — reads config/scheduler.json, validates cron
expressions, computes next run times, and manages presets.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Optional

_CONFIG_FILE = "scheduler.json"

PRESETS = {
    "conservative": {
        "stage1": {"cron": "0 7 * * 1",   "description": "Prospect sourcing — weekly Mondays 7am"},
        "stage2": {"cron": "0 8 * * 1",   "description": "Contact validation — weekly Mondays 8am"},
        "stage3": {"cron": "0 9 * * 1",   "description": "CRM sync — weekly Mondays 9am"},
        "stage4": {"cron": "0 8 * * *",   "description": "Monitoring — daily 8am"},
    },
    "aggressive": {
        "stage1": {"cron": "0 7 * * *",   "description": "Prospect sourcing — daily 7am"},
        "stage2": {"cron": "0 8 * * *",   "description": "Contact validation — daily 8am"},
        "stage3": {"cron": "0 6,18 * * *","description": "CRM sync — twice daily 6am/6pm"},
        "stage4": {"cron": "0 * * * *",   "description": "Monitoring — hourly"},
    },
    "startup": {
        "stage1": {"cron": "0 7 * * *",   "description": "Prospect sourcing — daily 7am"},
        "stage2": {"cron": "0 8 * * *",   "description": "Contact validation — daily 8am"},
        "stage3": {"cron": "0 9 * * *",   "description": "CRM sync — daily 9am"},
        "stage4": {"cron": "0 */4 * * *", "description": "Monitoring — every 4 hours"},
    },
}


def load_scheduler_config(config_dir: str) -> dict:
    path = os.path.join(config_dir, _CONFIG_FILE)
    if not os.path.exists(path):
        return {"schedules": {}, "defaults": {}}
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    _validate_config(cfg)
    return cfg


def save_scheduler_config(cfg: dict, config_dir: str) -> None:
    path = os.path.join(config_dir, _CONFIG_FILE)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
    os.replace(tmp, path)


def _validate_config(cfg: dict) -> None:
    for stage_name, s in cfg.get("schedules", {}).items():
        cron = s.get("cron", "")
        if cron and not validate_cron_expression(cron):
            raise ValueError(f"Invalid cron expression for {stage_name}: '{cron}'")


def validate_cron_expression(cron_str: str) -> bool:
    try:
        from croniter import croniter
        return croniter.is_valid(cron_str)
    except ImportError:
        # croniter not installed — basic field count check.
        parts = cron_str.strip().split()
        return len(parts) == 5


def get_next_run_time(cron_str: str, tz_name: str = "America/New_York") -> Optional[datetime]:
    try:
        from croniter import croniter
        import pytz
        tz = pytz.timezone(tz_name)
        base = datetime.now(tz)
        return croniter(cron_str, base).get_next(datetime)
    except Exception:
        return None


def apply_preset(preset_name: str, cfg: dict) -> dict:
    if preset_name not in PRESETS:
        raise ValueError(f"Unknown preset '{preset_name}'. Valid: {list(PRESETS)}")
    schedules = cfg.setdefault("schedules", {})
    for stage_name, overrides in PRESETS[preset_name].items():
        if stage_name not in schedules:
            schedules[stage_name] = {}
        schedules[stage_name].update(overrides)
        schedules[stage_name]["enabled"] = True
    return cfg


def print_schedule_table(cfg: dict) -> None:
    from src.scheduler.registry import STAGES
    schedules = cfg.get("schedules", {})
    tz = cfg.get("defaults", {}).get("timezone", "America/New_York")

    header = f"  {'Stage':<22} {'Schedule':<35} {'Next run'}"
    divider = "─" * 80
    print(f"\n{divider}")
    print(header)
    print(divider)
    for stage_name, info in STAGES.items():
        s = schedules.get(stage_name, {})
        enabled = s.get("enabled", False)
        cron = s.get("cron", "")
        desc = s.get("description", cron)
        if not enabled or not cron:
            schedule_str = "disabled"
            next_str = "—"
        else:
            schedule_str = desc[:35] if len(desc) <= 35 else cron
            nxt = get_next_run_time(cron, tz)
            next_str = nxt.strftime("%Y-%m-%d %H:%M %Z") if nxt else "—"
        label = f"{stage_name} ({info['display_name'][:12]})"
        print(f"  {label:<22} {schedule_str:<35} {next_str}")
    print(f"{divider}\n")
