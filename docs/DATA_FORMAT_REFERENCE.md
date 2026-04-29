# Data Format Reference

Complete field reference for DealRecord, PipelineRecord, and TAMRecord schemas.

---

## DealRecord

Represents one company the user has engaged with (past or current deal).

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `company_name` | string | **Yes** | Legal or common company name |
| `industry` | string | **Yes** | Primary industry (e.g., "Managed Care", "Health Plan") |
| `employee_count` | integer | **Yes** | Total headcount |
| `deal_stage` | string | **Yes** | See Deal Stage Taxonomy below |
| `domain` | string | No | Company website domain (used for deduplication) |
| `sub_industry` | string | No | More specific segment (e.g., "Medicaid MCO") |
| `revenue_range` | string | No | Annual revenue range (e.g., "$500M-$1B") |
| `state` | string | No | US state abbreviation or full name |
| `country` | string | No | Default: "US" |
| `medicaid_members` | integer | No | Medicaid member lives managed |
| `medicare_members` | integer | No | Medicare member lives managed |
| `tech_stack` | string | No | Primary CRM/platform (e.g., "Salesforce") |
| `deal_value` | float | No | Contract value in USD |
| `deal_cycle_days` | integer | No | Days from first contact to close |
| `source_channel` | string | No | How the deal originated (see Source Channels below) |
| `contact_title` | string | No | Title of the primary contact |
| `contact_persona` | string | No | Persona bucket (e.g., "VP Member Engagement") |
| `meeting_booked` | boolean | No | Whether a discovery call was scheduled |
| `proposal_sent` | boolean | No | Whether a proposal/SOW was sent |
| `closed_date` | string | No | ISO date (YYYY-MM-DD) — used for dedup: most recent kept |
| `loss_reason` | string | No | Why the deal was lost (e.g., "budget", "not_our_market") |

### Deal Stage Taxonomy

| Stage | Meaning | Counts as |
|-------|---------|-----------|
| `prospecting` | Identified, not yet contacted | Top of funnel |
| `contacted` | First outreach sent | Engaged |
| `meeting_booked` | Discovery/demo scheduled | Engaged |
| `proposal_sent` | Proposal/SOW delivered | Active pipeline |
| `negotiation` | Terms being discussed | Active pipeline |
| `closed_won` | Deal signed | **Converted** |
| `closed_lost` | Deal lost | Lost |
| `disqualified` | Not a fit | Disqualified |

### Source Channels

| Value | Meaning |
|-------|---------|
| `outbound_email` | Cold email sequence |
| `outbound_linkedin` | LinkedIn outreach |
| `inbound` | Inbound lead |
| `inbound_referral` | Referral from existing customer |
| `conference` | Conference or event |
| `paid` | Paid advertising |

### CSV Header Template

```
company_name,domain,industry,sub_industry,employee_count,revenue_range,state,country,medicaid_members,medicare_members,tech_stack,deal_stage,deal_value,deal_cycle_days,source_channel,contact_title,contact_persona,meeting_booked,proposal_sent,closed_date,loss_reason
```

### Example Record

```json
{
  "company_name": "Centene Health Partners",
  "domain": "centene.com",
  "industry": "Managed Care",
  "sub_industry": "Medicaid MCO",
  "employee_count": 3200,
  "revenue_range": "$1B+",
  "state": "Missouri",
  "medicaid_members": 850000,
  "medicare_members": 120000,
  "tech_stack": "Salesforce",
  "deal_stage": "closed_won",
  "deal_value": 150000,
  "deal_cycle_days": 62,
  "source_channel": "outbound_email",
  "contact_persona": "VP Member Engagement",
  "closed_date": "2025-09-15"
}
```

---

## PipelineRecord

Represents a currently active deal in your pipeline.

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `company_name` | string | **Yes** | Company name |
| `deal_stage` | string | **Yes** | Current deal stage |
| `domain` | string | No | Company domain |
| `deal_value` | float | No | Estimated contract value |
| `days_in_stage` | integer | No | Days at current stage |
| `last_activity_date` | string | No | ISO date of most recent activity |
| `assigned_rep` | string | No | Sales rep name |
| `engagement_score` | float | No | Engagement score 0–100 |

### CSV Header Template

```
company_name,domain,deal_stage,deal_value,days_in_stage,last_activity_date,assigned_rep,engagement_score
```

---

## TAMRecord

Represents a company in your total addressable market (not necessarily a customer).

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `company_name` | string | **Yes** | Company name |
| `industry` | string | **Yes** | Primary industry |
| `domain` | string | No | Company domain |
| `sub_industry` | string | No | Segment |
| `employee_count` | integer | No | Total headcount |
| `state` | string | No | US state |
| `medicaid_members` | integer | No | Medicaid members managed |
| `medicare_members` | integer | No | Medicare members managed |
| `tech_stack` | string | No | Primary platform |
| `is_current_customer` | boolean | No | Default: false |

### CSV Header Template

```
company_name,domain,industry,sub_industry,employee_count,state,medicaid_members,medicare_members,tech_stack,is_current_customer
```

---

## HubSpot Field Mapping

| HubSpot Property | DealRecord Field | Notes |
|-----------------|-----------------|-------|
| `dealname` | `company_name` | Strip deal description if formatted as "Company - Deal" |
| `amount` | `deal_value` | Convert string to float |
| `dealstage` | `deal_stage` | Map via HubSpot stage ID or label (see below) |
| `closedate` | `closed_date` | Convert to YYYY-MM-DD |
| `hs_analytics_source` | `source_channel` | Map to source channel values |
| `industry` | `industry` | Direct mapping |
| `employee_count` / `numberofemployees` | `employee_count` | Convert to int |
| `domain` / `website` | `domain` | Strip https:// if present |

### HubSpot Stage Mapping

| HubSpot Stage Label | DealRecord `deal_stage` |
|---------------------|------------------------|
| Appointment Scheduled | `meeting_booked` |
| Qualified To Buy | `proposal_sent` |
| Presentation Scheduled | `meeting_booked` |
| Decision Maker Bought-In | `negotiation` |
| Contract Sent | `negotiation` |
| Closed Won | `closed_won` |
| Closed Lost | `closed_lost` |

---

## Salesforce Field Mapping

| Salesforce Field | DealRecord Field | Notes |
|-----------------|-----------------|-------|
| `Name` | `company_name` | Strip deal description (e.g., "Company - Q4 Deal" → "Company") |
| `Amount` | `deal_value` | Convert string to float |
| `StageName` | `deal_stage` | Map via stage name (see below) |
| `CloseDate` | `closed_date` | Convert to YYYY-MM-DD |
| `LeadSource` | `source_channel` | Map to source channel values |
| `Industry` or `Industry__c` | `industry` | Use custom field if standard is blank |
| `NumberOfEmployees` | `employee_count` | Convert to int |
| `Website` or `Website__c` | `domain` | Strip https:// |

### Salesforce Stage Mapping

| Salesforce `StageName` | DealRecord `deal_stage` |
|------------------------|------------------------|
| Prospecting | `prospecting` |
| Qualification | `contacted` |
| Needs Analysis | `contacted` |
| Value Proposition | `meeting_booked` |
| Id. Decision Makers | `meeting_booked` |
| Perception Analysis | `proposal_sent` |
| Proposal/Price Quote | `proposal_sent` |
| Negotiation/Review | `negotiation` |
| Closed Won | `closed_won` |
| Closed Lost | `closed_lost` |
