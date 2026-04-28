from __future__ import annotations

from typing import List

from src.integrations.neverbounce.base import NeverBounceBase
from src.utils.logger import get_logger

log = get_logger(__name__)


class NeverBounceMockClient(NeverBounceBase):
    """
    NeverBounce mock client — pass-through in mock mode.
    The ZeroBounce mock already populates both zerobounce_* and neverbounce_* fields
    in a single pass. In production, this client makes a real second API call.
    Future: replace with real NeverBounce API for independent second-pass validation.
    """

    def validate_contacts(self, contacts: List[dict]) -> List[dict]:
        log.info(
            "NeverBounce mock: pass-through (%d contacts — fields set by ZeroBounce mock)",
            len(contacts),
        )
        return contacts
