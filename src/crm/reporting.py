from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List

from src.crm.base import FieldStatus, SetupReport
from src.crm.validation import build_gap_report
from src.utils.logger import get_logger

log = get_logger(__name__)


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def write_setup_plan_json(report: SetupReport, output_dir: str) -> str:
    fname = f"{report.client_name}_{report.crm_type}_setup_plan.json"
    path = os.path.join(output_dir, fname)
    _ensure_dir(path)
    payload: Dict[str, Any] = {
        **report.summary(),
        "fields": [
            {
                "object": f.object_name,
                "internal_name": f.internal_name,
                "label": f.label,
                "type": f.field_type,
                "status": f.status.value,
                "note": f.note,
            }
            for f in report.fields
        ],
        "pipelines": [
            {
                "name": p.pipeline_name,
                "status": p.status.value,
                "pipeline_id": p.pipeline_id,
                "note": p.note,
            }
            for p in report.pipelines
        ],
        "stages": [
            {
                "pipeline": s.pipeline_name,
                "label": s.stage_label,
                "probability": s.probability,
                "status": s.status.value,
                "note": s.note,
            }
            for s in report.stages
        ],
        "warnings": report.warnings,
        "errors": report.errors,
        "next_manual_steps": report.next_manual_steps,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    log.info("Setup plan written: %s", path)
    return path


def write_setup_report_md(report: SetupReport, output_dir: str) -> str:
    fname = f"{report.client_name}_{report.crm_type}_setup_report.md"
    path = os.path.join(output_dir, fname)
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_gap_report(report))
    log.info("Setup report written: %s", path)
    return path


def write_field_inventory_csv(report: SetupReport, output_dir: str) -> str:
    fname = f"{report.client_name}_{report.crm_type}_field_inventory.csv"
    path = os.path.join(output_dir, fname)
    _ensure_dir(path)
    rows = [
        {
            "object": f.object_name,
            "internal_name": f.internal_name,
            "label": f.label,
            "type": f.field_type,
            "status": f.status.value,
            "note": f.note,
        }
        for f in report.fields
    ]
    if rows:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    log.info("Field inventory written: %s (%d rows)", path, len(rows))
    return path


def write_pipeline_plan_csv(report: SetupReport, output_dir: str) -> str:
    fname = f"{report.client_name}_{report.crm_type}_pipeline_plan.csv"
    path = os.path.join(output_dir, fname)
    _ensure_dir(path)
    rows: List[Dict[str, Any]] = []
    for p in report.pipelines:
        rows.append({
            "type": "pipeline",
            "pipeline_name": p.pipeline_name,
            "stage_label": "",
            "probability": "",
            "status": p.status.value,
            "note": p.note,
        })
    for s in report.stages:
        rows.append({
            "type": "stage",
            "pipeline_name": s.pipeline_name,
            "stage_label": s.stage_label,
            "probability": s.probability,
            "status": s.status.value,
            "note": s.note,
        })
    if rows:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    log.info("Pipeline plan written: %s (%d rows)", path, len(rows))
    return path


def write_validation_report_json(report: SetupReport, output_dir: str) -> str:
    fname = f"{report.client_name}_{report.crm_type}_validation_report.json"
    path = os.path.join(output_dir, fname)
    _ensure_dir(path)
    payload = {
        **report.summary(),
        "warnings": report.warnings,
        "errors": report.errors,
        "fields_needs_review": [
            {"object": f.object_name, "field": f.internal_name, "note": f.note}
            for f in report.fields_by_status(FieldStatus.NEEDS_REVIEW)
        ],
        "fields_failed": [
            {"object": f.object_name, "field": f.internal_name, "note": f.note}
            for f in report.fields_by_status(FieldStatus.FAILED)
        ],
        "next_manual_steps": report.next_manual_steps,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    log.info("Validation report written: %s", path)
    return path


def write_all_reports(report: SetupReport, output_dir: str) -> List[str]:
    """Write all 5 output files and return their paths."""
    return [
        write_setup_plan_json(report, output_dir),
        write_setup_report_md(report, output_dir),
        write_field_inventory_csv(report, output_dir),
        write_pipeline_plan_csv(report, output_dir),
        write_validation_report_json(report, output_dir),
    ]
