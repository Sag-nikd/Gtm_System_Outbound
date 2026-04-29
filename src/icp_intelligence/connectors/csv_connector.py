from __future__ import annotations

import os
from typing import List, Optional

from src.icp_intelligence.connectors.base import ICPDataConnectorBase
from src.icp_intelligence.data_ingestion import load_deal_data, load_pipeline_data, load_tam_data
from src.utils.logger import get_logger

log = get_logger(__name__)


class CSVConnector(ICPDataConnectorBase):
    """File-based ICP data connector. Wraps load_deal_data/load_pipeline_data."""

    def __init__(
        self,
        deal_file: str = "",
        pipeline_file: str = "",
        company_file: str = "",
    ) -> None:
        self._deal_file = deal_file
        self._pipeline_file = pipeline_file
        self._company_file = company_file

    def connect(self) -> bool:
        exists = os.path.exists(self._deal_file) if self._deal_file else False
        if not exists:
            log.warning("CSVConnector: file not found — %s", self._deal_file)
        return exists

    def pull_deals(self, since: Optional[str] = None) -> List[dict]:
        if not self._deal_file:
            return []
        deals = load_deal_data(self._deal_file)
        if since:
            deals = [d for d in deals if (d.get("closed_date") or "") >= since]
        return deals

    def pull_pipeline(self, since: Optional[str] = None) -> List[dict]:
        if not self._pipeline_file:
            return []
        records = load_pipeline_data(self._pipeline_file)
        if since:
            records = [r for r in records
                       if (r.get("last_activity_date") or "") >= since]
        return records

    def pull_companies(self) -> List[dict]:
        if not self._company_file:
            return []
        return load_tam_data(self._company_file)

    def map_to_deal_record(self, raw: dict) -> dict:
        return raw
