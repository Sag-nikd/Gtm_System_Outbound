"""Tests that pipeline stages are skipped when upstream returns zero actionable records."""
from __future__ import annotations

import os


class _AllTier3Apollo:
    """Apollo mock: companies that score as Disqualified (Retail, zero members)."""
    def get_companies(self, file_path: str):
        return [
            {
                "company_id": f"co_{i:03d}",
                "company_name": f"Retail Co {i}",
                "website": f"https://retail{i}.com",
                "domain": f"retail{i}.com",
                "industry": "Retail",
                "employee_count": 10,
                "revenue_range": "<$1M",
                "state": "Texas",
                "primary_volume_metric": 0,
                "secondary_volume_metric": 0,
                "growth_signal": False,
                "hiring_signal": False,
                "tech_stack_signal": "Unknown",
                "ingestion_source": "fake_data",
                "ingestion_status": "ingested",
            }
            for i in range(3)
        ]

    def get_contacts(self, file_path: str):
        return []


class _AllSuppressedZeroBounce:
    """ZeroBounce mock: marks every contact as suppressed/invalid."""
    def validate_contacts(self, contacts):
        for ct in contacts:
            ct["zerobounce_status"] = "invalid"
            ct["zerobounce_reason"] = "mailbox does not exist"
            ct["neverbounce_status"] = "invalid"
            ct["neverbounce_reason"] = "undeliverable"
            ct["final_validation_status"] = "suppressed"
            ct["final_validation_reason"] = "both validators returned invalid"
        return contacts


class _PassthroughNeverBounce:
    def validate_contacts(self, contacts):
        return contacts


class _NullClay:
    def enrich_accounts(self, companies):
        for c in companies:
            c["enrichment_status"] = "enriched"
            c["enrichment_source"] = "clay_mock"
            c["recommended_personas"] = ""
            c["enriched_signal_summary"] = ""
            c["contact_discovery_approved"] = False
        return companies


class _NullHubSpot:
    def upsert_companies(self, companies):
        return []
    def upsert_contacts(self, contacts, companies):
        return []


class _NullValidity:
    def get_campaign_metrics(self, file_path: str):
        return []


def test_main_skips_contact_and_activation_when_zero_approved(tmp_path, monkeypatch):
    """main() does not write contact or activation CSVs when no companies are approved."""
    import src.main as main_mod
    from src.config.settings import settings

    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(
        main_mod, "_get_clients",
        lambda: (_AllTier3Apollo(), _NullClay(), _NullHubSpot(),
                 _AllSuppressedZeroBounce(), _PassthroughNeverBounce(), _NullValidity()),
    )

    main_mod.main()

    files = os.listdir(str(tmp_path))
    assert "05_discovered_contacts.csv" not in files, \
        "Contact discovery CSV must not be written when no companies are approved"
    assert "09_email_sequence_export.csv" not in files, \
        "Email sequence CSV must not be written when no companies are approved"
    assert "10_linkedin_outreach_export.csv" not in files, \
        "LinkedIn CSV must not be written when no companies are approved"
    # Campaign monitoring still runs independently (empty report is fine)
    assert "11_campaign_health_report.csv" in files


def test_main_skips_activation_when_zero_approved_contacts(tmp_path, monkeypatch):
    """main() does not write activation CSVs when all contacts are suppressed."""
    import src.main as main_mod
    from src.config.settings import settings
    from src.integrations.apollo.mock_client import ApolloMockClient
    from src.integrations.clay.mock_client import ClayMockClient

    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(
        main_mod, "_get_clients",
        lambda: (ApolloMockClient(), ClayMockClient(), _NullHubSpot(),
                 _AllSuppressedZeroBounce(), _PassthroughNeverBounce(), _NullValidity()),
    )

    main_mod.main()

    files = os.listdir(str(tmp_path))
    # Contact pipeline ran (approved companies exist in real mock data)
    assert "05_discovered_contacts.csv" in files
    assert "06_email_validation_results.csv" in files
    # Activation skipped because all contacts suppressed
    assert "09_email_sequence_export.csv" not in files, \
        "Email sequence CSV must not be written when no contacts are approved"
    assert "10_linkedin_outreach_export.csv" not in files
