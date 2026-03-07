from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_schema(schema_path: str | Path) -> dict | None:
    """Load and parse the state schema JSON file."""
    path = Path(schema_path)
    if not path.exists():
        return None
    
    with open(path, 'r') as f:
        return json.load(f)


def validate_state(data: dict[str, Any], schema: dict) -> tuple[bool, list[str]]:
    """Validate state data against schema.
    
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    
    if not isinstance(data, dict):
        errors.append("Root must be a dictionary")
        return False, errors
    
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    
    for field in required:
        if field not in data:
            errors.append(f"Missing required field: '{field}'")
    
    for field, field_schema in properties.items():
        if field not in data:
            continue
        
        value = data[field]
        field_type = field_schema.get("type")
        
        if field_type == "integer" and not isinstance(value, int):
            errors.append(f"Field '{field}' must be an integer")
        elif field_type == "string":
            if not isinstance(value, str):
                errors.append(f"Field '{field}' must be a string")
            elif "minLength" in field_schema and len(value) < field_schema["minLength"]:
                errors.append(f"Field '{field}' must be at least {field_schema['minLength']} characters")
        elif field_type == "number" and not isinstance(value, (int, float)):
            errors.append(f"Field '{field}' must be a number")
        elif field_type == "object" and not isinstance(value, dict):
            errors.append(f"Field '{field}' must be an object")
        elif field_type == "array" and not isinstance(value, list):
            errors.append(f"Field '{field}' must be an array")
        
        if field_type == "integer" and isinstance(value, int):
            if "minimum" in field_schema and value < field_schema["minimum"]:
                errors.append(f"Field '{field}' must be >= {field_schema['minimum']}")
            if "maximum" in field_schema and value > field_schema["maximum"]:
                errors.append(f"Field '{field}' must be <= {field_schema['maximum']}")
    
    return len(errors) == 0, errors


def validate_loop_state(data: dict[str, Any], schema_path: str | Path) -> tuple[bool, list[str]]:
    """Validate loop state against schema file.
    
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    schema = load_schema(schema_path)
    if schema is None:
        return False, [f"Schema not found: {schema_path}"]
    
    return validate_state(data, schema)
