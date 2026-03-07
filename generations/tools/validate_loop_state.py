#!/usr/bin/env python3
"""Validation script to enforce schema compliance before loop increment.

Validates loop state against defined criteria and exits with:
- 0 on valid state
- 1 on invalid state
"""

import json
import sys
from pathlib import Path


def load_criteria(criteria_path: str) -> dict | None:
    """Load and parse the criteria JSON file."""
    path = Path(criteria_path)
    if not path.exists():
        print(f"ERROR: Criteria file not found: {criteria_path}")
        return None
    
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in criteria file: {e}")
        return None


def validate_schema(data: dict) -> tuple[bool, list[str]]:
    """Validate that data conforms to expected schema.
    
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    
    if not isinstance(data, dict):
        errors.append("Root must be a dictionary")
        return False, errors
    
    if "ship_rules" not in data:
        errors.append("Missing required field: 'ship_rules'")
        return False, errors
    
    if not isinstance(data["ship_rules"], list):
        errors.append("'ship_rules' must be a list")
        return False, errors
    
    for i, rule in enumerate(data["ship_rules"]):
        if not isinstance(rule, dict):
            errors.append(f"Rule {i}: must be a dictionary")
            continue
        
        required_fields = ["id", "description", "enforcement"]
        for field in required_fields:
            if field not in rule:
                errors.append(f"Rule {i}: missing required field '{field}'")
            elif not isinstance(rule[field], str):
                errors.append(f"Rule {i}: '{field}' must be a string")
    
    return len(errors) == 0, errors


def validate_loop_state(criteria_path: str) -> bool:
    """Validate loop state against criteria schema.
    
    Returns:
        True if valid, False otherwise
    """
    criteria = load_criteria(criteria_path)
    if criteria is None:
        return False
    
    is_valid, errors = validate_schema(criteria)
    
    if not is_valid:
        for error in errors:
            print(f"VALIDATION ERROR: {error}")
        return False
    
    print("Validation passed: schema compliance confirmed")
    return True


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        criteria_path = "criteria.json"
    else:
        criteria_path = sys.argv[1]
    
    if validate_loop_state(criteria_path):
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
