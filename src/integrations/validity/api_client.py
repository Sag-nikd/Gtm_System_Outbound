from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from src.integrations.validity.base import ValidityBase
from src.utils.retry import api_retry
from src.utils.logger import get_logger

log = get_logger(__name__)

_BASE_URL = "https://api.senderscore.com/v1"


class ValidityAPIClient(ValidityBase):
    """
    Validity Everest API client.
    Requires VALIDITY_API_KEY (Bearer token) in environment.
    Endpoints used:
      GET /campaigns          — list all campaigns
      GET /campaigns/{id}/metrics — per-campaign deliverability metrics
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = f"{_BASE_URL}{path}"
        resp = requests.get(url, headers=self._headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def _list_campaigns(self) -> List[Dict[str, Any]]:
        """Return all campaigns from Validity Everest."""
        data = self._get("/campaigns")
        if isinstance(data, list):
            return data
        return data.get("campaigns", data.get("data", []))

    def _get_campaign_metrics(self, campaign_id: str) -> Dict[str, Any]:
        """Return deliverability metrics for a single campaign."""
        return self._get(f"/campaigns/{campaign_id}/metrics")

    @api_retry
    def get_campaign_metrics(self, file_path: str) -> List[dict]:
        """
        Fetch live campaign metrics from Validity Everest API.
        The file_path argument is accepted for interface compatibility but ignored;
        data comes from the API.
        """
        campaigns = self._list_campaigns()
        log.info("Validity: found %d campaigns", len(campaigns))

        results: List[dict] = []
        for campaign in campaigns:
            campaign_id = str(campaign.get("id", campaign.get("campaign_id", "")))
            if not campaign_id:
                continue
            try:
                metrics = self._get_campaign_metrics(campaign_id)
                record = _merge_campaign_metrics(campaign, metrics)
                results.append(record)
            except requests.HTTPError as exc:
                log.warning("Validity metrics fetch failed for campaign %s: %s", campaign_id, exc)
            except requests.RequestException as exc:
                log.warning("Validity request error for campaign %s: %s", campaign_id, exc)

        log.info("Validity: collected metrics for %d/%d campaigns", len(results), len(campaigns))
        return results


def _merge_campaign_metrics(campaign: Dict[str, Any], metrics: Dict[str, Any]) -> dict:
    """Merge campaign metadata with deliverability metrics into a flat record."""
    delivered = int(metrics.get("delivered", 0))
    sent = int(metrics.get("sent", campaign.get("volume", 0)) or 1)
    opens = int(metrics.get("opens", metrics.get("unique_opens", 0)))
    clicks = int(metrics.get("clicks", metrics.get("unique_clicks", 0)))
    bounces = int(metrics.get("bounces", metrics.get("hard_bounces", 0)))
    complaints = int(metrics.get("complaints", metrics.get("spam_complaints", 0)))
    unsubscribes = int(metrics.get("unsubscribes", 0))

    delivery_rate = delivered / sent if sent else 0.0
    open_rate = opens / delivered if delivered else 0.0
    click_rate = clicks / delivered if delivered else 0.0
    bounce_rate = bounces / sent if sent else 0.0
    complaint_rate = complaints / delivered if delivered else 0.0
    unsubscribe_rate = unsubscribes / delivered if delivered else 0.0

    return {
        "campaign_id": str(campaign.get("id", campaign.get("campaign_id", ""))),
        "campaign_name": campaign.get("name", campaign.get("campaign_name", "")),
        "send_date": campaign.get("send_date", campaign.get("sent_at", "")),
        "platform": campaign.get("platform", campaign.get("esp", "")),
        "volume": sent,
        "delivered": delivered,
        "delivery_rate": round(delivery_rate, 4),
        "opens": opens,
        "open_rate": round(open_rate, 4),
        "clicks": clicks,
        "click_rate": round(click_rate, 4),
        "bounces": bounces,
        "bounce_rate": round(bounce_rate, 4),
        "complaints": complaints,
        "complaint_rate": round(complaint_rate, 4),
        "unsubscribes": unsubscribes,
        "unsubscribe_rate": round(unsubscribe_rate, 4),
        "sender_score": metrics.get("sender_score", None),
        "inbox_rate": metrics.get("inbox_rate", metrics.get("inbox_placement", None)),
    }
