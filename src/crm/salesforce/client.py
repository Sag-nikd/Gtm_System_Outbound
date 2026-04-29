from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from src.utils.logger import get_logger
from src.utils.retry import api_retry

log = get_logger(__name__)

_API_VERSION = "v57.0"


class SalesforceClient:
    """
    Salesforce REST + Tooling API client.
    Call authenticate() before making any API requests.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
        security_token: str,
        instance_url: str,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.username = username
        self.password = password
        self.security_token = security_token
        self.instance_url = instance_url.rstrip("/")
        self._access_token: str = ""

    # ── Authentication ────────────────────────────────────────────────────────

    @api_retry
    def authenticate(self) -> bool:
        """
        Obtain OAuth2 access token via username-password flow.
        Returns True on success; raises on failure.
        """
        resp = requests.post(
            f"{self.instance_url}/services/oauth2/token",
            data={
                "grant_type": "password",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "username": self.username,
                "password": self.password + self.security_token,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        # Some flows return a different instance_url in the token response
        if "instance_url" in data:
            self.instance_url = data["instance_url"].rstrip("/")
        log.info("Salesforce: authenticated as %s", self.username)
        return True

    def _headers(self) -> Dict[str, str]:
        if not self._access_token:
            raise RuntimeError("SalesforceClient: call authenticate() before making API calls.")
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.instance_url}/services/data/{_API_VERSION}{path}"

    # ── Object metadata ───────────────────────────────────────────────────────

    @api_retry
    def get_object_fields(self, object_name: str) -> List[Dict[str, Any]]:
        """
        Describe a Salesforce object and return its field list.
        GET /services/data/v57.0/sobjects/{object_name}/describe/
        """
        resp = requests.get(
            self._url(f"/sobjects/{object_name}/describe/"),
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("fields", [])

    @api_retry
    def get_opportunity_stages(self) -> List[Dict[str, Any]]:
        """Return active Opportunity stage picklist values via SOQL."""
        soql = "SELECT MasterLabel, Probability FROM OpportunityStage WHERE IsActive = true"
        resp = requests.get(
            self._url("/query/"),
            headers=self._headers(),
            params={"q": soql},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("records", [])

    # ── Record operations ─────────────────────────────────────────────────────

    @api_retry
    def upsert_account(self, external_id_field: str, external_id: str, data: Dict[str, Any]) -> str:
        """
        Upsert a Salesforce Account using an external ID field.
        Returns the Salesforce Account ID.
        """
        resp = requests.patch(
            self._url(f"/sobjects/Account/{external_id_field}/{external_id}"),
            headers=self._headers(),
            json=data,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("id", external_id)

    @api_retry
    def upsert_contact(self, external_id_field: str, external_id: str, data: Dict[str, Any]) -> str:
        """
        Upsert a Salesforce Contact using an external ID field.
        Returns the Salesforce Contact ID.
        """
        resp = requests.patch(
            self._url(f"/sobjects/Contact/{external_id_field}/{external_id}"),
            headers=self._headers(),
            json=data,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("id", external_id)

    @api_retry
    def create_custom_field(self, object_name: str, field_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a custom field via Salesforce Tooling API.
        POST /services/data/v57.0/tooling/sobjects/CustomField/
        """
        resp = requests.post(
            f"{self.instance_url}/services/data/{_API_VERSION}/tooling/sobjects/CustomField/",
            headers=self._headers(),
            json={
                "FullName": f"{object_name}.{field_config['fullName']}",
                "Metadata": field_config.get("metadata", {}),
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    @api_retry
    def create_opportunity_stage(self, stage_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create an Opportunity stage via Tooling API."""
        resp = requests.post(
            f"{self.instance_url}/services/data/{_API_VERSION}/tooling/sobjects/OpportunityStage/",
            headers=self._headers(),
            json=stage_config,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
