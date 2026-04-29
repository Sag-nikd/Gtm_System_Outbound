# GTM System — Outbound Pipeline

A fully coded outbound GTM pipeline built in Python. Models every stage of a real outbound operation: ICP intelligence (data-driven targeting), company ingestion, ICP scoring, enrichment, two-step email validation, HubSpot CRM sync, outreach sequence export, and campaign health monitoring.

**Runs today on mock data — no paid API keys required. Designed to swap each integration to a real paid API one at a time.**

---

## How it works

The Python layer acts as the integration orchestration engine — like Zapier or n8n, but fully coded, versioned, and source-controlled. Every external tool (Apollo, Clay, ZeroBounce, HubSpot, etc.) has two clients:

| Client | Purpose |
|---|---|
| `mock_client.py` | Reads from local fake JSON files. Runs today with no credentials. |
| `api_client.py` | Stub wired to the real paid API. Activate by adding the key to `.env`. |

When you are ready to connect a real tool, you add the API key to `.env` and point the pipeline at `api_client` instead of `mock_client` — one integration at a time, without touching anything else.

---

## Current status

| Integration | Status | Notes |
|---|---|---|
| **Apollo** | Mock | Reads `fake_companies.json` + `fake_contacts.json` |
| **Clay** | Mock | Rule-based persona mapping + enrichment simulation |
| **ZeroBounce** | Mock | Keyword-based validation logic |
| **NeverBounce** | Mock | Pass-through (second-pass validator stub) |
| **HubSpot** | **Live** | Real CRM sync — companies, contacts, associations, custom properties |
| **Validity** | Mock | Reads `fake_campaign_metrics.json` |

HubSpot is the first integration running against a real API. The CRM setup script creates all custom properties and the deal pipeline in your portal. The sync script pushes scored companies and validated contacts with full contact-company associations.

Replacing the remaining mocks with real paid APIs requires only implementing the method bodies in the corresponding `api_client.py` files.

---

## Stage 0: ICP Intelligence Engine

Before the pipeline runs, Stage 0 analyzes your historical deal data to discover who actually buys from you — then auto-generates the ICP scoring config and Apollo search filters that drive the rest of the pipeline.

```
Your Deal History (CSV/JSON)
        ↓
  [Stage 0: ICP Intelligence]
  • Load & validate deal records
  • Analyze conversion patterns by industry, size, geo, tech stack
  • Generate icp_rules.json (replaces manual config)
  • Build Apollo search filters
  • Detect ICP drift from prior runs
        ↓
  config/icp_rules.json          ← used by Stage 1 scoring
  config/apollo_query_config.json ← used by Apollo client
  outputs/00_icp_intelligence_report.json
  outputs/00_icp_summary.csv
        ↓
  [Stage 1 → Stage 2 → Stage 3 → Stage 4]
        ↓
  outputs/pipeline_outcomes.csv  ← you fill in after outreach
        ↑
  [Next run: Stage 0 reads outcomes → refines ICP]
```

### Run Stage 0 standalone

```bash
# Analyze mock deal history (no API keys needed)
python -m src.icp_intelligence_runner --deals data/icp_intelligence/mock_deal_history.json

# Analyze your own deal data (CSV or JSON)
python -m src.icp_intelligence_runner --deals data/your_deals.csv
```

### Enable Stage 0 in the full pipeline

```bash
# In .env
ICP_INTELLIGENCE_ENABLED=true
ICP_DEAL_DATA_PATH=data/icp_intelligence/mock_deal_history.json
```

Then run `python -m src.main` — Stage 0 fires first and updates `config/icp_rules.json` before scoring begins.

**Full walkthrough:** [docs/ICP_INTELLIGENCE_GUIDE.md](docs/ICP_INTELLIGENCE_GUIDE.md)
**Data format reference:** [docs/DATA_FORMAT_REFERENCE.md](docs/DATA_FORMAT_REFERENCE.md)

---

## Quick start

```bash
# 1. Clone and set up a virtual environment
git clone https://github.com/Sag-nikd/Gtm_System_Outbound.git
cd Gtm_System_Outbound

python -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the full pipeline (mock mode — no API keys needed)
python src/main.py

# 4. Run the interactive demo
python demo.py

# 5. Run tests
pytest tests/ -v
```

