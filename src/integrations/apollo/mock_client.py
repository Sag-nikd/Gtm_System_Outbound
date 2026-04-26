from __future__ import annotations

from typing import List

from src.ingestion.company_ingestion import load_companies
from src.validation.email_validation_mock import load_contacts
from src.utils.logger import get_logger

log = get_logger(__name__)


class ApolloMockClient:
    """
    Apollo mock client — reads from local JSON data files.
    Future: replace with Apollo API (firmographic + contact search).
    """

    def get_companies(self, file_path: str) -> List[dict]:
        log.info("Apollo mock: loading companies from %s", file_path)
        companies = load_companies(file_path)
        log.info("Apollo mock: %d companies loaded", len(companies))
        return companies

    def get_contacts(self, file_path: str) -> List[dict]:
        log.info("Apollo mock: loading contacts from %s", file_path)
        contacts = load_contacts(file_path)
        log.info("Apollo mock: %d contacts loaded", len(contacts))
        return contacts
