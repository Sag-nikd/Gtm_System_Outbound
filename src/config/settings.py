"""Application settings — loaded from .env.local (or environment) via pydantic-settings."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── General ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    json_logs: bool = False
    mock_mode: bool = True

    # ── Paths ─────────────────────────────────────────────────────────────────
    base_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)

    @property
    def data_dir(self) -> Path:
        return self.base_dir / "data"

    @property
    def config_dir(self) -> Path:
        return self.base_dir / "config"

    @property
    def output_dir(self) -> Path:
        return self.base_dir / "outputs"

    @property
    def db_url(self) -> str:
        db_path = self.data_dir / "gtm_os.db"
        return f"sqlite+aiosqlite:///{db_path}"

    # ── Vendor API keys ───────────────────────────────────────────────────────
    apollo_api_key: str = ""
    hubspot_private_app_token: str = ""
    instantly_api_key: str = ""
    instantly_test_campaign_id: str = ""
    zerobounce_api_key: str = ""
    anthropic_api_key: str = ""
    voyage_api_key: str = ""
    granola_api_key: str = ""
    notion_api_key: str = ""
    notion_root_page_ids: str = ""  # comma-separated
    slack_bot_token: str = ""
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = ""
    gong_access_key: str = ""
    gong_access_key_secret: str = ""

    # ── Webhook secrets ───────────────────────────────────────────────────────
    instantly_webhook_secret: str = ""
    hubspot_webhook_secret: str = ""

    # ── Per-integration mode overrides ────────────────────────────────────────
    apollo_mode: str = ""       # "mock" | "live" | "" (falls back to mock_mode)
    hubspot_mode: str = ""
    instantly_mode: str = ""
    zerobounce_mode: str = ""

    def integration_mode(self, vendor: str) -> str:
        override = getattr(self, f"{vendor}_mode", "")
        if override:
            return override
        return "mock" if self.mock_mode else "live"

    @property
    def notion_page_ids(self) -> list[str]:
        return [p.strip() for p in self.notion_root_page_ids.split(",") if p.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    os.makedirs(s.data_dir, exist_ok=True)
    os.makedirs(s.output_dir, exist_ok=True)
    return s
