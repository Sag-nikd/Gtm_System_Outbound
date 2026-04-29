#!/usr/bin/env python3
"""
GTM System setup wizard — interactive CLI that configures a new deployment.

Usage:
  python setup.py
  python setup.py --vertical saas --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

# Ensure repo root is on the path when run directly
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_CONFIG_DIR = os.path.join(_ROOT, "config")
_TEMPLATES_DIR = os.path.join(_CONFIG_DIR, "templates")
_ENV_FILE = os.path.join(_ROOT, ".env")

_VERTICALS = {
    "1": ("saas", "SaaS / B2B Technology"),
    "2": ("ecommerce", "E-commerce / Retail"),
    "3": ("financial_services", "Financial Services / Fintech"),
    "4": ("logistics", "Logistics & Supply Chain"),
    "5": ("manufacturing", "Manufacturing / Industrial"),
}

_INTEGRATIONS = [
    ("APOLLO_API_KEY", "Apollo (prospect data)", True),
    ("CLAY_API_KEY", "Clay (enrichment)", True),
    ("HUBSPOT_PRIVATE_APP_TOKEN", "HubSpot private app token", True),
    ("ZEROBOUNCE_API_KEY", "ZeroBounce (email validation)", True),
    ("NEVERBOUNCE_API_KEY", "NeverBounce (email validation)", True),
    ("VALIDITY_API_KEY", "Validity / Everest (campaign monitoring)", False),
    ("SLACK_WEBHOOK_URL", "Slack webhook URL (notifications)", False),
]

_SCHEDULE_PRESETS = {
    "1": ("conservative", "Weekly (recommended for new deployments)"),
    "2": ("aggressive", "Daily — high-volume prospecting"),
    "3": ("startup", "Daily with hourly monitoring — high cadence"),
}


def _print_header() -> None:
    print("\n" + "=" * 60)
    print("  GTM System — Setup Wizard")
    print("=" * 60)
    print("  This wizard will configure your GTM pipeline.\n")


def _prompt(question: str, default: str = "", secret: bool = False) -> str:
    if default:
        prompt_text = f"  {question} [{default}]: "
    else:
        prompt_text = f"  {question}: "
    try:
        if secret:
            import getpass
            value = getpass.getpass(prompt_text)
        else:
            value = input(prompt_text).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n\nSetup cancelled.")
        sys.exit(0)
    return value if value else default


def _choose(question: str, options: dict, default: str = "1") -> tuple[str, str]:
    print(f"\n  {question}")
    for key, (_, label) in options.items():
        print(f"    {key}) {label}")
    choice = _prompt("Choose", default=default)
    return options.get(choice, options[default])


def _step_vertical(dry_run: bool) -> str:
    print("\n── Step 1: Industry vertical ─────────────────────────────")
    slug, label = _choose("Which industry best describes your target market?", _VERTICALS)
    print(f"  → Selected: {label}")
    return slug


def _step_apply_template(vertical: str, dry_run: bool) -> None:
    print("\n── Step 2: Applying vertical template ───────────────────")
    template_dir = os.path.join(_TEMPLATES_DIR, vertical)
    if not os.path.isdir(template_dir):
        print(f"  ⚠  Template not found for '{vertical}'. Skipping.")
        return

    files_copied = []
    for filename in os.listdir(template_dir):
        src = os.path.join(template_dir, filename)
        dst = os.path.join(_CONFIG_DIR, filename)
        if dry_run:
            print(f"  [dry-run] Would copy {filename} → config/{filename}")
        else:
            shutil.copy2(src, dst)
            files_copied.append(filename)

    if files_copied:
        print(f"  ✓ Applied {len(files_copied)} config files: {', '.join(files_copied)}")


def _step_icp_tuning(dry_run: bool) -> dict:
    print("\n── Step 3: ICP tuning ────────────────────────────────────")
    print("  We'll load the ICP rules from your selected template.\n")

    rules_path = os.path.join(_CONFIG_DIR, "icp_rules.json")
    if not os.path.exists(rules_path):
        print("  ⚠  icp_rules.json not found — skipping tuning.")
        return {}

    with open(rules_path, encoding="utf-8") as f:
        rules = json.load(f)

    industries = rules.get("industry_scores", {})
    print("  Current industry scores (top-scoring):")
    top = sorted(
        [(k, v) for k, v in industries.items() if k != "default"],
        key=lambda x: -x[1],
    )[:5]
    for name, score in top:
        print(f"    {name}: {score}")

    customise = _prompt("\n  Customise industry scores? (y/N)", default="n")
    if customise.lower() == "y" and not dry_run:
        for name, score in list(industries.items()):
            if name == "default":
                continue
            new_score = _prompt(f"    Score for '{name}' (0.0–1.0)", default=str(score))
            try:
                rules["industry_scores"][name] = float(new_score)
            except ValueError:
                pass
        with open(rules_path, "w", encoding="utf-8") as f:
            json.dump(rules, f, indent=2)
        print("  ✓ ICP rules saved")

    return rules


def _step_api_keys(dry_run: bool) -> dict:
    print("\n── Step 4: API keys & credentials ───────────────────────")
    print("  Keys are written to .env (never committed to git).\n")

    existing_env = _load_env()
    new_values: dict = {}

    for env_var, label, required in _INTEGRATIONS:
        current = existing_env.get(env_var, "")
        display = f"{label}{'' if required else ' (optional)'}"
        if current:
            change = _prompt(f"  {display} — already set. Change? (y/N)", default="n")
            if change.lower() != "y":
                new_values[env_var] = current
                continue
        value = _prompt(f"  {display}", secret=True)
        if value:
            new_values[env_var] = value
        elif required:
            print(f"  ⚠  {env_var} is required for live mode. Set MOCK_MODE=true to skip.")
        else:
            new_values[env_var] = ""

    if not dry_run:
        _write_env(new_values, existing_env)
        print("\n  ✓ Credentials saved to .env")

    return new_values


def _step_schedule(dry_run: bool) -> str:
    print("\n── Step 5: Pipeline schedule ─────────────────────────────")
    preset_slug, preset_label = _choose(
        "Select a scheduling preset:", _SCHEDULE_PRESETS
    )
    print(f"  → Selected: {preset_label}")

    sched_path = os.path.join(_CONFIG_DIR, "scheduler.json")
    if not dry_run and os.path.exists(sched_path):
        with open(sched_path, encoding="utf-8") as f:
            sched = json.load(f)

        try:
            from src.scheduler.config import apply_preset
            sched = apply_preset(preset_slug, sched)
            with open(sched_path, "w", encoding="utf-8") as f:
                json.dump(sched, f, indent=2)
            print("  ✓ Schedule saved")
        except ImportError:
            print("  ⚠  Could not apply preset (src.scheduler.config not found)")

    return preset_slug


def _step_mock_mode(dry_run: bool) -> None:
    print("\n── Step 6: Operating mode ────────────────────────────────")
    mode = _prompt(
        "  Run in mock mode (no real API calls)? (Y/n)",
        default="y",
    )
    mock = mode.lower() != "n"
    if not dry_run:
        existing = _load_env()
        existing["MOCK_MODE"] = "true" if mock else "false"
        _write_env(existing, {})
    print(f"  → MOCK_MODE={'true' if mock else 'false'}")


def _step_summary(vertical: str, preset: str, dry_run: bool) -> None:
    print("\n── Setup complete ────────────────────────────────────────")
    print(f"  Vertical   : {vertical}")
    print(f"  Preset     : {preset}")
    print(f"  Dry run    : {dry_run}")
    print("\n  Next steps:")
    print("    1.  Verify .env is populated with real API keys when ready")
    print("    2.  Run:  python -m src.runner all")
    print("    3.  Or:   docker compose up -d  (for scheduled deployment)")
    if dry_run:
        print("\n  (Dry-run mode — no files were modified)\n")
    else:
        print()


# ── Env helpers ───────────────────────────────────────────────────────────────

def _load_env() -> dict:
    env: dict = {}
    if not os.path.exists(_ENV_FILE):
        return env
    with open(_ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                env[key.strip()] = val.strip()
    return env


def _write_env(new_values: dict, base: dict) -> None:
    merged = {**base, **new_values}
    lines = []
    for key, val in merged.items():
        if val:
            lines.append(f"{key}={val}\n")
    with open(_ENV_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="GTM System Setup Wizard")
    parser.add_argument("--vertical", choices=[v for v, _ in _VERTICALS.values()], help="Skip vertical prompt")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing files")
    args = parser.parse_args()

    _print_header()

    if args.dry_run:
        print("  DRY-RUN MODE — no files will be modified\n")

    vertical = args.vertical or _step_vertical(args.dry_run)
    _step_apply_template(vertical, args.dry_run)
    _step_icp_tuning(args.dry_run)
    _step_api_keys(args.dry_run)
    preset = _step_schedule(args.dry_run)
    _step_mock_mode(args.dry_run)
    _step_summary(vertical, preset, args.dry_run)


if __name__ == "__main__":
    main()
