# GTM System MVP

A mock-first outbound GTM pipeline built in Python. Models every stage of a real GTM operation — company ingestion, ICP scoring, enrichment, two-step email validation, HubSpot lifecycle sync, outreach sequence export, and campaign health monitoring.

The Python layer acts as the integration orchestration engine — like Zapier or n8n — but fully coded, versioned, and designed for easy swap to real API clients. Every integration has a `mock_client.py` (runs today, no keys needed) and an `api_client.py` (stub ready for real credentials).

---

## Mock-first experiment goal

The entire system runs with `MOCK_MODE=true` (the default). No API keys required. Every stage uses fake data and mock logic so you can:

- Walk through the full GTM workflow end-to-end
- Inspect every checkpoint output as a CSV
- Understand the data shape before wiring real APIs
- Run `pytest` to validate the business logic at every stage

When you are ready to connect a real tool, flip `MOCK_MODE=false`, add the API key to `.env`, and swap the mock client for the real one — one integration at a time.

---

## How to run

```bash
# 1. Clone the repo and create a virtual environment
git clone https://github.com/Sag-nikd/Gtm_System_Outbound.git
cd Gtm_System_Outbound

python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the full pipeline (mock mode, no API keys needed)
python src/main.py

# 4. Run the interactive step-by-step demo
python demo.py

# 5. Run tests
pytest tests/ -v
```

---

## Environment setup

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
|---|---|---|
| `MOCK_MODE` | `true` | Run with mock clients (no API keys needed) |
| `APOLLO_API_KEY` | _(empty)_ | Apollo firmographic + contact API |
| `CLAY_API_KEY` | _(empty)_ | Clay enrichment + waterfall API |
| `HUBSPOT_PRIVATE_APP_TOKEN` | _(empty)_ | HubSpot Private App for CRM upserts |
| `ZEROBOUNCE_API_KEY` | _(empty)_ | ZeroBounce email validation API |
| `NEVERBOUNCE_API_KEY` | _(empty)_ | NeverBounce second-pass validation API |
| `VALIDITY_API_KEY` | _(empty)_ | Validity deliverability + campaign data |
| `OUTPUT_DIR` | `outputs` | Where checkpoint CSVs are written |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`) |

The `.env` file is gitignored — it will never be committed.

---

## Pipeline workflow

```
fake_companies.json
      ↓
[run_company_pipeline]
  Apollo  → 01_company_ingestion.csv
  ICP Scoring (internal)
  Clay    → 02_company_enrichment.csv
            03_icp_scored_accounts.csv
  Gate    → 04_approved_accounts.csv     (Tier 1 + Tier 2 only)
      ↓
[run_contact_pipeline]
  Apollo  → 05_discovered_contacts.csv
  ZeroBounce + NeverBounce → 06_email_validation_results.csv
      ↓
[run_activation_pipeline]
  HubSpot → 07_hubspot_company_export.csv
            08_hubspot_contact_export.csv
  Outreach → 09_email_sequence_export.csv
             10_linkedin_outreach_export.csv
      ↓
[run_campaign_monitoring]
  Validity → 11_campaign_health_report.csv
