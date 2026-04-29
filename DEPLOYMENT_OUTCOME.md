# GTM Pipeline — Deployment Outcome

Sprint completed: 2026-04-29  
Stories delivered: 22 across 4 epics  
Test coverage: **406 tests, all passing**

---

## What Was Built

A production-ready, industry-agnostic B2B outbound pipeline. The system ingests
companies and contacts, scores them against configurable ICP rules, enriches via
external APIs, validates emails, syncs to CRM, and enrolls approved contacts into
outreach sequences — all with per-integration mock/live switching and optional
persistent storage.

---

## Epic 1 — De-verticalization (Stories 1.1–1.6)

Removed all healthcare-specific hardcodes and replaced with config-driven behavior.

| Story | Deliverable |
|-------|-------------|
| 1.1 | Renamed `medicaid_members`/`medicare_members` → `primary_volume_metric`/`secondary_volume_metric` throughout schema |
| 1.2 | ICP scoring weights and rules externalized to `config/icp_config.json` |
| 1.3 | Outreach copy (email angles, LinkedIn templates, campaign name) externalized to `config/outreach_templates.json` |
| 1.4 | Persona map (industry → personas) externalized to `config/persona_map.json` |
| 1.5 | Removed hardcoded HubSpot portal ID; reads `HUBSPOT_PORTAL_ID` env var |
| 1.6 | Rebuilt `data/fake_companies.json` (15 companies, 9 industries) and `data/fake_contacts.json` (22 contacts) with generic B2B verticals |

---

## Epic 2 — Live API Clients (Stories 2.1–2.4)

Each integration now has a real HTTP client alongside the existing mock.

| Story | Deliverable |
|-------|-------------|
| 2.1 | `ApolloAPIClient` — POST `/mixed_companies/search` and `/mixed_people/search`; maps responses to internal schema |
| 2.2 | `ZeroBounceAPIClient` — batch validation via POST `/validatebatch`; 100 emails per call; maps status to `final_validation_status` |
| 2.3 | Per-integration `{NAME}_MODE=mock\|live` env vars; `settings._validate()` enforces API keys for live integrations |
| 2.4 | `HubSpotAPIClient` batch upsert — `/batch/create` and `/batch/update` for companies and contacts; 100 records per call |

---

## Epic 3 — Reliability & Ops (Stories 3.1–3.5)

| Story | Deliverable |
|-------|-------------|
| 3.1 | Abstract `StorageBackend` + `SQLiteBackend`; 5 tables (`pipeline_runs`, `companies`, `contacts`, `validation_results`, `campaign_health`); opt-in via `STORAGE_ENABLED=true` |
| 3.2 | `ClayAPIClient` — POST `/enrichment/company`; falls back to local persona-map enrichment on network failure |
| 3.3 | `.github/workflows/pipeline.yml` — weekly cron (`0 8 * * 1`) + `workflow_dispatch`; uploads output artifacts |
| 3.4 | Replaced all broad `except Exception: pass` handlers with specific exception types |
| 3.5 | Cross-run deduplication via `outputs/sync_history.json`; skips companies with unchanged `icp_score`, skips known contact emails |

---

## Epic 4 — Production Hardening (Stories 4.1–4.5)

| Story | Deliverable |
|-------|-------------|
| 4.1 | `EnrollmentBase` ABC + `MockEnrollmentClient` + `ApolloSequenceClient`; `get_enrollment_client()` factory |
| 4.2 | `src/monitoring/dashboard.py` — reads `run_manifest.json` + `11_campaign_health_report.csv`; `print_dashboard()` terminal output + `get_pipeline_summary()` structured dict |
| 4.3 | `Dockerfile` (`python:3.11-slim`) + `docker-compose.yml` with optional PostgreSQL service (`profiles: [postgres]`) |
| 4.4 | `SalesforceClient` — OAuth2 username-password flow; REST + Tooling API for upsert and field creation |
| 4.5 | `NeverBounceAPIClient` — single-check GET per contact; overrides `final_validation_status` to `suppressed` on disagreement |

---

## Architecture

```
[Data Source]
  Apollo API / local JSON
       │
       ▼
[Ingestion]  src/ingestion/
  Companies + contacts loaded
       │
       ▼
[ICP Scoring]  src/scoring/
  Config-driven weights from icp_config.json
       │
       ▼
[Enrichment]  src/enrichment/ + src/integrations/clay/
  Industry personas, Clay API with local fallback
       │
       ▼
[Email Validation]  src/integrations/zerobounce/ + neverbounce/
  ZeroBounce batch → NeverBounce second-pass
       │
       ▼
[CRM Sync]  src/crm/hubspot/ + src/crm/salesforce/
  HubSpot batch upsert, Salesforce REST/Tooling
       │
       ▼
[Outreach Enrollment]  src/outreach/
  Apollo Sequences or mock
       │
       ▼
[Storage]  src/storage/  (optional)
  SQLite or pluggable backend
       │
       ▼
[Monitoring]  src/monitoring/
  Terminal dashboard + structured summary
```

---

## Configuration

| File | Purpose |
|------|---------|
| `config/icp_config.json` | Scoring weights, industry multipliers, tier thresholds |
| `config/persona_map.json` | Industry → target personas mapping |
| `config/outreach_templates.json` | Email angles, LinkedIn copy, campaign name |
| `.env` | Runtime secrets and mode flags (never committed) |

### Key environment variables

```
MOCK_MODE=true|false          # global default for all integrations
APOLLO_MODE=mock|live
CLAY_MODE=mock|live
HUBSPOT_MODE=mock|live
ZEROBOUNCE_MODE=mock|live
NEVERBOUNCE_MODE=mock|live
STORAGE_ENABLED=false|true
STORAGE_DB_PATH=outputs/gtm_pipeline.db
HUBSPOT_PORTAL_ID=...
APOLLO_API_KEY=...
CLAY_API_KEY=...
HUBSPOT_API_KEY=...
ZEROBOUNCE_API_KEY=...
NEVERBOUNCE_API_KEY=...
SF_CLIENT_ID=...
SF_CLIENT_SECRET=...
SF_USERNAME=...
SF_PASSWORD=...
SF_SECURITY_TOKEN=...
SF_INSTANCE_URL=...
```

---

## Running

```bash
# Mock mode (default — no API keys required)
python src/main.py

# Docker
docker build -t gtm-pipeline .
docker run --env-file .env gtm-pipeline

# Docker with PostgreSQL
docker compose --profile postgres up

# GitHub Actions
# Runs automatically every Monday 08:00 UTC
# Or trigger manually from Actions tab
```

---

## Commits

| Commit | Story group |
|--------|------------|
| `148a31a` | Epic 1 Stories 1.2–1.5: de-verticalize config |
| `c53f1e5` | Story 1.6: rebuild generic mock data |
| `ce5162d` | Epic 2 Stories 2.1–2.4: live API clients |
| `37f5232` | Epic 3 Stories 3.1–3.5: storage, scheduling, dedup |
| `74b2065` | Epic 4 Stories 4.1–4.5: enrollment, dashboard, Docker, Salesforce, NeverBounce |
