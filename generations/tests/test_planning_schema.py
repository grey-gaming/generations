from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import ValidationError, validate

from generations.models import BlockPlan


BLOCK_PLAN_SCHEMA = {
    "type": "object",
    "required": [
        "block_id",
        "planning_loop",
        "execution_range",
        "primary_pillar",
        "why_this_pillar_now",
        "target_outcomes",
        "sub_goals",
        "allowed_support_work",
        "explicit_non_goals",
        "success_signals",
        "failure_signals",
        "expected_artifacts",
        "metrics_to_watch",
        "risks",
        "review_focus",
    ],
    "properties": {
        "block_id": {"type": "integer"},
        "planning_loop": {"type": "integer"},
        "execution_range": {
            "type": "array",
            "items": {"type": "integer"},
            "minItems": 2,
            "maxItems": 2,
        },
        "primary_pillar": {
            "type": "string",
            "enum": ["self", "game", "monetization_platform"],
        },
        "why_this_pillar_now": {"type": "string"},
        "target_outcomes": {"type": "array", "items": {"type": "string"}},
        "sub_goals": {"type": "array", "items": {"type": "string"}},
        "allowed_support_work": {"type": "array", "items": {"type": "string"}},
        "explicit_non_goals": {"type": "array", "items": {"type": "string"}},
        "success_signals": {"type": "array", "items": {"type": "string"}},
        "failure_signals": {"type": "array", "items": {"type": "string"}},
        "expected_artifacts": {"type": "array", "items": {"type": "string"}},
        "metrics_to_watch": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "review_focus": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
}


def test_valid_block_plan_json_passes_schema():
    valid_plan = {
        "block_id": 1,
        "planning_loop": 1,
        "execution_range": [2, 10],
        "primary_pillar": "self",
        "why_this_pillar_now": "Platform first.",
        "target_outcomes": ["Clarify planning"],
        "sub_goals": ["Improve planning"],
        "allowed_support_work": ["Website visibility"],
        "explicit_non_goals": ["Game implementation"],
        "success_signals": ["Cleaner plans"],
        "failure_signals": ["No-op loops"],
        "expected_artifacts": ["Planner changes"],
        "metrics_to_watch": ["review_quality"],
        "risks": ["Meta drift"],
        "review_focus": ["Platform clarity"],
    }
    validate(instance=valid_plan, schema=BLOCK_PLAN_SCHEMA)


def test_block_plan_model_output_passes_schema():
    plan = BlockPlan(
        block_id=1,
        planning_loop=1,
        execution_range=(2, 10),
        primary_pillar="self",
        why_this_pillar_now="Platform first.",
        target_outcomes=["Clarify planning"],
        sub_goals=["Improve planning"],
        allowed_support_work=["Website visibility"],
        explicit_non_goals=["Game implementation"],
        success_signals=["Cleaner plans"],
        failure_signals=["No-op loops"],
        expected_artifacts=["Planner changes"],
        metrics_to_watch=["review_quality"],
        risks=["Meta drift"],
        review_focus=["Platform clarity"],
    )
    validate(instance=plan.as_dict(), schema=BLOCK_PLAN_SCHEMA)


def test_block_plan_missing_required_field_fails_schema():
    invalid_plan = {
        "block_id": 1,
        "planning_loop": 1,
        "execution_range": [2, 10],
        "primary_pillar": "self",
        "why_this_pillar_now": "Platform first.",
        "target_outcomes": ["Clarify planning"],
        "sub_goals": ["Improve planning"],
        "allowed_support_work": ["Website visibility"],
        "explicit_non_goals": ["Game implementation"],
        "success_signals": ["Cleaner plans"],
        "failure_signals": ["No-op loops"],
        "expected_artifacts": ["Planner changes"],
        "metrics_to_watch": ["review_quality"],
        "review_focus": ["Platform clarity"],
    }
    with pytest.raises(ValidationError):
        validate(instance=invalid_plan, schema=BLOCK_PLAN_SCHEMA)


def test_block_plan_invalid_enum_value_fails_schema():
    invalid_plan = {
        "block_id": 1,
        "planning_loop": 1,
        "execution_range": [2, 10],
        "primary_pillar": "invalid_pillar",
        "why_this_pillar_now": "Platform first.",
        "target_outcomes": ["Clarify planning"],
        "sub_goals": ["Improve planning"],
        "allowed_support_work": ["Website visibility"],
        "explicit_non_goals": ["Game implementation"],
        "success_signals": ["Cleaner plans"],
        "failure_signals": ["No-op loops"],
        "expected_artifacts": ["Planner changes"],
        "metrics_to_watch": ["review_quality"],
        "risks": ["Meta drift"],
        "review_focus": ["Platform clarity"],
    }
    with pytest.raises(ValidationError):
        validate(instance=invalid_plan, schema=BLOCK_PLAN_SCHEMA)


def test_block_plan_invalid_type_fails_schema():
    invalid_plan = {
        "block_id": "one",
        "planning_loop": 1,
        "execution_range": [2, 10],
        "primary_pillar": "self",
        "why_this_pillar_now": "Platform first.",
        "target_outcomes": ["Clarify planning"],
        "sub_goals": ["Improve planning"],
        "allowed_support_work": ["Website visibility"],
        "explicit_non_goals": ["Game implementation"],
        "success_signals": ["Cleaner plans"],
        "failure_signals": ["No-op loops"],
        "expected_artifacts": ["Planner changes"],
        "metrics_to_watch": ["review_quality"],
        "risks": ["Meta drift"],
        "review_focus": ["Platform clarity"],
    }
    with pytest.raises(ValidationError):
        validate(instance=invalid_plan, schema=BLOCK_PLAN_SCHEMA)


def test_block_plan_empty_arrays_pass_schema():
    plan = BlockPlan(
        block_id=1,
        planning_loop=1,
        execution_range=(2, 10),
        primary_pillar="self",
        why_this_pillar_now="Platform first.",
        target_outcomes=[],
        sub_goals=[],
        allowed_support_work=[],
        explicit_non_goals=[],
        success_signals=[],
        failure_signals=[],
        expected_artifacts=[],
        metrics_to_watch=[],
        risks=[],
        review_focus=[],
    )
    validate(instance=plan.as_dict(), schema=BLOCK_PLAN_SCHEMA)