```

---

## Output files

All 11 checkpoint CSVs are written to `outputs/` (excluded from git):

| # | File | What it contains |
|---|------|-----------------|
| 01 | `01_company_ingestion.csv` | Normalized firmographic data from Apollo |
| 02 | `02_company_enrichment.csv` | Enrichment signals + recommended personas from Clay |
| 03 | `03_icp_scored_accounts.csv` | Full ICP score breakdown per company |
| 04 | `04_approved_accounts.csv` | Tier 1 + Tier 2 accounts approved for contact discovery |
| 05 | `05_discovered_contacts.csv` | Contacts found for approved accounts |
| 06 | `06_email_validation_results.csv` | ZeroBounce + NeverBounce results + final decision |
| 07 | `07_hubspot_company_export.csv` | HubSpot-ready company records with lifecycle stages |
| 08 | `08_hubspot_contact_export.csv` | HubSpot-ready contact records |
| 09 | `09_email_sequence_export.csv` | Email sequence import (Outreach / Instantly / Smartlead) |
| 10 | `10_linkedin_outreach_export.csv` | LinkedIn sequence import (HeyReach) |
| 11 | `11_campaign_health_report.csv` | Campaign health status + recommended actions |

---

## Folder structure

```
gtm-system/
├── data/                          fake JSON data (companies, contacts, metrics)
├── config/                        icp_rules.json, lifecycle_mapping.json
├── src/
│   ├── config/
│   │   └── settings.py            env-driven settings singleton (MOCK_MODE, API keys, paths)
│   ├── schemas/
│   │   ├── company.py             pydantic Company model
│   │   ├── contact.py             pydantic Contact model
│   │   └── campaign.py            pydantic Campaign model
│   ├── integrations/
│   │   ├── apollo/                mock_client.py + api_client.py
│   │   ├── clay/                  mock_client.py + api_client.py
│   │   ├── hubspot/               mock_client.py + api_client.py
│   │   ├── zerobounce/            mock_client.py + api_client.py
│   │   ├── neverbounce/           mock_client.py + api_client.py
│   │   └── validity/              mock_client.py + api_client.py
│   ├── utils/
│   │   ├── logger.py              get_logger() factory
│   │   └── retry.py               api_retry tenacity decorator
│   ├── ingestion/                 company_ingestion.py (Apollo mock logic)
│   ├── scoring/                   icp_scoring.py (internal — not an external API)
│   ├── enrichment/                clay_mock_enrichment.py
│   ├── validation/                email_validation_mock.py
│   ├── hubspot/                   hubspot_sync_mock.py
│   ├── outreach/                  sequence_export.py
│   ├── monitoring/                campaign_health.py
│   └── main.py                    4-stage pipeline orchestrator
├── tests/
│   ├── conftest.py                shared pytest fixtures
│   ├── test_icp_scoring.py        ICP score logic + tier boundaries
│   ├── test_email_validation.py   ZeroBounce + NeverBounce + decision logic
│   ├── test_enrichment.py         Clay persona mapping + approval gate
│   ├── test_campaign_health.py    Campaign health thresholds + priority
│   ├── test_ingestion.py          Domain extraction + field normalization
│   ├── test_hubspot_mapping.py    HubSpot lifecycle stage mapping
│   └── test_pipeline_smoke.py     End-to-end pipeline smoke tests
├── demo.py                        interactive step-by-step CLI demo
├── .env.example                   environment variable template
├── .gitattributes                 force LF line endings
├── .gitignore
├── requirements.txt
└── README.md
```

---

## Future API roadmap

Each integration has a `mock_client.py` (current) and an `api_client.py` (stub). To activate a real integration:

1. Add the API key to `.env`
2. Implement the method body in `api_client.py`
3. Set `MOCK_MODE=false`

| Integration | Mock today | Real API target |
|---|---|---|
| **Apollo** | reads `fake_companies.json` + `fake_contacts.json` | Apollo firmographic + people search API |
| **Clay** | rule-based persona mapping | Clay enrichment workflows + waterfall enrichment |
| **ZeroBounce** | keyword-based mock | ZeroBounce v2 single/batch validation API |
| **NeverBounce** | pass-through (mock fuses both validators) | NeverBounce v4 verify API (independent second pass) |
| **HubSpot** | CSV-ready dicts | HubSpot Private App API — companies + contacts upsert |
| **Validity** | reads `fake_campaign_metrics.json` | Validity deliverability data + sequencing platform metrics |

---

## What is not included yet

- Real API calls (all integrations are mocked)
- Database or persistent storage
- Frontend or dashboard
- Docker or cloud deployment
- Authentication / multi-tenant support
- Outreach / Instantly / Smartlead / HeyReach API clients (sequence CSVs are generated; enrollment API is future)
- Scheduled / recurring pipeline runs

---

## AI SDR future layer

The AI SDR layer activates only after the GTM system produces clean, validated data. The AI SDR must only operate on:

- Tier 1 and Tier 2 accounts (scored and enriched)
- Contacts with `final_validation_status = approved`
- Approved personas mapped to the correct ICP profile
- Domains with healthy deliverability scores (`domain_health_score >= 70`)
- Contacts at lifecycle stage `Contact Validated → Ready for Outreach`

The GTM system is the prerequisite data pipeline. The AI SDR is the activation layer on top of clean data.