---

## Connecting real APIs

### Step 1 — Copy the env template

```bash
cp .env.example .env
```

### Step 2 — Add keys for the integrations you want to activate

| Variable | Paid service |
|---|---|
| `APOLLO_API_KEY` | Apollo.io — company + contact search |
| `CLAY_API_KEY` | Clay — enrichment waterfall |
| `ZEROBOUNCE_API_KEY` | ZeroBounce — email validation (primary) |
| `NEVERBOUNCE_API_KEY` | NeverBounce — email validation (second pass) |
| `HUBSPOT_PRIVATE_APP_TOKEN` | HubSpot Private App — CRM upserts |
| `VALIDITY_API_KEY` | Validity — deliverability + campaign health |

### Step 3 — Run CRM setup (HubSpot only, first time)

```bash
# Creates all custom properties and deal pipeline in your HubSpot portal
python scripts/generate_crm_setup.py --client default --crm hubspot --mode live
```

### Step 4 — Push pipeline output to HubSpot

```bash
# Runs the full simulation and syncs companies + contacts to HubSpot
python scripts/sync_to_hubspot.py
```

### Step 5 — Swap a mock for a real client

In each pipeline stage, replace:

```python
from src.integrations.apollo import ApolloMockClient
```

with:

```python
from src.integrations.apollo import ApolloApiClient
```

Then implement the method body in `api_client.py` using the vendor's SDK or REST endpoint. All interfaces are identical — mock and real clients share the same method signatures.

---

## Pipeline stages

```
[Stage 0: ICP Intelligence]  (optional — enable via ICP_INTELLIGENCE_ENABLED=true)
  0. Analyze deal history     -> config/icp_rules.json (auto-updated)
                                 config/apollo_query_config.json
                                 outputs/00_icp_intelligence_report.json
                                 outputs/00_icp_summary.csv
        |
[Stage 1: Company Pipeline]
  (Input: fake_companies.json or Apollo API — filtered by Apollo query config)
  1. Apollo ingestion         -> 01_company_ingestion.csv
  2. ICP scoring (internal)   -> 03_icp_scored_accounts.csv
  3. Clay enrichment          -> 02_company_enrichment.csv
  4. Tier gate (Tier 1 + 2)   -> 04_approved_accounts.csv
        |
[Stage 2: Contact Pipeline]
  5. Apollo contact discovery -> 05_discovered_contacts.csv
  6. ZeroBounce validation    -> 06_email_validation_results.csv
  7. NeverBounce second pass  -> (merged into file 06)
        |
[Stage 3: Activation]
  8. HubSpot CRM sync         -> companies + contacts + associations (live)
  9. Outreach sequence export -> 09_email_sequence_export.csv
 10. LinkedIn export          -> 10_linkedin_outreach_export.csv
        |
[Stage 4: Monitoring]
 11. Validity campaign health -> 11_campaign_health_report.csv
        |
[Feedback loop]
     Fill in pipeline_outcomes.csv → re-run Stage 0 to refine ICP
```

---

## Output files

All checkpoint CSVs and reports are written to `outputs/` (gitignored):

| # | File | Contents |
|---|------|----------|
| 00a | `00_icp_intelligence_report.json` | Full ICPProfile, drift report, Apollo config (Stage 0) |
| 00b | `00_icp_summary.csv` | One row per industry — conversion rate, win count, index (Stage 0) |
| 01 | `01_company_ingestion.csv` | Normalized firmographic data |
| 02 | `02_company_enrichment.csv` | Enrichment signals + recommended personas |
| 03 | `03_icp_scored_accounts.csv` | ICP score breakdown per company |
| 04 | `04_approved_accounts.csv` | Tier 1 + 2 accounts approved for outreach |
| 05 | `05_discovered_contacts.csv` | Contacts found for approved accounts |
| 06 | `06_email_validation_results.csv` | Validation results + final send/suppress decision |
| 07 | `07_hubspot_company_export.csv` | HubSpot-ready company records |
| 08 | `08_hubspot_contact_export.csv` | HubSpot-ready contact records |
| 09 | `09_email_sequence_export.csv` | Email sequence import (Outreach / Instantly / Smartlead) |
| 10 | `10_linkedin_outreach_export.csv` | LinkedIn sequence import (HeyReach) |
| 11 | `11_campaign_health_report.csv` | Campaign health status + recommended actions |

