from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() == "true"

        self.APOLLO_API_KEY: str = os.getenv("APOLLO_API_KEY", "")
        self.CLAY_API_KEY: str = os.getenv("CLAY_API_KEY", "")
        self.HUBSPOT_PRIVATE_APP_TOKEN: str = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")
        self.ZEROBOUNCE_API_KEY: str = os.getenv("ZEROBOUNCE_API_KEY", "")
        self.NEVERBOUNCE_API_KEY: str = os.getenv("NEVERBOUNCE_API_KEY", "")
        self.VALIDITY_API_KEY: str = os.getenv("VALIDITY_API_KEY", "")

        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

        # Paths resolved from project root (3 levels up from src/config/settings.py)
        _here = os.path.dirname(os.path.abspath(__file__))
        self.BASE_DIR: str = os.path.dirname(os.path.dirname(_here))
        self.DATA_DIR: str = os.path.join(self.BASE_DIR, "data")
        self.CONFIG_DIR: str = os.path.join(self.BASE_DIR, "config")

        _output_env = os.getenv("OUTPUT_DIR", "outputs")
        self.OUTPUT_DIR: str = (
            _output_env
            if os.path.isabs(_output_env)
            else os.path.join(self.BASE_DIR, _output_env)
        )


settings = Settings()
