"""
Pre-flight checks — validates environment, API keys, config files, and
output directory writability before the pipeline starts.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from typing import List, NamedTuple


class CheckResult(NamedTuple):
    name: str
    passed: bool
    message: str


def run_preflight(config_dir: str, output_dir: str, live_mode: bool = False) -> List[CheckResult]:
    """
    Run all pre-flight checks and return a list of CheckResult objects.
    Raises SystemExit if any critical check fails.
    """
    results: List[CheckResult] = []

    results.extend(_check_python_version())
    results.extend(_check_required_packages())
    results.extend(_check_config_files(config_dir))
    results.extend(_check_output_writable(output_dir))

    if live_mode:
        results.extend(_check_live_env_vars())

    return results


def print_preflight_report(results: List[CheckResult]) -> bool:
    """Print a formatted preflight report. Returns True if all checks passed."""
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed

    print("\n── Pre-flight checks ────────────────────────────────────────")
    for r in results:
        icon = "✓" if r.passed else "✗"
        print(f"  {icon}  {r.name:<35} {r.message}")
    print(f"\n  {passed}/{len(results)} checks passed", end="")
    if failed:
        print(f", {failed} failed")
    else:
        print(" — all clear")
    print("─" * 60, "\n")

    return failed == 0


def assert_preflight(config_dir: str, output_dir: str, live_mode: bool = False) -> None:
    """Run preflight and abort with a readable error if any check fails."""
    results = run_preflight(config_dir, output_dir, live_mode)
    ok = print_preflight_report(results)
    if not ok:
        sys.exit("Pre-flight failed. Fix the issues above and re-run.")


# ── Individual check groups ───────────────────────────────────────────────────

def _check_python_version() -> List[CheckResult]:
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 9)
    return [CheckResult(
        name="Python version ≥ 3.9",
        passed=ok,
        message=f"{major}.{minor} ({'ok' if ok else 'upgrade required'})",
    )]


def _check_required_packages() -> List[CheckResult]:
    required = ["pandas", "requests", "croniter", "pytz"]
    results = []
    for pkg in required:
        try:
            __import__(pkg)
            results.append(CheckResult(name=f"Package: {pkg}", passed=True, message="installed"))
        except ImportError:
            results.append(CheckResult(
                name=f"Package: {pkg}",
                passed=False,
                message=f"missing — run: pip install {pkg}",
            ))
    return results


def _check_config_files(config_dir: str) -> List[CheckResult]:
    required_files = [
        "icp_rules.json",
        "apollo_query_config.json",
        "scheduler.json",
    ]
    results = []
    for filename in required_files:
        path = os.path.join(config_dir, filename)
        if not os.path.exists(path):
            results.append(CheckResult(
                name=f"Config: {filename}",
                passed=False,
                message=f"missing at {path}",
            ))
            continue
        try:
            with open(path, encoding="utf-8") as f:
                json.load(f)
            results.append(CheckResult(name=f"Config: {filename}", passed=True, message="valid JSON"))
        except json.JSONDecodeError as exc:
            results.append(CheckResult(
                name=f"Config: {filename}",
                passed=False,
                message=f"invalid JSON: {exc}",
            ))
        except OSError as exc:
            results.append(CheckResult(
                name=f"Config: {filename}",
                passed=False,
                message=f"unreadable: {exc}",
            ))
    return results


def _check_output_writable(output_dir: str) -> List[CheckResult]:
    try:
        os.makedirs(output_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=output_dir, delete=True):
            pass
        return [CheckResult(name="Output directory writable", passed=True, message=output_dir)]
    except (OSError, PermissionError) as exc:
        return [CheckResult(
            name="Output directory writable",
            passed=False,
            message=f"cannot write to {output_dir}: {exc}",
        )]


_LIVE_MODE_KEYS = [
    ("APOLLO_API_KEY", "Apollo"),
    ("CLAY_API_KEY", "Clay"),
    ("HUBSPOT_PRIVATE_APP_TOKEN", "HubSpot"),
    ("ZEROBOUNCE_API_KEY", "ZeroBounce"),
    ("NEVERBOUNCE_API_KEY", "NeverBounce"),
]

_OPTIONAL_LIVE_KEYS = [
    ("VALIDITY_API_KEY", "Validity (optional)"),
    ("SLACK_WEBHOOK_URL", "Slack notifications (optional)"),
]


def _check_live_env_vars() -> List[CheckResult]:
    results = []
    for env_var, label in _LIVE_MODE_KEYS:
        val = os.getenv(env_var, "")
        results.append(CheckResult(
            name=f"Env: {label}",
            passed=bool(val),
            message="set" if val else f"{env_var} is not set",
        ))
    for env_var, label in _OPTIONAL_LIVE_KEYS:
        val = os.getenv(env_var, "")
        results.append(CheckResult(
            name=f"Env: {label}",
            passed=True,  # optional — always passes
            message="set" if val else "not set (optional)",
        ))
    return results
