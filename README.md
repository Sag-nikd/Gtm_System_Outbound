# GTM System MVP

A local MVP simulation of a GTM operations system. It models company ingestion, ICP scoring, Clay-style enrichment, two-step email validation, HubSpot lifecycle mapping, outreach sequence export, and campaign health monitoring.

The Python layer acts as the integration orchestration engine — similar to how Zapier or n8n connect tools — but fully coded, versioned, and replaceable with real API integrations. Each stage is a discrete, testable Python module.

---

## What this system does

1. Ingests company firmographic data (fake JSON → later Apollo API)
2. Simulates Clay-style enrichment to surface engagement signals
3. Scores every company against a configurable ICP model
4. Assigns ICP tiers (Tier 1 / Tier 2 / Tier 3 / Disqualified)
5. Approves only Tier 1 and Tier 2 accounts for contact discovery
6. Loads contacts for approved accounts (fake JSON → later Apollo/Clay)
7. Runs two-step email validation (mock ZeroBounce + NeverBounce)
8. Assigns final validation status: approved / review / suppressed
9. Builds HubSpot-ready company and contact records with lifecycle stages
10. Exports email sequence files for Outreach / Instantly / Smartlead / HubSpot Sequences
11. Exports LinkedIn sequence files for HeyReach
12. Evaluates campaign health metrics and generates a recommended action report

Every step writes a checkpoint CSV to `outputs/` so you can inspect and debug each stage independently.

---

## Current MVP workflow

```
fake_companies.json
       ↓
[01] Apollo/Company Ingestion     → 01_apollo_company_ingestion.csv
       ↓
[02] Clay Enrichment              → 02_clay_enriched_accounts.csv
       ↓
[03] ICP Scoring                  → 03_icp_scored_accounts.csv
       ↓
[04] Tier Distribution            → 04_icp_tier_distribution.csv
       ↓
[05] Approved Accounts            → 05_approved_accounts_for_contact_discovery.csv
       ↓
fake_contacts.json (Tier 1 + 2 only)
       ↓
[06] Contact Discovery            → 06_discovered_contacts.csv
       ↓
[07] ZeroBounce Validation        → 07_zerobounce_validation.csv
       ↓
[08] NeverBounce Validation       → 08_neverbounce_validation.csv
       ↓
[09] Final Validation Decision    → 09_final_validated_contacts.csv
       ↓
[10] Approved Contacts            → 10_approved_contacts_for_hubspot_and_outreach.csv
       ↓
[11] HubSpot Companies            → 11_hubspot_companies.csv
[12] HubSpot Contacts             → 12_hubspot_contacts.csv
       ↓
[13] Email Sequence Export        → 13_email_sequence_export.csv
[14] LinkedIn Sequence Export     → 14_linkedin_sequence_export.csv
       ↓
fake_campaign_metrics.json
       ↓
[15] Campaign Metrics Input       → 15_campaign_metrics_input.csv
[16] Campaign Health Report       → 16_campaign_health_report.csv
```

---

## Future production workflow

```
Apollo API → Clay API → ICP Scoring → ZeroBounce + NeverBounce APIs
→ HubSpot Private App API → Outreach / Instantly / HeyReach APIs
→ Validity + sequencing platform data → Campaign health monitoring
```

---

## Folder structure

```
gtm-system/
├── data/
│   ├── fake_companies.json
│   ├── fake_contacts.json
│   └── fake_campaign_metrics.json
├── src/
│   ├── ingestion/company_ingestion.py
│   ├── scoring/icp_scoring.py
│   ├── enrichment/clay_mock_enrichment.py
│   ├── validation/email_validation_mock.py
│   ├── hubspot/hubspot_sync_mock.py
│   ├── outreach/sequence_export.py
│   ├── monitoring/campaign_health.py
│   └── main.py
├── config/
│   ├── icp_rules.json
│   └── lifecycle_mapping.json
├── outputs/          ← all 16 checkpoint CSV files land here
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

---

## How to run locally

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # macOS / Linux
venv\Scripts\activate             # Windows

# Install dependencies
pip install -r requirements.txt

# Run the full GTM pipeline
python src/main.py
```

