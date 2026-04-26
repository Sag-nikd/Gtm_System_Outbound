"""
Company ingestion module.
# Future: Replace this JSON loader with Apollo firmographic API ingestion.
"""

from __future__ import annotations
import json
from urllib.parse import urlparse


REQUIRED_FIELDS = [
    "company_id", "company_name", "website", "industry",
    "employee_count", "revenue_range", "state",
    "medicaid_members", "medicare_members",
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
    for record in raw:
        missing = [field for field in REQUIRED_FIELDS if field not in record]
        if missing:
            print(f"  [WARN] Skipping {record.get('company_id', '?')}: missing fields {missing}")
            continue
        companies.append(_normalize_company(record))

    return companies
