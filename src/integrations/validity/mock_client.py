from __future__ import annotations

from typing import List

from src.integrations.validity.base import ValidityBase
from src.monitoring.campaign_health import load_campaign_metrics
from src.utils.logger import get_logger

log = get_logger(__name__)


class ValidityMockClient(ValidityBase):
    """
    Validity mock client — reads campaign metrics from a local JSON file.
    Future: replace with Validity API and live sequencing platform data.
    """

    def get_campaign_metrics(self, file_path: str) -> List[dict]:
        log.info("Validity mock: loading campaign metrics from %s", file_path)
        metrics = load_campaign_metrics(file_path)
        log.info("Validity mock: %d campaigns loaded", len(metrics))
        return metrics
