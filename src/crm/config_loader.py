from __future__ import annotations

import os
from typing import Any, Dict, Optional

import yaml

from src.utils.logger import get_logger

log = get_logger(__name__)

_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "crm",
)


def _load_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_client_config(client_name: str, config_dir: Optional[str] = None) -> Dict[str, Any]:
    """Load a client YAML config by name. Looks for {client_name}.yaml first, falls back to client_template.yaml."""
    base = config_dir or _CONFIG_DIR
    candidate = os.path.join(base, f"{client_name}.yaml")
    if os.path.exists(candidate):
        log.info("Loading client config: %s", candidate)
        return _load_yaml(candidate)
    fallback = os.path.join(base, "client_template.yaml")
    log.info("Client config not found for '%s', using template: %s", client_name, fallback)
    config = _load_yaml(fallback)
    config.setdefault("client", {})["name"] = client_name
    return config


def load_crm_default_setup(crm: str, config_dir: Optional[str] = None) -> Dict[str, Any]:
    """Load the default CRM setup YAML (hubspot or salesforce)."""
    base = config_dir or _CONFIG_DIR
    path = os.path.join(base, f"{crm}_default_setup.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"CRM setup config not found: {path}")
    log.info("Loading CRM default setup: %s", path)
    return _load_yaml(path)


def load_lifecycle_rules(config_dir: Optional[str] = None) -> Dict[str, Any]:
    base = config_dir or _CONFIG_DIR
    path = os.path.join(base, "lifecycle_rules.yaml")
    return _load_yaml(path)


def load_pipeline_templates(config_dir: Optional[str] = None) -> Dict[str, Any]:
    base = config_dir or _CONFIG_DIR
    path = os.path.join(base, "pipeline_templates.yaml")
    return _load_yaml(path)


def load_field_mapping(config_dir: Optional[str] = None) -> Dict[str, Any]:
    base = config_dir or _CONFIG_DIR
    path = os.path.join(base, "field_mapping.yaml")
    return _load_yaml(path)


def resolve_setup_config(
    client_name: str,
    crm: str,
    config_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge client config + CRM default setup into a single resolved config dict."""
    client_cfg = load_client_config(client_name, config_dir)
    crm_cfg = load_crm_default_setup(crm, config_dir)
    return {
        "client": client_cfg.get("client", {}),
        "gtm": client_cfg.get("gtm", {}),
        "crm_setup": client_cfg.get("crm_setup", {}),
        "custom_fields": crm_cfg.get("custom_fields", {}),
        "pipeline": crm_cfg.get("pipeline", {}),
        "objects": crm_cfg.get("objects", {}),
    }
