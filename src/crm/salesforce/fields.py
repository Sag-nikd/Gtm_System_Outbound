from __future__ import annotations

from typing import Any, Dict, List

# Salesforce custom field API names follow the __c suffix convention.
# This module translates generic field configs into Salesforce field metadata dicts
# suitable for Tooling API or Metadata API deployment.

_SF_TYPE_MAP: Dict[str, str] = {
    "string": "Text",
    "text": "Text",
    "number": "Number",
    "enumeration": "Picklist",
    "bool": "Checkbox",
    "date": "Date",
    "url": "URL",
    "textarea": "LongTextArea",
}


def build_field_metadata(field_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a Salesforce CustomField metadata dict from a generic field config.
    Used for Tooling API deployment or dry-run output.

    Reference: https://developer.salesforce.com/docs/atlas.en-us.api_meta.meta/api_meta/meta_customfield.htm
    """
    raw_type = field_config.get("type", "string")
    sf_type = _SF_TYPE_MAP.get(raw_type, "Text")

    metadata: Dict[str, Any] = {
        "fullName": field_config["internal_name"],
        "label": field_config.get("label", field_config["internal_name"]),
        "type": sf_type,
        "required": False,
        "trackFeedHistory": False,
        "description": field_config.get("description", ""),
    }

    if sf_type == "Text":
        metadata["length"] = field_config.get("length", 255)
    elif sf_type == "Number":
        metadata["precision"] = field_config.get("precision", 5)
        metadata["scale"] = field_config.get("scale", 2)
    elif sf_type == "LongTextArea":
        metadata["length"] = field_config.get("length", 32768)
        metadata["visibleLines"] = 5
    elif sf_type == "Picklist":
        options = field_config.get("options", [])
        metadata["valueSet"] = {
            "valueSetDefinition": {
                "sorted": False,
                "value": [
                    {
                        "fullName": str(opt),
                        "label": str(opt),
                        "default": False,
                    }
                    for opt in options
                ],
            }
        }
    elif sf_type == "Checkbox":
        metadata["defaultValue"] = field_config.get("default", False)

    return metadata


def field_exists(
    internal_name: str, existing_fields: List[Dict[str, Any]]
) -> bool:
    """Check if a field with this API name already exists on the object."""
    return any(
        f.get("name") == internal_name or f.get("fullName") == internal_name
        for f in existing_fields
    )


def field_has_type_conflict(
    internal_name: str,
    required_type: str,
    existing_fields: List[Dict[str, Any]],
) -> bool:
    """Return True if field exists but type differs from required."""
    sf_required = _SF_TYPE_MAP.get(required_type, "Text")
    for f in existing_fields:
        name = f.get("name") or f.get("fullName", "")
        if name == internal_name:
            existing_type = f.get("type", f.get("fieldType", ""))
            return existing_type.lower() != sf_required.lower()
    return False
