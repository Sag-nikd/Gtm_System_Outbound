from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.MOCK_MODE: bool = os.getenv("MOCK_MODE", "true").lower() == "true"

        # Per-integration mode overrides: "mock" or "live".
        # Defaults to the global MOCK_MODE setting when not explicitly set.
        _default_mode = "mock" if self.MOCK_MODE else "live"
        self.APOLLO_MODE: str = os.getenv("APOLLO_MODE", _default_mode)
        self.CLAY_MODE: str = os.getenv("CLAY_MODE", _default_mode)
        self.HUBSPOT_MODE: str = os.getenv("HUBSPOT_MODE", _default_mode)
        self.ZEROBOUNCE_MODE: str = os.getenv("ZEROBOUNCE_MODE", _default_mode)
        self.NEVERBOUNCE_MODE: str = os.getenv("NEVERBOUNCE_MODE", _default_mode)
        self.VALIDITY_MODE: str = os.getenv("VALIDITY_MODE", _default_mode)

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

        self.LOG_FORMAT: str = os.getenv("LOG_FORMAT", "text")

        # ICP Intelligence (Stage 0) settings
        self.ICP_INTELLIGENCE_ENABLED: bool = (
            os.getenv("ICP_INTELLIGENCE_ENABLED", "false").lower() == "true"
        )
        self.ICP_DEAL_DATA_PATH: str = os.getenv(
            "ICP_DEAL_DATA_PATH",
            os.path.join(self.DATA_DIR, "icp_intelligence", "mock_deal_history.json"),
        )
        self.ICP_PIPELINE_DATA_PATH: str = os.getenv("ICP_PIPELINE_DATA_PATH", "")
        self.ICP_TAM_DATA_PATH: str = os.getenv("ICP_TAM_DATA_PATH", "")
        self.ICP_FEEDBACK_ENABLED: bool = (
            os.getenv("ICP_FEEDBACK_ENABLED", "false").lower() == "true"
        )
        self.ICP_DATA_SOURCE: str = os.getenv("ICP_DATA_SOURCE", "csv")

        self._validate()

    # Map per-integration MODE attr → required API key attr
    _MODE_KEY_MAP = [
        ("APOLLO_MODE", "APOLLO_API_KEY"),
        ("CLAY_MODE", "CLAY_API_KEY"),
        ("HUBSPOT_MODE", "HUBSPOT_PRIVATE_APP_TOKEN"),
        ("ZEROBOUNCE_MODE", "ZEROBOUNCE_API_KEY"),
        ("NEVERBOUNCE_MODE", "NEVERBOUNCE_API_KEY"),
        ("VALIDITY_MODE", "VALIDITY_API_KEY"),
    ]

    # Kept for backwards-compat with existing settings tests
    _REQUIRED_LIVE_KEYS = [key for _, key in _MODE_KEY_MAP]

    def _validate(self) -> None:
        missing = [
            key
            for mode_attr, key in self._MODE_KEY_MAP
            if getattr(self, mode_attr, "live") == "live" and not getattr(self, key, "")
        ]
        if missing:
            raise EnvironmentError(
                f"Missing required keys for live mode: {', '.join(missing)}"
            )


settings = Settings()
