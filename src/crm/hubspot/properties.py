from __future__ import annotations

from typing import Any, Dict, List

from src.utils.logger import get_logger

log = get_logger(__name__)

# HubSpot type mapping from generic config types
_TYPE_MAP: Dict[str, str] = {
    "string": "text",
    "number": "number",
    "enumeration": "enumeration",
    "bool": "booleancheckbox",
    "date": "date",
    "text": "text",
}

_FIELD_TYPE_MAP: Dict[str, str] = {
    "text": "text",
    "number": "number",
    "enumeration": "select",
    "booleancheckbox": "booleancheckbox",
    "date": "date",
}


def build_property_payload(
    object_name: str, field_config: Dict[str, Any], group_name: str = "gtm_properties"
) -> Dict[str, Any]:
    """
    Translate a generic field config dict into a HubSpot property creation payload.
    https://developers.hubspot.com/docs/api/crm/properties
    """
    raw_type = field_config.get("type", "string")
    hs_type = _TYPE_MAP.get(raw_type, "text")
    field_type = _FIELD_TYPE_MAP.get(hs_type, "text")

    payload: Dict[str, Any] = {
        "name": field_config["internal_name"],
        "label": field_config.get("label", field_config["internal_name"]),
        "type": hs_type,
        "fieldType": field_type,
        "groupName": field_config.get("group", group_name),
        "description": field_config.get("description", ""),
        "hidden": False,
        "hasUniqueValue": False,
    }

    if hs_type == "enumeration":
        options = field_config.get("options", [])
        payload["options"] = _build_enum_options(options)

    return payload


def _build_enum_options(options: List[Any]) -> List[Dict[str, Any]]:
    """Build HubSpot enumeration options list from string list or dict list."""
    result = []
    for i, opt in enumerate(options):
        if isinstance(opt, dict):
            result.append({
                "label": opt.get("label", str(opt.get("value", ""))),
                "value": opt.get("value", str(opt.get("label", ""))),
                "displayOrder": i,
                "hidden": False,
            })
        else:
            label = str(opt)
            value = label.lower().replace(" ", "_").replace("-", "_").replace("/", "_")
            result.append({
                "label": label,
                "value": value,
                "displayOrder": i,
                "hidden": False,
            })
    return result


def field_exists(
    internal_name: str, existing_properties: List[Dict[str, Any]]
) -> bool:
    return any(p.get("name") == internal_name for p in existing_properties)


def field_has_type_conflict(
    internal_name: str,
    required_type: str,
    existing_properties: List[Dict[str, Any]],
) -> bool:
    """Return True if the field exists but has a different HubSpot type."""
    for p in existing_properties:
        if p.get("name") == internal_name:
            existing_type = p.get("type", "")
            mapped = _TYPE_MAP.get(required_type, required_type)
            return existing_type != mapped
    return False
