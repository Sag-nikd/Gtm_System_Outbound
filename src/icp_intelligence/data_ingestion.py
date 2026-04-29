from __future__ import annotations

import csv
import json
import os
from typing import List

from pydantic import ValidationError

from src.schemas.deal_record import DealRecord, PipelineRecord, TAMRecord
from src.utils.logger import get_logger

log = get_logger(__name__)

_DEAL_STAGES = {
    "prospecting", "contacted", "meeting_booked", "proposal_sent",
    "negotiation", "closed_won", "closed_lost", "disqualified",
}


def _read_file(file_path: str) -> List[dict]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [dict(row) for row in reader]
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def _coerce_numeric(record: dict, fields: List[str]) -> dict:
    """Convert string numerics from CSV parsing to int/float where applicable."""
    out = dict(record)
    for field in fields:
        val = out.get(field)
        if val == "" or val is None:
            out[field] = None
            continue
        if isinstance(val, str):
            try:
                out[field] = int(val) if "." not in val else float(val)
            except ValueError:
                out[field] = None
    return out


def load_deal_data(file_path: str) -> List[dict]:
    raw = _read_file(file_path)
    records = []
    seen_domains: dict = {}  # domain -> (index, closed_date)

    for i, record in enumerate(raw):
        record = _coerce_numeric(record, ["employee_count", "medicaid_members", "medicare_members",
                                          "deal_value", "deal_cycle_days"])
        try:
            DealRecord(**record)
        except ValidationError as exc:
            log.warning("Skipping deal record '%s': %d validation error(s)",
                        record.get("company_name", "?"), exc.error_count())
            continue

        domain = (record.get("domain") or "").strip().lower()
        closed_date = record.get("closed_date") or ""

        if domain:
            if domain in seen_domains:
                prev_idx, prev_date = seen_domains[domain]
                if closed_date > prev_date:
                    # Replace previous with this newer one
                    records[prev_idx] = None
                    seen_domains[domain] = (len(records), closed_date)
                    records.append(record)
                # else: skip this older duplicate
                continue
            seen_domains[domain] = (len(records), closed_date)

        records.append(record)

    result = [r for r in records if r is not None]
    log.info("Loaded %d deal records from %s", len(result), file_path)
    return result


def load_pipeline_data(file_path: str) -> List[dict]:
    raw = _read_file(file_path)
    records = []
    for record in raw:
        record = _coerce_numeric(record, ["deal_value", "days_in_stage", "engagement_score"])
        try:
            PipelineRecord(**record)
        except ValidationError as exc:
            log.warning("Skipping pipeline record '%s': %d validation error(s)",
                        record.get("company_name", "?"), exc.error_count())
            continue
        records.append(record)
    log.info("Loaded %d pipeline records from %s", len(records), file_path)
    return records


def load_tam_data(file_path: str) -> List[dict]:
    raw = _read_file(file_path)
    records = []
    for record in raw:
        record = _coerce_numeric(record, ["employee_count", "medicaid_members", "medicare_members"])
        try:
            TAMRecord(**record)
        except ValidationError as exc:
            log.warning("Skipping TAM record '%s': %d validation error(s)",
                        record.get("company_name", "?"), exc.error_count())
            continue
        records.append(record)
    log.info("Loaded %d TAM records from %s", len(records), file_path)
    return records
