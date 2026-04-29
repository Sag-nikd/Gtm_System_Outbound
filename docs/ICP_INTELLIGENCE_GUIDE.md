# ICP Intelligence Engine — Walkthrough Guide

## Section 1: What This Does

The **ICP Intelligence Engine** (Stage 0) analyzes your historical deal data to discover who actually buys from you, then automatically configures the rest of the GTM pipeline to target more of those companies.

### The Data Flow

```
Your Deal History (CSV/JSON)
        ↓
  [Stage 0: ICP Intelligence]
  • Load & validate deal records
  • Analyze conversion patterns
  • Generate icp_rules.json
  • Build Apollo search filters
  • Detect drift from prior runs
        ↓
  config/icp_rules.json          ←── used by Stage 1 scoring
  config/apollo_query_config.json ←── used by Apollo client (live mode)
  outputs/00_icp_intelligence_report.json
  outputs/00_icp_summary.csv
        ↓
  [Stage 1: Company Pipeline]  → ICP scoring → Enrichment → Approval
        ↓
  [Stage 2: Contact Pipeline]  → Discovery → Email validation
        ↓
  [Stage 3: Activation Pipeline] → HubSpot sync → Sequences
        ↓
  [Stage 4: Campaign Monitoring] → Health reports
        ↓
  outputs/pipeline_outcomes.csv  ←── you fill this in after outreach
        ↑
  [Next run: Stage 0 reads outcomes → refines ICP]
```

### What Problem It Solves

Without this engine, you have to guess your ICP and hardcode it in `config/icp_rules.json`. The engine replaces that guess with data: it reads your deal history, calculates which industries/sizes/regions convert best, and generates a scoring config that reflects reality.

**Who it's for:** GTM engineers, RevOps teams, or founders running outbound at healthcare SaaS or health-plan-facing companies. The default configuration targets Medicaid MCOs and Health Plans, but the engine works for any B2B vertical.

---

## Section 2: Quick Start — Mock Mode (5-minute setup)

```bash
# 1. Clone and install
git clone https://github.com/Sag-nikd/Gtm_System_Outbound.git
cd gtm-system
pip install -r requirements.txt

# 2. Run ICP intelligence on mock deal history
python -m src.icp_intelligence_runner --deals data/icp_intelligence/mock_deal_history.json

# 3. Run the full pipeline (uses the generated icp_rules.json)
python -m src.main
```

### What You'll See

After running Stage 0, check these outputs:

| File | What It Tells You |
|------|-------------------|
| `outputs/00_icp_summary.csv` | One row per industry — conversion rate, deal count, index vs baseline |
| `outputs/00_icp_intelligence_report.json` | Full ICPProfile, drift report, Apollo config |
| `config/icp_rules.json` | Updated scoring weights and thresholds |
| `config/apollo_query_config.json` | Search filters for Apollo (live mode) |
| `config/icp_rules_recommended.json` | Recommended rules (when drift is major — for human review) |
| `config/icp_history/` | Timestamped backups of every prior `icp_rules.json` |

### How the Generated `icp_rules.json` Differs

The default `config/icp_rules.json` uses equal weights (25/25/15/15/10/10). The generated version derives weights from your actual win/loss data — if employee_count is the strongest predictor of conversion in your data, its weight goes up. Industries you've never won get `score: 0.0`; industries where you win at 2x the baseline get `score: 1.0`.

---

## Section 3: Using Your Own Data

### Minimum Viable Fields (required)

```json
{
  "company_name": "Centene Health Partners",
  "industry": "Managed Care",
  "employee_count": 3200,
  "deal_stage": "closed_won"
}
```

Deal stages the engine recognizes: `prospecting`, `contacted`, `meeting_booked`, `proposal_sent`, `negotiation`, `closed_won`, `closed_lost`, `disqualified`

### Full Field Set (optional but enriches the analysis)

