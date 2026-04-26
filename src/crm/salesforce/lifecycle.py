from __future__ import annotations

from typing import Any, Dict, List

# Salesforce lifecycle updates are managed via custom __c fields.
# Native Salesforce Lead Status and Opportunity Stage should be managed via
# Process Builder, Flow, or Apex — not updated directly by this tool.

GTM_LIFECYCLE_FIELDS: List[Dict[str, Any]] = [
    {
        "internal_name": "GTM_Status__c",
        "label": "GTM Status",
        "type": "Picklist",
        "options": [
            "Sales Ready",
            "Not Scored",
            "Nurture",
            "Disqualified",
            "In Sequence",
            "Replied",
            "Meeting Booked",
        ],
        "description": "External GTM status — updated by GTM system, not Salesforce workflows",
        "object": "Contact",
    },
    {
        "internal_name": "GTM_Lifecycle_Stage__c",
        "label": "GTM Lifecycle Stage",
        "type": "Picklist",
        "options": ["Target", "MQL", "SQL", "Opportunity", "Customer", "Churned"],
        "description": "GTM-managed lifecycle stage. Map to native Lead Status/Stage via Flow.",
        "object": "Contact",
    },
    {
        "internal_name": "GTM_Status__c",
        "label": "GTM Status",
        "type": "Picklist",
        "options": [
            "Sales Ready",
            "Not Scored",
            "Nurture",
            "Disqualified",
            "In Sequence",
            "Replied",
            "Meeting Booked",
        ],
        "object": "Lead",
    },
]

MANUAL_STEPS = [
    "In Salesforce Setup > Object Manager > Contact > Fields & Relationships: "
    "verify GTM_Status__c and GTM_Lifecycle_Stage__c are visible to relevant profiles.",
    "Create a Salesforce Flow: when GTM_Status__c = 'Sales Ready', update Lead Status = 'Working'.",
    "Create a Salesforce Flow: when GTM_Lifecycle_Stage__c = 'Opportunity', create an Opportunity record.",
    "Assign new custom fields to Page Layouts for Account, Contact, Lead, and Opportunity.",
    "Add Opportunity Stage picklist values in Setup > Picklist Value Sets > Opportunity Stage.",
]