---

## How to configure environment variables

Copy `.env.example` to `.env` and fill in your API keys when you are ready to connect real integrations:

```bash
cp .env.example .env
```

The `.env` file is in `.gitignore` — it will never be committed.

---

## Output files

All 16 checkpoint files are written to `outputs/`:

| # | File | Purpose |
|---|------|---------|
| 01 | `01_apollo_company_ingestion.csv` | Raw normalized firmographic data |
| 02 | `02_clay_enriched_accounts.csv` | Enrichment signals added |
| 03 | `03_icp_scored_accounts.csv` | Full score breakdown per company |
| 04 | `04_icp_tier_distribution.csv` | Tier distribution summary |
| 05 | `05_approved_accounts_for_contact_discovery.csv` | Tier 1 + 2 approved accounts |
| 06 | `06_discovered_contacts.csv` | Contacts for approved accounts |
| 07 | `07_zerobounce_validation.csv` | ZeroBounce first-pass results |
| 08 | `08_neverbounce_validation.csv` | NeverBounce second-pass results |
| 09 | `09_final_validated_contacts.csv` | Combined validation decision |
| 10 | `10_approved_contacts_for_hubspot_and_outreach.csv` | Clean approved contacts |
| 11 | `11_hubspot_companies.csv` | HubSpot-ready company import |
| 12 | `12_hubspot_contacts.csv` | HubSpot-ready contact import |
| 13 | `13_email_sequence_export.csv` | Email sequencer import |
| 14 | `14_linkedin_sequence_export.csv` | LinkedIn outreach import |
| 15 | `15_campaign_metrics_input.csv` | Raw campaign performance data |
| 16 | `16_campaign_health_report.csv` | Campaign health decisions |

CSV outputs are excluded from git via `.gitignore`.

---

## Future integrations

### Apollo
Replace `src/ingestion/company_ingestion.py` JSON loader with Apollo firmographic API to pull real company records by industry, employee count, and location filters.

### Clay
Replace `src/enrichment/clay_mock_enrichment.py` with Clay enrichment workflows, waterfall enrichment, and signal detection for tech stack, hiring, and growth triggers.

### ZeroBounce and NeverBounce
Replace the mock logic in `src/validation/email_validation_mock.py` with real API calls to ZeroBounce and NeverBounce for live deliverability checking.

### HubSpot
Replace the CSV outputs in `src/hubspot/hubspot_sync_mock.py` with HubSpot Private App API upsert calls for companies and contacts, including lifecycle stage updates.

### Outreach / Salesloft / Apollo Sequences / Instantly / Smartlead
Replace the email CSV in `src/outreach/sequence_export.py` with direct API enrollment into email sequences on your chosen sequencing platform.

### HeyReach
Replace the LinkedIn CSV in `src/outreach/sequence_export.py` with HeyReach API calls to enroll contacts into LinkedIn outreach campaigns.

### Validity
Replace `data/fake_campaign_metrics.json` with live Validity deliverability data and sequencing platform engagement metrics in `src/monitoring/campaign_health.py`.

---

## AI SDR future layer

The AI SDR layer should only activate after the GTM system has produced clean, validated data. The AI SDR must only operate on:

- Tier 1 and Tier 2 accounts (scored and enriched)
- Contacts with `final_validation_status = approved`
- Approved personas mapped to the correct ICP profile
- Domains with healthy deliverability scores (domain_health_score ≥ 70)
- Contacts at the correct lifecycle stage (Contact Validated → Ready for Outreach)

The GTM system is the prerequisite data pipeline. The AI SDR is the activation layer on top of clean data.

---

## GitHub upload steps

```bash
cd gtm-system
git init
git add .
git commit -m "Initial GTM system MVP"
git branch -M main
git remote add origin <your-github-repo-url>
git push -u origin main
```
