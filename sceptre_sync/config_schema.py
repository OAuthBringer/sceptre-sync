"""
Configuration schema for the parameter sync utility.

This module defines the expected structure and validation rules for
the configuration files used by the parameter sync utility.
"""

import jsonschema
from typing import Dict, Any


CONFIG_SCHEMA = {
    "type": "object",
    "required": ["template_patterns"],
    "properties": {
        "template_patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["pattern", "sync_params"],
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern to match file paths"
                    },
                    "sync_params": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of parameters to synchronize"
                    }
                }
            }
        }
    }
}


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate the configuration against the schema.

    Args:
        config: Configuration dictionary to validate

    Returns:
        True if valid, raises jsonschema.ValidationError otherwise
    """
    jsonschema.validate(instance=config, schema=CONFIG_SCHEMA)
    return True