```json
{
  "company_name": "Centene Health Partners",
  "domain": "centene.com",
  "industry": "Managed Care",
  "sub_industry": "Medicaid MCO",
  "employee_count": 3200,
  "revenue_range": "$1B+",
  "state": "Missouri",
  "country": "US",
  "medicaid_members": 850000,
  "medicare_members": 120000,
  "tech_stack": "Salesforce",
  "deal_stage": "closed_won",
  "deal_value": 150000,
  "deal_cycle_days": 62,
  "source_channel": "outbound_email",
  "contact_title": "VP Member Engagement",
  "contact_persona": "VP Member Engagement",
  "meeting_booked": true,
  "proposal_sent": true,
  "closed_date": "2025-09-15",
  "loss_reason": null
}
```

### Exporting from HubSpot (step-by-step)

1. In HubSpot, go to **CRM → Deals**
2. Click **Actions → Export** (top right)
3. Select these properties to include: Deal Name, Amount, Deal Stage, Close Date, Pipeline, Associated Company, Industry, Number of Employees, Lead Source
4. Export as **CSV**
5. Rename/map columns to match the DealRecord schema (see `docs/DATA_FORMAT_REFERENCE.md` for the mapping table)
6. Place the file at `data/your_deals.csv`
7. Run: `python -m src.icp_intelligence_runner --deals data/your_deals.csv`

### Exporting from Salesforce (step-by-step)

1. Go to **Reports → New Report**
2. Choose **Report Type: Opportunities**
3. Add columns: Opportunity Name, Amount, Stage, Close Date, Lead Source, Industry, Number of Employees, Website
4. Click **Run** → **Export** → **Export Details**
5. Map the `StageName` column to the deal stage taxonomy (see `DATA_FORMAT_REFERENCE.md`)
6. Use the `SalesforceICPConnector.map_to_deal_record()` method or export and rename manually

### Exporting from a Spreadsheet

Copy these column headers into your CSV:
```
company_name,domain,industry,employee_count,deal_stage,deal_value,deal_cycle_days,state,medicaid_members,medicare_members,tech_stack,contact_persona,source_channel,closed_date,loss_reason
```

### Configuring the Path

In `.env` or your environment:
```bash
ICP_DEAL_DATA_PATH=data/my_company_deals.csv
ICP_PIPELINE_DATA_PATH=data/my_pipeline.json   # optional
ICP_TAM_DATA_PATH=data/my_tam.json             # optional
```

---

## Section 4: Understanding the ICP Report

### `00_icp_intelligence_report.json` Structure

**`profile.conversion_rate`** — Your overall closed_won / (closed_won + closed_lost + disqualified). This is the baseline for all index calculations.

**`profile.industry_breakdown`** — Each industry segment shows:
- `deal_count`: total deals attempted
- `win_count`: closed_won deals
- `conversion_rate`: win_count / (win_count + loss_count)
- `index`: conversion_rate / overall_conversion_rate — values > 1.0 mean this industry converts above baseline; < 1.0 means below

**`profile.confidence_level`** — `"low"` (<10 total deals), `"medium"` (10–30), `"high"` (>30). Low confidence = don't auto-update rules.

**`profile.icp_summary`** — One-paragraph plain-English description: "Your strongest ICP is Managed Care organizations with 2000–9999 employees."

### Reading the Drift Report

| `drift_severity` | Meaning | Action |
|-----------------|---------|--------|
| `none` | No significant changes | No action needed |
| `minor` | 1–2 dimensions shifted | Auto-updated if `confidence_level=high`, else review `icp_rules_recommended.json` |
| `major` | 3+ dimensions shifted | Human review required — check `icp_rules_recommended.json` |
| `critical` | Top industry score changed | Immediate review — targeting has fundamentally shifted |

**`should_auto_update`** — `true` only when `drift_severity=minor` AND `confidence_level=high`. In all other cases, the recommended rules are saved for human review.

### Reading the Apollo Query Config