---

## HubSpot custom properties

The setup script creates these properties in your HubSpot portal under the **GTM Properties** group:

**Companies**

| Property | Type | Description |
|---|---|---|
| `icp_score` | Number | Numeric fit score (0–100) |
| `icp_tier` | Enum | Tier 1 / Tier 2 / Tier 3 / Rejected |
| `gtm_segment` | Enum | enterprise / mid_market / smb / startup |
| `enrichment_status` | Enum | enriched / needs_review / failed |
| `account_source` | String | Lead source (e.g. Apollo) |
| `fit_reason` | String | Human-readable scoring rationale |
| `last_scored_date` | Date | Date of last ICP score run |

**Contacts**

| Property | Type | Description |
|---|---|---|
| `buyer_persona` | Enum | CEO / Founder / VP Sales / RevOps / etc. |
| `email_validation_status` | Enum | valid / risky / invalid |
| `sequence_status` | Enum | not_added / enrolled / completed |
| `outreach_channel` | Enum | email / linkedin / none |
| `contact_source` | String | Lead source (e.g. Apollo) |
| `gtm_linkedin_url` | String | LinkedIn profile URL |

---

## Folder structure

```
gtm-system/
├── data/
│   ├── icp_intelligence/          Deal history + pipeline outcomes for Stage 0
│   │   ├── mock_deal_history.json      30 historical deals (closed_won/lost/disqualified)
│   │   ├── mock_pipeline_active.json   10 active pipeline deals
│   │   ├── mock_tam_universe.json      50-company TAM (7 existing customers)
│   │   └── mock_pipeline_outcomes.csv  15 outreach outcome records
│   └── (fake_companies.json, fake_contacts.json, fake_campaign_metrics.json)
├── config/
│   ├── icp_rules.json             ICP scoring weights and tier thresholds
│   ├── lifecycle_mapping.json     Lifecycle stage transition rules
│   └── crm/
│       ├── hubspot_default_setup.yaml   All GTM custom properties + pipeline definition
│       ├── salesforce_default_setup.yaml
│       ├── client_template.yaml         Per-client override template
│       ├── lifecycle_rules.yaml
│       ├── pipeline_templates.yaml
│       └── field_mapping.yaml
├── scripts/
│   ├── generate_crm_setup.py      Create HubSpot/Salesforce properties + pipeline
│   ├── validate_crm_setup.py      Inspect-only: compare config vs live CRM state
│   └── sync_to_hubspot.py         Run simulation and push output to HubSpot
├── src/
│   ├── icp_intelligence/          Stage 0: ICP Intelligence Engine
│   │   ├── data_ingestion.py          CSV/JSON loader + Pydantic validation + dedup
│   │   ├── profile_analyzer.py        Conversion rate analysis → ICPProfile
│   │   ├── rules_generator.py         ICPProfile → icp_rules.json + history backup
│   │   ├── apollo_query_builder.py    ICPProfile → apollo_query_config.json
│   │   ├── drift_detector.py          Diff current vs recommended rules → ICPDriftReport
│   │   ├── feedback_ingestor.py       Merge pipeline output CSVs with deal history
│   │   └── connectors/
│   │       ├── base.py                ICPDataConnectorBase (ABC)
│   │       ├── csv_connector.py       File-based connector (fully implemented)
│   │       ├── hubspot_connector.py   HubSpot connector (map_to_deal_record live; API stub)
│   │       └── salesforce_connector.py Salesforce connector (map_to_deal_record live; API stub)
│   ├── icp_intelligence_runner.py Stage 0 CLI entry point + orchestrator
│   ├── config/
│   │   └── settings.py            Env-driven settings (MOCK_MODE, API keys, ICP paths)
│   ├── schemas/                   Pydantic models: Company, Contact, Campaign, DealRecord, ICPProfile
│   ├── integrations/
│   │   ├── apollo/                mock_client.py + api_client.py
│   │   ├── clay/                  mock_client.py + api_client.py
│   │   ├── hubspot/               mock_client.py + api_client.py
│   │   ├── zerobounce/            mock_client.py + api_client.py
│   │   ├── neverbounce/           mock_client.py + api_client.py
│   │   └── validity/              mock_client.py + api_client.py
│   ├── crm/
│   │   ├── base.py                Abstract CRMProvider + SetupMode + result dataclasses
│   │   ├── setup_generator.py     Orchestrates CRM setup across providers
│   │   ├── config_loader.py       YAML config loader + client/CRM merge
│   │   ├── validation.py          Field conflict detection + gap analysis
│   │   ├── reporting.py           Writes setup_plan.json, setup_report.md, CSVs
│   │   ├── hubspot/
│   │   │   ├── client.py          HubSpot REST client (properties, pipelines, groups)
│   │   │   ├── setup.py           HubSpotSetupProvider (dry-run + live)
│   │   │   ├── sync.py            Company + contact upsert + association
│   │   │   ├── properties.py      Property payload builder + type mapping
│   │   │   ├── pipeline.py        Pipeline + stage payload builders
│   │   │   └── lifecycle.py       GTM lifecycle property definitions
│   │   └── salesforce/
│   │       └── setup.py           SalesforceSetupProvider (stub — live mode not yet implemented)
│   ├── utils/
│   │   ├── logger.py              get_logger() factory
│   │   └── retry.py               api_retry tenacity decorator
│   ├── ingestion/                 Company ingestion (Apollo)
│   ├── scoring/                   ICP scoring engine (internal — no external API)
│   ├── enrichment/                Clay enrichment
│   ├── validation/                ZeroBounce + NeverBounce email validation
│   ├── outreach/                  Sequence CSV export
│   ├── monitoring/                Campaign health monitoring (Validity)
│   └── main.py                    Pipeline orchestrator (Stage 0 + Stages 1–4)
├── tests/
│   ├── test_icp_scoring.py
│   ├── test_email_validation.py
│   ├── test_enrichment.py
│   ├── test_campaign_health.py
│   ├── test_ingestion.py
│   ├── test_hubspot_mapping.py
│   ├── test_pipeline_smoke.py
│   └── crm/
│       ├── test_hubspot_dry_run.py
│       ├── test_salesforce_dry_run.py
│       ├── test_config_loader.py
│       └── test_setup_generator.py
├── docs/
│   ├── ICP_INTELLIGENCE_GUIDE.md  Full walkthrough: quick start, data formats, report reading
│   └── DATA_FORMAT_REFERENCE.md   DealRecord/PipelineRecord/TAMRecord field reference + CRM mappings
├── demo.py                        Interactive step-by-step CLI demo
├── .env.example                   Environment variable template
├── requirements.txt
└── README.md
```

---

## What is not yet implemented

- Apollo, Clay, ZeroBounce, NeverBounce, Validity real API clients (stubs exist, method bodies are empty)
- HubSpot and Salesforce direct ICP data connectors (`pull_deals()` not yet implemented; use CSV export)
- Salesforce live mode (dry-run and inspect work; live requires SDK implementation)
- Database or persistent storage (all state is in CSV files per run)
- Scheduled / recurring pipeline runs
- Outreach / Instantly / Smartlead / HeyReach API enrollment (sequence CSVs are generated; API enrollment is a future step)
- Frontend or dashboard
- Docker / cloud deployment
- Multi-tenant support

---

## AI SDR layer (future)

The AI SDR activation layer sits on top of this pipeline and only operates on clean, scored data. Prerequisites for AI SDR activation:

- Company is Tier 1 or Tier 2 (ICP score threshold met)
- Contact `final_validation_status = approved`
- Contact persona matches the target ICP profile
- Domain `domain_health_score >= 70`
- Contact lifecycle stage is `Contact Validated`

The GTM pipeline is the data prerequisite. The AI SDR is the outreach activation on top of verified, enriched records.
