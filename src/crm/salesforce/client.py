from __future__ import annotations

import os
from typing import Any, Dict, List

from src.utils.logger import get_logger
from src.utils.retry import api_retry

log = get_logger(__name__)

# Salesforce uses OAuth2 username-password flow for server-to-server access.
# Metadata API (for creating custom fields) requires additional Tooling API calls
# or Metadata API SOAP calls — more complex than HubSpot's REST properties API.
# Live field creation is stubbed with clear TODOs. Dry-run is fully supported.


class SalesforceClient:
    """
    Salesforce REST + Tooling API client stub.
    authenticate() obtains an OAuth2 access token.
    Field/object creation methods raise NotImplementedError — see TODOs below.
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

    @api_retry
    def authenticate(self) -> bool:
        """
        Obtain OAuth2 access token using username-password flow.

        TODO: Implement with requests:
            POST {instance_url}/services/oauth2/token
            grant_type=password
            client_id={client_id}
            client_secret={client_secret}
            username={username}
            password={password+security_token}
        """
        raise NotImplementedError(
            "Salesforce live authentication not yet implemented. "
            "Use --mode dry-run or implement OAuth2 username-password flow."
        )

    @api_retry
    def get_object_fields(self, object_name: str) -> List[Dict[str, Any]]:
        """
        TODO: GET {instance_url}/services/data/v57.0/sobjects/{object_name}/describe/
        Returns field metadata including Name, Type, Custom.
        """
        raise NotImplementedError(
            f"get_object_fields({object_name}) not yet implemented. Use --mode dry-run."
        )

    @api_retry
    def create_custom_field(
        self, object_name: str, field_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        TODO: Use Tooling API to create a CustomField metadata record.
            POST {instance_url}/services/data/v57.0/tooling/sobjects/CustomField/
            Body: {FullName: '{object_name}.{field_name}', Metadata: {...}}

        Requires:
          1. Create CustomField via Tooling API
          2. Deploy via MetadataService or Tooling API deployments
          3. Add to Page Layouts (separate step — do manually or via Metadata API)
        """
        raise NotImplementedError(
            f"Salesforce live custom field creation for {object_name} not yet implemented. "
            "Use --mode dry-run to generate the field plan, then create fields manually in "
            "Salesforce Setup → Object Manager → {object_name} → Fields & Relationships."
        )

    @api_retry
    def get_opportunity_stages(self) -> List[Dict[str, Any]]:
        """
        TODO: SOQL query via REST API:
            SELECT MasterLabel, Probability FROM OpportunityStage WHERE IsActive = true
        """
        raise NotImplementedError(
            "get_opportunity_stages not yet implemented. Use --mode dry-run."
        )

    @api_retry
    def create_opportunity_stage(self, stage_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        TODO: OpportunityStage picklist values are managed via Metadata API.
        This is safer done in Setup → Picklist Value Sets, or via Metadata API deployment.
        """
        raise NotImplementedError(
            "Salesforce opportunity stage creation requires Metadata API deployment. "
            "Add stages manually in Setup → Opportunity Stages. Use --mode dry-run for the plan."
        )
