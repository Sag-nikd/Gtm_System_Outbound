from __future__ import annotations

import json
from typing import List, Optional

from pydantic import BaseModel


class ApolloQueryConfig(BaseModel):
    organization_search: dict
    contact_search: dict
    exclusions: dict
    estimated_tam_size: int
    query_rationale: str

    def save(self, output_path: str) -> None:
        import os
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.model_dump(), f, indent=2)
