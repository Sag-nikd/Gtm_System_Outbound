from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import requests

from src.utils.logger import get_logger
from src.utils.retry import api_retry

log = get_logger(__name__)

_BASE_URL = "https://api.hubapi.com"


class HubSpotClient:
    """
    Thin HubSpot REST client using the Private App token.
    All methods raise NotImplementedError when no token is available.
    Used only in live mode — dry-run skips all network calls.
    """

    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError(
                "HUBSPOT_PRIVATE_APP_TOKEN is required for live mode. "
                "Set it in .env or use --mode dry-run."
            )
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{_BASE_URL}{path}"
        resp = requests.get(url, headers=self._headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{_BASE_URL}{path}"
        resp = requests.post(url, headers=self._headers, json=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()

    @api_retry
    def get_properties(self, object_name: str) -> List[Dict[str, Any]]:
        data = self._get(f"/crm/v3/properties/{object_name}")
        return data.get("results", [])

    @api_retry
    def create_property(self, object_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(f"/crm/v3/properties/{object_name}", payload)

    @api_retry
    def get_pipelines(self, object_name: str = "deals") -> List[Dict[str, Any]]:
        data = self._get(f"/crm/v3/pipelines/{object_name}")
        return data.get("results", [])

    @api_retry
    def create_pipeline(self, object_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._post(f"/crm/v3/pipelines/{object_name}", payload)

    @api_retry
    def create_pipeline_stage(
        self, object_name: str, pipeline_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self._post(
            f"/crm/v3/pipelines/{object_name}/{pipeline_id}/stages", payload
        )

    @api_retry
    def get_property_groups(self, object_name: str) -> List[Dict[str, Any]]:
        data = self._get(f"/crm/v3/properties/{object_name}/groups")
        return data.get("results", [])

    @api_retry
    def create_property_group(
        self, object_name: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        return self._post(f"/crm/v3/properties/{object_name}/groups", payload)
