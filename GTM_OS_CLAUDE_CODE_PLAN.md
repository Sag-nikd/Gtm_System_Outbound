# GTM-OS — Claude Code Execution Plan

**Repo:** `Sag-nikd/Gtm_System_Outbound`
**Builder:** Claude Code (autonomous)
**Human role:** Pre-flight prep, soak-testing between batches, prompt evaluation in Batch H
**End state:** A GTM engineer downloads, plugs in API keys, ships their first real outbound campaign within 1 hour. The system also ingests their Gong calls, exec meetings, CPO docs, and CRM events; extracts pains, objections, and strategic initiatives; delivers a daily Slack digest of "what to focus on today" to every rep; and gets smarter every week via feedback loops.

---

## How to use this document

This is a **batched execution plan**, not a story-by-story backlog. Each batch is sized to be **one Claude Code session** (autonomous run of 1-3 hours). Architecture decisions are pre-locked so Claude Code never has to ask.

**Workflow:**
1. Do the **T-minus prep** (Section 1) once, before any code. This unblocks Claude Code from vendor-signup walls.
2. Open Claude Code in the repo, paste the **kickoff prompt for Batch A** (Section 4.A).
3. Let it run. Claude Code commits, tests, and reports back.
4. Run the **soak test** for Batch A (Section 5.A). Eyeball, confirm, move on.
5. Repeat for Batches B → J.
6. After Batch H, do the **prompt evaluation protocol** (Section 6). This is the only batch with mandatory human iteration.
7. Cut v1.0.0 release. Ship.

**Total wall clock:** ~2-3 weeks gated by (a) vendor account approvals (Gong API access is longest), (b) your prompt evaluation in Batch H, (c) your soak-test time between batches.

**Total Claude Code autonomous time:** ~20-30 hours across 10 sessions.
**Total human time:** ~15-20 hours, mostly in T-minus prep + Batch H prompt evaluation.

---

## Section 1 — T-minus prep checklist (do this first)

Claude Code cannot create vendor accounts, click through 2FA, or wait for sales emails. Start every signup in parallel **today** so the keys are ready when Batch B begins.

### 1.1 Vendor accounts (start in parallel, ordered by lead time)

