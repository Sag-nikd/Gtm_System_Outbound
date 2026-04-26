from __future__ import annotations

from typing import Any, Dict, List

from src.crm.base import FieldResult, FieldStatus, SetupReport
from src.utils.logger import get_logger

log = get_logger(__name__)


def find_field_conflicts(
    required_fields: List[Dict[str, Any]],
    existing_fields: List[Dict[str, Any]],
    name_key: str = "internal_name",
    type_key: str = "type",
) -> List[Dict[str, Any]]:
    """Return fields that exist in CRM but have a different type than required."""
    existing_map = {f[name_key]: f for f in existing_fields if name_key in f}
    conflicts = []
    for req in required_fields:
        name = req.get(name_key)
        if name and name in existing_map:
            existing_type = existing_map[name].get(type_key, "")
            required_type = req.get(type_key, "")
            if existing_type and required_type and existing_type != required_type:
                conflicts.append({
                    "field": name,
                    "required_type": required_type,
                    "existing_type": existing_type,
                })
    return conflicts


def find_missing_fields(
    required_fields: List[Dict[str, Any]],
    existing_fields: List[Dict[str, Any]],
    name_key: str = "internal_name",
) -> List[Dict[str, Any]]:
    """Return required fields that do not exist in the CRM."""
    existing_names = {f.get(name_key) for f in existing_fields}
    return [f for f in required_fields if f.get(name_key) not in existing_names]


def build_gap_report(report: SetupReport) -> str:
    """Produce a plain-text gap summary from a SetupReport."""
    lines: List[str] = [
        f"# CRM Gap Report — {report.client_name} ({report.crm_type})",
        f"Mode: {report.mode}   Timestamp: {report.timestamp}",
        "",
        "## Fields",
        f"  Planned:      {len(report.fields_by_status(FieldStatus.PLANNED))}",
        f"  Created:      {len(report.fields_by_status(FieldStatus.CREATED))}",
        f"  Skipped:      {len(report.fields_by_status(FieldStatus.SKIPPED_EXISTS))}",
        f"  Needs Review: {len(report.fields_by_status(FieldStatus.NEEDS_REVIEW))}",
        f"  Failed:       {len(report.fields_by_status(FieldStatus.FAILED))}",
        "",
    ]
    conflicts = report.fields_by_status(FieldStatus.NEEDS_REVIEW)
    if conflicts:
        lines.append("## Fields Needing Manual Review")
        for f in conflicts:
            lines.append(f"  - [{f.object_name}] {f.internal_name}: {f.note}")
        lines.append("")

    failed = report.fields_by_status(FieldStatus.FAILED)
    if failed:
        lines.append("## Failed Fields")
        for f in failed:
            lines.append(f"  - [{f.object_name}] {f.internal_name}: {f.note}")
        lines.append("")

    if report.warnings:
        lines.append("## Warnings")
        for w in report.warnings:
            lines.append(f"  - {w}")
        lines.append("")

    if report.errors:
        lines.append("## Errors")
        for e in report.errors:
            lines.append(f"  - {e}")
        lines.append("")

    if report.next_manual_steps:
        lines.append("## Next Manual Steps in CRM UI")
        for step in report.next_manual_steps:
            lines.append(f"  - {step}")
        lines.append("")

    return "\n".join(lines)
