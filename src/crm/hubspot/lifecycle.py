from __future__ import annotations

from typing import Any, Dict, List

# GTM lifecycle stage fields are stored as custom HubSpot properties,
# not as native HubSpot lifecycle stages, to avoid conflicts with CRM-native rules.
# Native lifecycle stages (Subscriber, Lead, MQL, SQL, Opportunity, Customer)
# should be managed via HubSpot workflows — set those up manually in HubSpot UI.

GTM_LIFECYCLE_PROPERTIES: List[Dict[str, Any]] = [
    {
        "internal_name": "gtm_status",
        "label": "GTM Status",
        "type": "enumeration",
        "options": [
            {"label": "Sales Ready", "value": "sales_ready"},
            {"label": "Not Scored", "value": "not_scored"},
            {"label": "Nurture", "value": "nurture"},
            {"label": "Disqualified", "value": "disqualified"},
            {"label": "In Sequence", "value": "in_sequence"},
            {"label": "Replied", "value": "replied"},
            {"label": "Meeting Booked", "value": "meeting_booked"},
        ],
        "group": "gtm_properties",
        "description": "External GTM status — updated by GTM system, not by HubSpot workflows",
    },
    {
        "internal_name": "gtm_lifecycle_stage",
        "label": "GTM Lifecycle Stage",
        "type": "enumeration",
        "options": [
            {"label": "Target", "value": "target"},
            {"label": "MQL", "value": "mql"},
            {"label": "SQL", "value": "sql"},
            {"label": "Opportunity", "value": "opportunity"},
            {"label": "Customer", "value": "customer"},
            {"label": "Churned", "value": "churned"},
        ],
        "group": "gtm_properties",
        "description": (
            "GTM-managed lifecycle stage. "
            "Map to native HubSpot lifecycle stage via workflow if needed."
        ),
    },
]

MANUAL_STEPS = [
    "In HubSpot: create a Workflow (Contact-based), trigger on 'GTM Status = Sales Ready', "
    "action: Set Lifecycle Stage = MQL.",
    "In HubSpot: create a Workflow, trigger on 'GTM Status = Meeting Booked', "
    "action: Create Deal in GTM Outbound Pipeline at stage 'Meeting Booked'.",
    "In HubSpot: create a Workflow, trigger on Deal Stage = Closed Won, "
    "action: Set Contact Lifecycle Stage = Customer.",
    "In HubSpot: enable required property groups under Settings > Properties > Group.",
    "In HubSpot: assign the GTM Outbound Pipeline as the default pipeline for your sales team.",
]
