"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-29

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("domain", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("employee_count", sa.Integer(), nullable=True),
        sa.Column("revenue_band", sa.String(50), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("icp_score", sa.Float(), nullable=True),
        sa.Column("icp_tier", sa.String(20), nullable=True),
        sa.Column("fit_reason", sa.String(1000), nullable=True),
        sa.Column("pipeline_state", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("persona", sa.String(100), nullable=True),
        sa.Column("linkedin_url", sa.String(500), nullable=True),
        sa.Column("validation_status", sa.String(50), nullable=True),
        sa.Column("pipeline_state", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("running", "completed", "failed", "aborted", name="runstatus"),
            default="running",
            nullable=False,
        ),
        sa.Column("config_snapshot", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "run_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("pipeline_runs.id"), nullable=False),
        sa.Column("stage", sa.String(100), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "vendor_calls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("pipeline_runs.id"), nullable=True),
        sa.Column(
            "vendor",
            sa.Enum(
                "apollo", "zerobounce", "instantly", "hubspot", "gong",
                "granola", "notion", "anthropic", "voyage", "sendgrid", "slack",
                name="vendorname",
            ),
            nullable=False,
        ),
        sa.Column("endpoint", sa.String(255), nullable=False),
        sa.Column("units_consumed", sa.Float(), nullable=True),
        sa.Column("credit_cost", sa.Float(), nullable=True),
        sa.Column("dollar_cost", sa.Float(), nullable=True),
        sa.Column("success", sa.Boolean(), default=True, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("called_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("vendor_calls")
    op.drop_table("run_events")
    op.drop_table("pipeline_runs")
    op.drop_table("contacts")
    op.drop_table("companies")
