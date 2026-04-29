"""
Stage registry — defines every pipeline stage, its dependencies, and required clients.
Used by the runner to resolve execution order and validate prerequisites.
"""
from __future__ import annotations

from collections import OrderedDict
from typing import Dict, List, Optional

# Ordered so iteration always reflects pipeline order.
STAGES: Dict[str, dict] = OrderedDict([
    ("stage0", {
        "display_name": "ICP Intelligence",
        "description": "ICP recalibration — optional, generates scoring config",
        "dependencies": [],
        "clients_needed": [],
        "output_file": None,   # writes config, not staging data
        "optional": True,
    }),
    ("stage1", {
        "display_name": "Company Pipeline",
        "description": "Apollo → ICP score → Clay enrich → approval gate",
        "dependencies": [],
        "clients_needed": ["apollo", "clay"],
        "output_file": "stage1_enriched.json",
        "optional": False,
    }),
    ("stage2", {
        "display_name": "Contact Pipeline",
        "description": "Contact discovery → ZeroBounce → NeverBounce",
        "dependencies": ["stage1"],
        "clients_needed": ["apollo", "zerobounce", "neverbounce"],
        "output_file": "stage2_validated.json",
        "optional": False,
    }),
    ("stage3", {
        "display_name": "Activation Pipeline",
        "description": "CRM sync → email sequences → LinkedIn sequences",
        "dependencies": ["stage1", "stage2"],
        "clients_needed": ["hubspot"],
        "output_file": "stage3_activation.json",
        "optional": False,
    }),
    ("stage4", {
        "display_name": "Campaign Monitoring",
        "description": "Validity metrics → health report",
        "dependencies": [],
        "clients_needed": ["validity"],
        "output_file": "stage4_monitoring.json",
        "optional": False,
    }),
])

# Stages that cannot run concurrently (stage2 output is stage3 input mid-write).
CONFLICT_PAIRS = [("stage2", "stage3"), ("stage3", "stage2")]


def get_stage(name: str) -> dict:
    if name not in STAGES:
        raise KeyError(f"Unknown stage '{name}'. Valid stages: {list(STAGES)}")
    return STAGES[name]


def get_all_prerequisites(stage_name: str) -> List[str]:
    """Return all prerequisite stages in topological order."""
    visited: List[str] = []
    _topo(stage_name, visited, set())
    return [s for s in visited if s != stage_name]


def _topo(name: str, order: List[str], seen: set) -> None:
    if name in seen:
        return
    seen.add(name)
    for dep in STAGES[name]["dependencies"]:
        _topo(dep, order, seen)
    order.append(name)


def topological_order(stage_names: List[str]) -> List[str]:
    """Return the given stages sorted in valid execution order."""
    visited: List[str] = []
    seen: set = set()
    for name in stage_names:
        _topo(name, visited, seen)
    return [s for s in visited if s in stage_names]


def validate_no_cycles() -> None:
    """Raise if the dependency graph contains a cycle (safety check)."""
    for stage in STAGES:
        _check_cycle(stage, [], set())


def _check_cycle(name: str, path: List[str], visiting: set) -> None:
    if name in visiting:
        raise RuntimeError(f"Cycle detected in stage dependencies: {' → '.join(path + [name])}")
    visiting.add(name)
    for dep in STAGES[name]["dependencies"]:
        _check_cycle(dep, path + [name], visiting)
    visiting.discard(name)


# Validate on import.
validate_no_cycles()