| Service | Why | Lead time | What to do |
|---|---|---|---|
| **Gong** | Call transcript ingestion | **5-10 business days** (longest pole) | Email Gong CSM or sales: request API access for an integration build. Get a Bearer token + workspace ID. |
| **Apollo.io** | Company + contact sourcing | Same day | Free trial → Settings → Integrations → API. Save key as `APOLLO_API_KEY`. |
| **HubSpot** | CRM | Same day | Create developer test portal → Private Apps → create app with `crm.objects.companies.write`, `crm.objects.contacts.write`, `crm.schemas.companies.write`, `crm.schemas.contacts.write`, `oauth` scopes. Save token as `HUBSPOT_PRIVATE_APP_TOKEN`. |
| **Instantly** | Sequencer | Same day | Sign up → API & Webhooks → generate v2 API key. Save as `INSTANTLY_API_KEY`. Create one empty test campaign and save its ID as `INSTANTLY_TEST_CAMPAIGN_ID`. |
| **ZeroBounce** | Email validation | Same day | Sign up → 100 free credits → API key. Save as `ZEROBOUNCE_API_KEY`. |
| **Anthropic API** | LLM (extraction, classification, digest generation) | Same day | console.anthropic.com → API keys. Save as `ANTHROPIC_API_KEY`. |
| **Voyage AI** | Embeddings (Anthropic-recommended) | Same day | voyageai.com → API key. Save as `VOYAGE_API_KEY`. |
| **Granola** | Non-Gong meeting notes | Same day | Settings → API. Save as `GRANOLA_API_KEY`. (Optional for v1; defer if you don't use Granola.) |
| **Notion** | Strategic doc ingestion | Same day | Notion → Integrations → create internal integration → share specific pages with it. Save as `NOTION_API_KEY` + `NOTION_ROOT_PAGE_IDS`. |
| **Slack** | Daily digest delivery | Same day | api.slack.com/apps → Create new app → bot token scopes: `chat:write`, `im:write`, `users:read.email`. Install to workspace. Save bot token as `SLACK_BOT_TOKEN`. |
| **SendGrid** | Email delivery (digest fallback) | Same day | Free tier (100 emails/day). API key with Mail Send permission. Save as `SENDGRID_API_KEY`. Verify sender domain. |
| **ngrok** | Webhook receiver public URL (dev) | Same day | Free account → auth token. Save locally; not needed in production. |
| **Fly.io** | Webhook receiver public URL (prod) | Same day | Free tier. Install `flyctl`, run `fly auth signup`. |
| **GitHub** (already have) | CI/CD + Docker registry (GHCR) | — | Make sure repo has Actions enabled. Generate PAT with `write:packages` if needed. |

### 1.2 Sample data for prompt evaluation (Batch H)

Without real signal data, extraction prompts can't be evaluated. Collect before Batch H:

- **20-30 Gong call transcripts** (export as text from Gong UI; redact if needed)
- **5-10 exec meeting notes** (from Granola, Otter, or hand-copied)
- **3-5 CPO/strategic docs** (your own or your company's recent ones; redact)
- **5-10 closed-won + 5-10 closed-lost HubSpot deal histories** (export with all activities)

Save these to `data/eval/` in the repo (gitignored). They'll be used as the prompt evaluation harness in Batch H.

### 1.3 Local environment

- **Python 3.11+** installed (Claude Code will assume this)
- **Docker Desktop** installed and running
- **Claude Code** authenticated and pointed at the repo root
- **A clean working branch** (`git checkout -b claude-code-build`) so Claude Code can commit freely
- An `.env.local` file at repo root, pre-populated with all keys from Section 1.1 (Claude Code reads this; never commit it)

---

## Section 2 — Locked architecture decisions

These are pre-decided. Claude Code does not deliberate on them.

### 2.1 Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Already in repo |
| Async | async-first throughout (`asyncio`, `httpx`, async SQLAlchemy) | Modern Python; webhook receiver demands it; no point mixing |
| ORM | SQLAlchemy 2.0 (async) | Industry standard; first-class async |
| Migrations | Alembic | Standard with SQLAlchemy |
| Database (v1) | SQLite via `aiosqlite` | Zero ops, local-first, fits "download and run" model |
| Database (v2 path) | Postgres via `asyncpg` | Same SQLAlchemy code works; swap connection string |
| HTTP client | `httpx` (async) | Modern, async-native |
| Validation | Pydantic v2 | Already in repo |
| Settings | `pydantic-settings` | Native Pydantic env var loading |
| CLI framework | Typer | Cleaner than Click for type-hinted commands |
| Web framework | FastAPI | Native Pydantic; async; the only sane choice with this stack |
| Logging | `structlog` (JSON output) | Structured, queryable |
| Testing | `pytest` + `pytest-asyncio` + `vcrpy` | Standard; vcrpy records real API responses for replay |
| Linting | `ruff` | Replaces black + flake8 + isort + pyupgrade |
| Type checking | `mypy --strict` on `src/` | Catches schema drift early |
| LLM SDK | `anthropic` + `openai` packages | Direct, no LangChain |
| Vector store | `sqlite-vec` extension | Local-first, zero ops, fits the SQLite story |
| Embeddings | Voyage `voyage-3-large` | Anthropic-recommended; good quality |
| Process scheduler | GitHub Actions cron for nightly jobs; APScheduler for in-process | No need for Airflow/Prefect at this scale |
| Containerization | Docker + docker-compose | Standard |
| Webhook public URL (dev) | ngrok | Standard |
| Webhook public URL (prod) | Fly.io with shipped `fly.toml` | Easiest one-click prod deploy |

### 2.2 Repository conventions

- **Async everywhere.** No sync DB calls, no sync HTTP, no `requests`.
- **All vendor clients have mock + api variants** behind the same interface (existing pattern; preserve it).
- **All API client methods use the `@track_vendor_call` decorator** for cost logging.
- **All public methods on services have type hints; mypy --strict must pass.**
- **All new tables go through Alembic migration**; no `create_all()`.
- **All LLM calls go through `src/llm/client.py`**; never `import anthropic` outside that module.
- **All prompts live in `src/llm/prompts/<name>.md`** with YAML front-matter; never inline strings.
- **Logging: `log = structlog.get_logger(__name__)` at top of every module.** Never `print`. Never `logging` directly.
- **Errors: domain errors in `src/errors.py` (one class per failure mode), raised loudly, caught only at CLI/webhook boundary.**
- **CLI is the only user-facing surface for v1.** No web UI. (Streamlit dashboard is optional, in Batch I.)
- **Single-tenant only.** No multi-tenancy in v1. One install = one company.

### 2.3 Vendor scope (v1)

| Category | v1 ships | v2/later |
|---|---|---|
| Sourcing | Apollo | ZoomInfo, Clay |
| Enrichment | Apollo's built-in | Clay waterfall |
| Email validation | ZeroBounce | NeverBounce second pass |
| CRM | HubSpot | Salesforce |
| Sequencer | Instantly | Smartlead, Outreach, HeyReach |
| Deliverability | Defer | Validity |
| Calls | Gong | Chorus, Wingman |
| Meetings | Granola | Fireflies, Otter |
| Docs | Notion | Confluence, Google Drive |
| Inbox | Instantly replies (via webhook) | Gmail/Outlook direct |

**v1 = one provider per category. Ship narrow, deep, working.**

### 2.4 Database identity rules

- **Company stable key:** `lower(domain)`. No domain → reject at ingestion.
- **Contact stable key:** `lower(email)`. No email → store but exclude from outreach until enriched.
- **Signal stable key:** `(source_type, source_id)`. Source ID is the vendor's ID (Gong call ID, HubSpot event ID, etc.).
- **All foreign keys use UUID `id` columns** generated client-side (`uuid.uuid4`).
- **Soft delete via `deleted_at` column**, never hard delete.

### 2.5 LLM model routing (locked)

Defined in `config/llm_routing.yaml`:

| Task | Model | Why |
|---|---|---|
| Pain extraction from calls | `claude-sonnet-4-5` | Long context, nuanced extraction |
| Objection/competitor classification | `claude-haiku-4-5` | Cheap, fast, structured output |
| Persona signal detection | `claude-haiku-4-5` | Fast, structured |
| Strategic initiative detection | `claude-sonnet-4-5` | Reasoning-heavy |
| Win/loss synthesis | `claude-sonnet-4-5` | Long context, multi-source |
| Daily digest generation | `claude-sonnet-4-5` | Quality over cost; few digests/day |
| Personalized opener generation | `claude-haiku-4-5` | Volume; cost matters |
| Embeddings | `voyage-3-large` | Anthropic-recommended |

---

## Section 3 — Master kickoff prompt (paste this first)

Before starting any batch, paste this once to set Claude Code's context for the whole project:

```
You are building GTM-OS, an outbound + GTM intelligence operating system,
in the repo Sag-nikd/Gtm_System_Outbound. The full execution plan lives in
GTM_OS_CLAUDE_CODE_PLAN.md at the repo root.

Working agreements:
1. Read GTM_OS_CLAUDE_CODE_PLAN.md Section 2 (Locked architecture
   decisions) before writing any code. Never deviate from those choices.
2. Work on one Batch at a time. Do not start the next Batch.
3. After each Batch: run all tests, run mypy --strict, run ruff, commit
   on the current branch with message "Batch <X>: <summary>". Do not push
   without explicit instruction.
4. If you hit an architectural decision not covered in Section 2, pick the
   simpler option, document the choice in docs/decisions/ADR-<n>.md, and
   continue.
5. If you hit a missing API key, stop and tell me which key is missing and
   where to put it. Do not stub or fake.
6. Every new module gets a docstring, type hints, structlog logger, and
   tests.
7. Output a "Batch <X> complete" summary at the end with: files created,
   tests added, manual verification steps for the human.

Confirm you've read Section 2 and understand the working agreements.
```

After Claude Code confirms, paste the kickoff prompt for the current Batch (Sections 4.A through 4.J).

---

## Section 4 — Batches

### Batch A — Foundation (state, DB, CLI shell, observability)

**Scope:** SQLite + Alembic + async SQLAlchemy models, settings via pydantic-settings, Typer CLI shell with subcommands stubbed, structlog logging, cost-tracking decorator + `vendor_calls` table, repository pattern.

**No external integrations yet.** This is pure infrastructure.

**Dependencies:** None.

**Files Claude Code creates/modifies:**
```
pyproject.toml
alembic.ini
src/db/migrations/env.py
src/db/migrations/versions/0001_initial.py
src/db/models/base.py
src/db/models/companies.py
src/db/models/contacts.py
src/db/models/runs.py
src/db/models/vendor_calls.py
src/db/session.py
src/db/repository/base.py
src/db/repository/companies.py
src/db/repository/contacts.py
src/db/repository/runs.py
src/config/settings.py
src/cost/tracker.py
src/cli/app.py
src/cli/db.py
src/cli/runs.py
src/cli/cost.py
src/logging.py
src/errors.py
config/vendor_pricing.yaml
tests/db/test_models.py
tests/db/test_repository.py
tests/cost/test_tracker.py
tests/cli/test_db_commands.py
```

**Kickoff prompt for Batch A:**

```
Execute Batch A from GTM_OS_CLAUDE_CODE_PLAN.md Section 4.A.

Setup:
- Use Python 3.11+, async SQLAlchemy 2.0, Alembic, Typer, pydantic-settings, structlog
- Database is SQLite at data/gtm_os.db via aiosqlite
- All ORM access goes through async sessions; no sync calls
- Set up pyproject.toml with all dev deps (pytest, pytest-asyncio, vcrpy, ruff, mypy, alembic)
- Add a Makefile with targets: install, test, lint, typecheck, db-migrate, db-reset

Models for this batch:
- Company (id UUID, domain unique-lower, name, country, employee_count, revenue_band, industry, source, created_at, updated_at, deleted_at)
- Contact (id UUID, email unique-lower, company_id FK, first_name, last_name, title, persona, linkedin_url, created_at, updated_at, deleted_at)
- PipelineRun (id UUID, started_at, completed_at, status enum, config_snapshot JSON, summary JSON)
- RunEvent (id, run_id FK, stage, event_type, payload JSON, created_at)
- VendorCall (id, run_id FK nullable, vendor enum, endpoint, units_consumed, credit_cost float, dollar_cost float, success bool, error_message, called_at, latency_ms)

Cost tracker:
- @track_vendor_call(vendor, endpoint, unit_calculator) decorator
- Reads pricing from config/vendor_pricing.yaml
- Logs to vendor_calls table; never blocks main flow on logging failure

CLI:
- gtm db init           # creates db file, runs all migrations
- gtm db migrate        # alembic upgrade head
- gtm db status         # show migration version + row counts per table
- gtm db reset          # drops file, re-inits (with --yes guard)
- gtm runs list --limit 20
- gtm runs show <run_id>
- gtm cost summary [--run-id]
- gtm cost forecast --contacts 5000

Verification I'll run after:
- make install && make db-migrate
- gtm db status
- pytest -v
- mypy --strict src/
- ruff check src/

Begin.
```

---

### Batch B — Outbound integrations (real API clients)

**Scope:** Real `api_client.py` for Apollo, ZeroBounce, Instantly. Verify and extend HubSpot real client. All wrapped in `@track_vendor_call`. All using `vcrpy` cassettes for tests.

**Dependencies:** Batch A complete.

**Files:**
```
src/integrations/apollo/api_client.py
src/integrations/apollo/schemas.py
src/integrations/apollo/mappers.py
src/integrations/zerobounce/api_client.py
src/integrations/zerobounce/schemas.py
src/integrations/instantly/__init__.py
src/integrations/instantly/mock_client.py
src/integrations/instantly/api_client.py
src/integrations/instantly/schemas.py
src/integrations/hubspot/api_client.py
src/integrations/base.py
config/vendor_pricing.yaml
tests/integrations/cassettes/
tests/integrations/test_apollo.py
tests/integrations/test_zerobounce.py
tests/integrations/test_instantly.py
```

**Kickoff prompt for Batch B:**

```
Execute Batch B from GTM_OS_CLAUDE_CODE_PLAN.md Section 4.B.

Required env vars: APOLLO_API_KEY, ZEROBOUNCE_API_KEY, INSTANTLY_API_KEY,
INSTANTLY_TEST_CAMPAIGN_ID, HUBSPOT_PRIVATE_APP_TOKEN

For each vendor, implement async api_client.py with:
- All methods async, using httpx.AsyncClient with a 30s timeout
- Tier-based rate limiting via tenacity (exponential backoff on 429, max 5 retries)
- Pagination handled internally; methods return lists or async generators
- All public methods wrapped with @track_vendor_call
- Pydantic schemas for vendor request/response shapes (in schemas.py)
- Mappers translating vendor schemas to internal Company/Contact models
- Failures raise specific errors from src/errors.py

Apollo (api.apollo.io/v1):
- search_companies(filters) -> AsyncIterator[Company]
- search_contacts(company_id, persona_filters) -> AsyncIterator[Contact]
- enrich_company(domain) -> Company
- enrich_contact(email) -> Contact

ZeroBounce (api.zerobounce.net):
- validate_email(email) -> ValidationResult
- validate_batch(emails) -> List[ValidationResult]
- ValidationResult.status: valid, risky, invalid

Instantly (api.instantly.ai/api/v2):
- list_campaigns() -> List[Campaign]
- get_campaign(campaign_id) -> Campaign
- add_leads_to_campaign(campaign_id, leads) -> AddLeadsResult (batch 100)
- get_campaign_analytics(campaign_id) -> CampaignAnalytics

Tests use vcrpy. Filter authorization headers from cassettes.

Begin.
```

---

### Batch C — Pipeline orchestration + safety

**Scope:** Suppression list system, idempotent pipeline runs, end-to-end orchestrator.

**Dependencies:** Batches A, B.

**Files:**
```
src/db/migrations/versions/0002_suppression.py
src/db/migrations/versions/0003_pipeline_state.py
src/db/models/suppression.py
src/db/repository/suppression.py
src/suppression/service.py
src/cli/suppression.py
src/pipeline/orchestrator.py
src/pipeline/stages/01_ingest.py ... 09_export_linkedin.py
src/cli/pipeline.py
tests/suppression/
tests/pipeline/
```

**Kickoff prompt for Batch C:**

```
Execute Batch C from GTM_OS_CLAUDE_CODE_PLAN.md Section 4.C.

Suppression list:
- Table: suppression_list(id, email lower, domain lower nullable, reason enum,
  source, run_id nullable, added_at, notes)
- Reasons: customer, competitor, bounce, unsubscribe, manual, replied_negative, do_not_contact
- Domain entries block entire domain
- CLI: gtm suppress add, import, export, check, list

Pipeline orchestrator:
- One file per stage; each exposes async def run(run_id, ctx) -> StageResult
- PipelineContext carries: settings, db session factory, logger, run_id
- Each stage reads from DB, writes to DB, emits run_events, writes legacy CSV
- Idempotency: upsert by lower(domain) / lower(email)
- CLI: gtm pipeline run, dry-run, status

Tests:
- Two runs with same mock data → second inserts 0 contacts
- Suppressed email → excluded at stage 8

Begin.
```

---

### Batch D — Webhook receiver + auto-suppression

**Scope:** FastAPI webhook server for Instantly + HubSpot events.

**Dependencies:** Batches A, B, C.

**Files:**
```
src/db/migrations/versions/0004_engagement_events.py
src/db/models/engagement_events.py
src/webhooks/server.py
src/webhooks/auth.py
src/webhooks/handlers/instantly.py
src/webhooks/handlers/hubspot.py
src/cli/webhooks.py
docker/webhooks.Dockerfile
fly.toml
tests/webhooks/
docs/webhooks.md
```

**Kickoff prompt for Batch D:**

```
Execute Batch D from GTM_OS_CLAUDE_CODE_PLAN.md Section 4.D.

FastAPI app:
- POST /webhooks/instantly, POST /webhooks/hubspot, GET /health
- Signature verification middleware
- engagement_events table with external_event_id for idempotency

InstantlyHandler: bounced→suppression, unsubscribed→suppression, others→store
HubSpotHandler: lifecycle/deal/engagement events→store

CLI: gtm webhooks serve, test
Docker: docker/webhooks.Dockerfile + docker-compose.yml webhooks service
Fly.io: fly.toml shipped in repo root

Tests:
- Bad signature → 401
- Duplicate event → 200 no double-write
- Bounce → suppression row created

Begin.
```

---

### Batch E — Onboarding wizard, Docker, CI, release

**Scope:** `gtm init` wizard, Dockerfile, docker-compose, CI/CD, README rewrite, v0.1.0 tag.

**Dependencies:** Batches A-D.

**Files:**
```
src/cli/init.py
config/templates/{saas,healthcare,fintech,b2b_marketplace,manufacturing}.yaml
Dockerfile
docker-compose.yml
.github/workflows/ci.yml
.github/workflows/docker-publish.yml
.github/workflows/release.yml
QUICKSTART.md
README.md (rewrite)
samples/ (committed redacted CSVs)
CHANGELOG.md
```

**Kickoff prompt for Batch E:**

```
Execute Batch E from GTM_OS_CLAUDE_CODE_PLAN.md Section 4.E.

gtm init wizard: Typer prompts, idempotent, generates .env.local +
config/icp_rules.json from chosen template + lifecycle_mapping.json +
hubspot setup yaml.

Industry templates: saas, healthcare, fintech, b2b_marketplace, manufacturing
- Each has opinionated, well-commented scoring_rules, tier_thresholds,
  persona_definitions, sample_filters

Dockerfile: multi-stage, python:3.11-slim, non-root, entrypoint gtm
docker-compose.yml: gtm + webhooks services, shared volumes

CI: ruff → mypy → pytest with coverage → codecov badge
Docker publish: GHCR on tag v*.*.*
Release: auto release notes from commits

README: tagline → problem → one-command demo → Mermaid pipeline diagram →
badges → QUICKSTART link → architecture link

Bump version to 0.1.0 in pyproject.toml. git tag v0.1.0 (do not push).

Begin.
```

---

### Batch F — Intelligence foundation (LLM, vector, signal schema)

**Scope:** LLM client wrapper, prompt registry, sqlite-vec vector store, signal schema.

**Dependencies:** Batches A-E.

**Files:**
```
src/llm/client.py
src/llm/providers/anthropic.py
src/llm/providers/openai.py
src/llm/prompts/registry.py
config/llm_routing.yaml
src/vector/store.py
src/vector/embedder.py
src/db/migrations/versions/0005_signals_and_vectors.py
src/db/models/signals.py
src/db/models/vector_index.py
src/db/repository/signals.py
src/signals/service.py
src/cli/signals.py
src/cli/llm.py
tests/llm/
tests/vector/
tests/signals/
```

**Kickoff prompt for Batch F:**

```
Execute Batch F from GTM_OS_CLAUDE_CODE_PLAN.md Section 4.F.

Required env vars: ANTHROPIC_API_KEY, VOYAGE_API_KEY

LLM client: route by task → config/llm_routing.yaml → provider/model/temp
Prompt registry: .md files with YAML front-matter, Jinja vars, output JSON schema validation
Vector store: sqlite-vec, Voyage voyage-3-large embeddings, search with metadata filters
Signals: source_types (gong_call, meeting_note, crm_event, email_reply, strategic_doc,
  product_content, roi_model), upsert idempotent on (source_type, source_id),
  auto-link to company by email domain

CLI: gtm signals list/show/search/embed, gtm llm test/prompts

Begin.
```

---

### Batch G — Signal ingestion (all 6 sources)

**Scope:** Real ingestion clients for Gong, Granola, Notion, web crawler, HubSpot CRM events, email replies.

**Dependencies:** Batches D, F.

**Files:**
```
src/signals/ingestion/gong/client.py + mapper.py
src/signals/ingestion/granola/client.py + mapper.py
src/signals/ingestion/notion/client.py + mapper.py
src/signals/ingestion/web/crawler.py + extractor.py
config/content_sources.yaml
src/signals/ingestion/hubspot_events.py
src/signals/ingestion/instantly_replies.py
.github/workflows/ingest-cron.yml.example
tests/signals/ingestion/
```

**Kickoff prompt for Batch G:**

```
Execute Batch G from GTM_OS_CLAUDE_CODE_PLAN.md Section 4.G.

Required env vars: GONG_ACCESS_KEY, GONG_ACCESS_KEY_SECRET, NOTION_API_KEY,
NOTION_ROOT_PAGE_IDS. GRANOLA_API_KEY (optional).

Each Ingester: async ingest(since, until) -> IngestResult
Reads last_synced_at from sync_state table; upserts via SignalService.

Gong: /v2/calls + /v2/calls/transcript → gong_call signals, auto-link by participant domains
Granola: list notes → meeting_note signals
Notion: recursive page walk + notion-to-md → strategic_doc signals
Web: httpx + trafilatura + robots.txt + content hash → product_content signals
HubSpot backfill: historical deal/contact engagement → crm_event signals
Instantly replies: extend Batch D handler → email_reply signals

CLI: gtm signals ingest {gong,granola,notion,content,crm,all}

Begin.
```

---

### Batch H — Signal processing (LLM extractors)

**Scope:** Pain extractor, objection/competitor classifier, persona detector, initiative detector, win/loss synthesizer. Eval harness.

**Dependencies:** Batches F, G.

**Files:**
```
src/signals/processing/pain_extractor.py
src/signals/processing/mention_classifier.py
src/signals/processing/persona_detector.py
src/signals/processing/initiative_detector.py
src/signals/processing/winloss_synthesizer.py
src/signals/processing/runner.py
src/llm/prompts/pain_extraction.md
src/llm/prompts/objection_classification.md
src/llm/prompts/persona_detection.md
src/llm/prompts/initiative_detection.md
src/llm/prompts/winloss_synthesis.md
config/pain_taxonomy.yaml
config/objection_taxonomy.yaml
config/competitors.yaml
src/db/migrations/versions/0006_extracted.py
src/db/models/{extracted_pains,extracted_mentions,strategic_initiatives,winloss_analyses}.py
src/cli/{intel,process}.py
eval/eval_runner.py
eval/cases/
eval/rubric.md
tests/signals/processing/
```

**Kickoff prompt for Batch H:**

```
Execute Batch H from GTM_OS_CLAUDE_CODE_PLAN.md Section 4.H.

Each Processor: async process(signal) -> ProcessingResult, writes to denormalized table.

Pain extractor: gong_call/meeting_note/email_reply → extracted_pains
  (pain_category from taxonomy, pain_text, confidence, supporting_quote)
Mention classifier: objections (from taxonomy) + competitors (from config)
  → extracted_mentions
Persona detector: updates contacts.persona_signals if confidence > 0.7
Initiative detector: strategic_doc/meeting_note with exec participants
  → strategic_initiatives
Win/loss synthesizer: triggered by deal closed event, multi-signal synthesis
  → winloss_analyses

Runner: gtm process run [--processor] [--limit] [--since]
  Processes pending signals; idempotent on signal_id + prompt version

Eval harness: eval/eval_runner.py, cases/<processor>/<case_id>.yaml,
  gtm eval run <processor> → scorecard

Begin.
```

---

### Batch I — Daily focus + Slack delivery

**Scope:** Account focus scoring, daily digest generator, Slack/SendGrid delivery, user management.

**Dependencies:** Batches F, G, H.

**Files:**
```
src/db/migrations/versions/0007_users_and_focus.py
src/db/models/{users,daily_digests,focus_scores}.py
src/focus/account_scorer.py
src/focus/digest_generator.py
src/focus/delivery/{slack,sendgrid,file}.py
src/llm/prompts/daily_digest.md
config/focus_rules.yaml
src/cli/{users,digest,focus}.py
src/dashboard/app.py  (optional Streamlit)
.github/workflows/digest-cron.yml.example
tests/focus/
```

**Kickoff prompt for Batch I:**

```
Execute Batch I from GTM_OS_CLAUDE_CODE_PLAN.md Section 4.I.

Required env vars: SLACK_BOT_TOKEN, SENDGRID_API_KEY, SENDGRID_FROM_EMAIL

Users: table with email, slack_user_id, timezone, digest_channel, digest_time_local,
  accounts_owned (list of domains or "all")

Account focus scorer: nightly recompute of focus_score for every owned account.
  Score = weighted combination of:
  - recency of pain signals (decay over time)
  - initiative alignment (does their strategic doc align with your pitch?)
  - engagement signals (recent opens, replies)
  - deal velocity (days in stage, last activity)
  - win pattern match (similarity to closed-won ICP)
  Writes to focus_scores(account_id, user_id, score, score_breakdown JSON, scored_at)

Digest generator: for each user, pulls their top 10 accounts by focus_score,
  generates narrative via daily_digest.md prompt explaining WHY each account
  is hot today, includes top pain signals and suggested next action

Delivery: Slack DM via bot token, SendGrid HTML email, file fallback
  Idempotent: one digest per user per UTC day

CLI:
- gtm users add/list/remove/set-pref
- gtm digest generate [--user] [--date]
- gtm digest preview [--user]    (to stdout)
- gtm digest send [--user] [--dry-run]
- gtm focus recompute [--account]
- gtm focus list [--user]

GHA cron template: digest-cron.yml.example runs nightly at user's local time

Begin.
```

---

### Batch J — Feedback loops, polish, v1.0.0

**Scope:** Win/loss feedback ingestion into ICP rules, outcome tracking, personalized opener generation, token budget guardrails, `gtm doctor`, v1.0.0 release.

**Dependencies:** All previous batches.

**Kickoff prompt for Batch J:**

```
Execute Batch J from GTM_OS_CLAUDE_CODE_PLAN.md Section 4.J.

Feedback loops:
- Weekly job: re-reads all winloss_analyses, re-weights icp_rules.json
  (higher weight to traits that cluster in won deals; lower for lost)
- Writes icp_rules_recommended.json alongside icp_rules.json
  (human reviews and approves via gtm rules review)
- gtm rules {show, diff, apply, history}

Outcome tracking:
- HubSpot webhook: deal closed → update contact.outreach_outcome
  (booked, ghosted, replied_positive, replied_negative, bounced)
- Aggregate in outcome_stats view

Personalized opener generation:
- For each contact in sequence export, generate 1-sentence custom opener
  using pain signals + initiative signals + product_content signals
- Model: claude-haiku-4-5 (Batch H confirmed model routing)
- Written to contacts.personalized_opener
- CLI: gtm openers generate --campaign <id> [--limit N]

Token budget guardrails:
- Config: max_tokens_per_day, max_tokens_per_run, alert_threshold
- Cost tracker accumulates; gtm cost forecast warns before expensive runs
- Enforced at LLMClient.complete(); raises BudgetExceededError

gtm doctor:
- Validates entire system state: DB migrations, all env vars set,
  at least one signal ingested in last 7d, Slack delivery working,
  CRM connection live, Instantly campaign has leads
- Prints a red/green checklist; exits non-zero if any critical checks fail
- Run as the first step in all GHA workflows

v1.0.0:
- Bump pyproject.toml to 1.0.0
- Update CHANGELOG.md with full release notes
- Tag v1.0.0 (do not push; human triggers release)

Begin.
```

---

## Section 5 — Soak tests

See batch-specific soak tests embedded in Section 4 above.

## Section 6 — Prompt evaluation protocol (Batch H)

Before declaring Batch H done:
1. Run `gtm eval run pain_extractor` against your 20-30 real Gong transcripts
2. Score each output against rubric.md (precision, recall, hallucination rate)
3. Target: ≥ 80% precision, ≥ 70% recall, 0 hallucinations
4. If any metric fails, iterate on the prompt in `src/llm/prompts/pain_extraction.md`
5. Repeat for objection_classification, persona_detection, initiative_detection
6. Only proceed to Batch I after all 4 processors pass evaluation

---

*NOTE: This document was partially truncated at 50,000 characters when received. Sections 5 (soak tests F-J detail) and 6 (full prompt evaluation protocol) may be incomplete. Paste the complete plan if updates are needed.*