`config/apollo_query_config.json` contains:
- `organization_search.industry_keywords` — industries to target (above-baseline converters)
- `organization_search.employee_ranges` — sweet spot ±1 band around top-converting size
- `organization_search.technology_names` — tech stacks seen in closed-won deals
- `exclusions.domains` — existing customer domains (don't re-prospect)
- `exclusions.industries` — industries with 0% conversion and >3 attempts

---

## Section 5: Running the Full Pipeline

### Enable Stage 0

Set in `.env`:
```bash
ICP_INTELLIGENCE_ENABLED=true
ICP_DEAL_DATA_PATH=data/icp_intelligence/mock_deal_history.json
```

Then run:
```bash
python -m src.main
```

The pipeline will:
1. Run Stage 0 → generate/update `config/icp_rules.json`
2. Run Stage 1 using the new rules
3. Continue through Stages 2–4 as normal
4. Write `run_manifest.json` with `icp_intelligence` as the first stage entry

### The Feedback Loop

After a pipeline run, your outreach is sent. Over the next few weeks, you'll learn which contacts replied, booked meetings, or became customers. Feed that back in:

1. Create `data/pipeline_outcomes.csv` with columns: `email, company_name, domain, outcome, outcome_date`
2. Valid outcomes: `replied`, `meeting_booked`, `proposal_sent`, `closed_won`, `closed_lost`, `no_response`
3. Enable feedback: `ICP_FEEDBACK_ENABLED=true`
4. Run again — Stage 0 merges outcomes with your deal history

**Feedback loop diagram:**
```
Run ICP Intelligence → Run Pipeline → Send Outreach
         ↑                                   ↓
         └── Collect Outcomes ← Track Results ←┘
              (pipeline_outcomes.csv)
```

---

## Section 6: Connecting Live CRM Data

### HubSpot Direct (future)

```bash
ICP_DATA_SOURCE=hubspot
HUBSPOT_PRIVATE_APP_TOKEN=your_token_here
```

`HubSpotICPConnector.pull_deals()` will be implemented in a future release. Today, use the CSV export path described in Section 3.

### Salesforce Direct (future)

```bash
ICP_DATA_SOURCE=salesforce
SF_USERNAME=user@company.com
SF_PASSWORD=password
SF_SECURITY_TOKEN=token
```

`SalesforceICPConnector.pull_deals()` will be implemented in a future release.

### Required Permissions

**HubSpot:** CRM → Deals (read), CRM → Companies (read), Reports (read)

**Salesforce:** Opportunity (read), Account (read), Report (run)

### Scheduling Automated ICP Refresh

Use cron (Linux/Mac) or Task Scheduler (Windows) to run Stage 0 monthly:
```bash
# Monthly ICP refresh — runs first of each month at 6am
0 6 1 * * cd /path/to/gtm-system && python -m src.icp_intelligence_runner \
  --deals data/my_deals.csv --feedback-dir outputs/
```

---

## Section 7: Customization

### Adding a New Industry to Scoring

1. Open `config/icp_rules.json`
2. Add an entry under `industry_scores`: `"Veterinary Care": 0.3`
3. The scoring engine will apply this score the next time it runs
4. OR: add deals for that industry to your deal history and let the ICP engine generate the score automatically

### Changing Tier Boundaries

Edit `config/icp_rules.json` under `tiers`:
```json
"tiers": {
  "tier_1": { "min": 85, "max": 100, "label": "Tier 1" },
  ...
}
```

### Adding a New Data Connector

1. Create `src/icp_intelligence/connectors/your_connector.py`
2. Inherit from `ICPDataConnectorBase`
3. Implement all 5 abstract methods: `connect()`, `pull_deals()`, `pull_pipeline()`, `pull_companies()`, `map_to_deal_record()`
4. Add `ICP_DATA_SOURCE=your_connector` handling in `src/icp_intelligence_runner.py`

### Adapting for Non-Healthcare Verticals

The ICP engine is industry-agnostic. To adapt:
1. Remove `medicaid_members` / `medicare_members` from your deal data (optional fields — the engine skips member volume breakdown if they're absent)
2. Update `config/icp_rules.json` with your actual industry names
3. Update `src/outreach/sequence_export.py` `EMAIL_ANGLES` with your personas
4. Update `src/enrichment/clay_mock_enrichment.py` `PERSONA_MAP` with your target titles
