from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import List, Optional

from src.storage.base import StorageBackend
from src.utils.logger import get_logger

log = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    company_count INTEGER DEFAULT 0,
    contact_count INTEGER DEFAULT 0,
    metadata TEXT
);

CREATE TABLE IF NOT EXISTS companies (
    run_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    company_name TEXT,
    industry TEXT,
    icp_tier TEXT,
    icp_score REAL,
    data TEXT,
    PRIMARY KEY (run_id, company_id)
);

CREATE TABLE IF NOT EXISTS contacts (
    run_id TEXT NOT NULL,
    contact_id TEXT NOT NULL,
    company_id TEXT,
    email TEXT,
    persona_type TEXT,
    final_validation_status TEXT,
    data TEXT,
    PRIMARY KEY (run_id, contact_id)
);

CREATE TABLE IF NOT EXISTS validation_results (
    run_id TEXT NOT NULL,
    email TEXT NOT NULL,
    zerobounce_status TEXT,
    neverbounce_status TEXT,
    final_status TEXT,
    checked_at TEXT,
    PRIMARY KEY (run_id, email)
);

CREATE TABLE IF NOT EXISTS campaign_health (
    run_id TEXT NOT NULL,
    campaign_name TEXT NOT NULL,
    emails_sent INTEGER,
    open_rate REAL,
    reply_rate REAL,
    meetings_booked INTEGER,
    domain_health_score REAL,
    data TEXT,
    PRIMARY KEY (run_id, campaign_name)
);
"""


class SQLiteBackend(StorageBackend):
    """SQLite-backed pipeline run storage."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)
        log.debug("SQLite storage initialized at %s", self.db_path)

    def save_pipeline_run(self, run_data: dict) -> str:
        run_id = run_data["run_id"]
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO pipeline_runs
                   (run_id, started_at, status, company_count, contact_count, metadata)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    run_data.get("started_at", now),
                    run_data.get("status", "running"),
                    run_data.get("company_count", 0),
                    run_data.get("contact_count", 0),
                    json.dumps({k: v for k, v in run_data.items()
                                if k not in ("run_id", "started_at", "status",
                                             "company_count", "contact_count")}),
                ),
            )
        return run_id

    def update_pipeline_run(self, run_id: str, updates: dict) -> None:
        allowed = {"status", "completed_at", "company_count", "contact_count"}
        fields = {k: v for k, v in updates.items() if k in allowed}
        if not fields:
            return
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        with self._conn() as conn:
            conn.execute(
                f"UPDATE pipeline_runs SET {set_clause} WHERE run_id = ?",
                list(fields.values()) + [run_id],
            )

    def save_companies(self, companies: List[dict], run_id: str) -> None:
        rows = [
            (
                run_id,
                c.get("company_id", ""),
                c.get("company_name", ""),
                c.get("industry", ""),
                c.get("icp_tier", ""),
                float(c.get("icp_score", 0) or 0),
                json.dumps(c),
            )
            for c in companies
        ]
        with self._conn() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO companies
                   (run_id, company_id, company_name, industry, icp_tier, icp_score, data)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
        log.debug("Saved %d companies for run %s", len(rows), run_id)

    def save_contacts(self, contacts: List[dict], run_id: str) -> None:
        rows = [
            (
                run_id,
                c.get("contact_id", ""),
                c.get("company_id", ""),
                c.get("email", ""),
                c.get("persona_type", ""),
                c.get("final_validation_status", ""),
                json.dumps(c),
            )
            for c in contacts
        ]
        with self._conn() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO contacts
                   (run_id, contact_id, company_id, email, persona_type,
                    final_validation_status, data)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
        log.debug("Saved %d contacts for run %s", len(rows), run_id)

    def save_campaign_health(self, metrics: List[dict], run_id: str) -> None:
        rows = [
            (
                run_id,
                m.get("campaign_name", ""),
                int(m.get("emails_sent", 0) or 0),
                float(m.get("open_rate", 0) or 0),
                float(m.get("reply_rate", 0) or 0),
                int(m.get("meetings_booked", 0) or 0),
                float(m.get("domain_health_score", 0) or 0),
                json.dumps(m),
            )
            for m in metrics
        ]
        with self._conn() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO campaign_health
                   (run_id, campaign_name, emails_sent, open_rate, reply_rate,
                    meetings_booked, domain_health_score, data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )

    def get_latest_run(self) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def get_run(self, run_id: str) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM pipeline_runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        return dict(row) if row else None
