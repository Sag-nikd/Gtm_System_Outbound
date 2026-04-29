"""
Company ingestion module.
# Future: Replace this JSON loader with Apollo firmographic API ingestion.
"""

from __future__ import annotations
import json
from urllib.parse import urlparse

from pydantic import ValidationError

from src.schemas.company import Company
from src.utils.logger import get_logger

log = get_logger(__name__)

REQUIRED_FIELDS = [
    "company_id", "company_name", "website", "industry",
    "employee_count", "revenue_range", "state",
    "primary_volume_metric", "secondary_volume_metric",
    "growth_signal", "hiring_signal", "tech_stack_signal",
]


def _extract_domain(website: str) -> str:
    try:
        parsed = urlparse(website if website.startswith("http") else f"https://{website}")
        return parsed.netloc.replace("www.", "").strip()
    except Exception:
        return website.strip()


def _normalize_company(company: dict) -> dict:
    company["company_name"] = company["company_name"].strip().title()
    company["industry"] = company["industry"].strip().title()
    company["state"] = company["state"].strip().title()
    company["website"] = company["website"].strip().lower()
    company["domain"] = _extract_domain(company["website"])
    company["ingestion_source"] = "fake_data"   # Future: Apollo
    company["ingestion_status"] = "ingested"
    return company


def load_companies(file_path: str) -> list[dict]:
    with open(file_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    companies = []
    seen_ids: set = set()
    for record in raw:
        missing = [field for field in REQUIRED_FIELDS if field not in record]
        if missing:
            log.warning("Skipping %s: missing fields %s", record.get("company_id", "?"), missing)
            continue
        normalized = _normalize_company(record)
        try:
            Company(**normalized)
        except ValidationError as exc:
            log.warning(
                "Skipping %s: schema validation failed — %s",
                normalized.get("company_id", "?"), exc.error_count()
            )
            continue
        cid = normalized.get("company_id", "")
        if cid in seen_ids:
            log.warning("Skipping duplicate company_id '%s'", cid)
            continue
        seen_ids.add(cid)
        companies.append(normalized)

    return companies
