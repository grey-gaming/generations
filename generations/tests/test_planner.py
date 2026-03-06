from __future__ import annotations

from pathlib import Path

from generations.config import AppConfig
from generations.journal.store import JournalStore
from generations.memory.store import MemoryStore
from generations.models import BlockPlan, LongTermVisionRecord, RetrospectiveRecord
from generations.planner import Planner


class StubModel:
    def plan_long_term_vision(self, seed, loop_counter, memory, recent_entries, *, current_version):
        return (
            LongTermVisionRecord(
                version=current_version + 1,
                generated_at="2026-03-06T00:00:00Z",
                refined_at_loop=loop_counter,
                index_summary="Founding vision.",
                pillars={
                    "self": {
                        "name": "self",
                        "summary": "Build the autonomous platform.",
                        "purpose": "Platform purpose.",
                        "good_end_state": "Reliable autonomous studio.",
                        "failure_modes": ["drift"],
                        "relationships": ["supports the game"],
                        "content": "word " * 500,
                    },
                    "game": {
                        "name": "game",
                        "summary": "Build the game.",
                        "purpose": "Game purpose.",
                        "good_end_state": "Playable prototype.",
                        "failure_modes": ["stays abstract"],
                        "relationships": ["proves the platform"],
                        "content": "word " * 500,
                    },
                    "monetization_platform": {
                        "name": "monetization_platform",
                        "summary": "Build honest support surfaces.",
                        "purpose": "Monetization purpose.",
                        "good_end_state": "Transparent support layer.",
                        "failure_modes": ["outruns evidence"],
                        "relationships": ["follows product proof"],
                        "content": "word " * 500,
                    },
                },
                change_summary="Initial long-term vision created.",
            ),
            {"provider": "stub"},
        )

    def plan_initial_self_block(self, seed, loop_counter, memory, vision):
        return (
            BlockPlan(
                block_id=1,
                planning_loop=loop_counter,
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
            ),
            {"provider": "stub"},
        )

    def write_retrospective(self, seed, loop_counter, memory, prior_block, block_entries):
        return (
            RetrospectiveRecord(
                block_id=int(prior_block["block_id"]),
                retrospective_loop=loop_counter,
                primary_pillar=prior_block["primary_pillar"],
                execution_range=tuple(prior_block["execution_range"]),
                intended_outcomes=list(prior_block["target_outcomes"]),
                actual_outcomes=["Outcome landed"],
                wins=["Stayed coherent"],
                failures=[],
                stalls=[],
                surprises=[],
                metric_reflection={"helpful": ["review_quality"], "misleading": []},
                carry_forward=["Keep the block focus"],
                change_next_time=["Choose the next pillar deliberately"],
                summary="The block stayed coherent.",
            ),
            {"provider": "stub"},
        )

    def plan_block(self, seed, loop_counter, memory, vision, latest_retro, *, block_id):
        return (
            BlockPlan(
                block_id=block_id,
                planning_loop=loop_counter,
                execution_range=(loop_counter + 1, loop_counter + 9),
                primary_pillar="game",
                why_this_pillar_now="The platform is ready for game focus.",
                target_outcomes=["Start game execution"],
                sub_goals=["Prototype one system"],
                allowed_support_work=["Validation support"],
                explicit_non_goals=["Monetization experiments"],
                success_signals=["Executable game artifact"],
                failure_signals=["Only docs"],
                expected_artifacts=["Game code"],
                metrics_to_watch=["game_progress"],
                risks=["Shallow prototype"],
                review_focus=["Executable proof"],
            ),
            {"provider": "stub"},
        )


def test_planner_writes_vision_and_initial_block(tmp_path: Path) -> None:
    config = AppConfig.from_root(tmp_path)
    journal = JournalStore(config.journal_path)
    memory = MemoryStore(config.memory_path)
    planner = Planner(config, StubModel(), journal, memory)

    vision, _ = planner.ensure_long_term_vision("seed", 0)
    assert vision is not None
    assert vision.version == 1
    assert (tmp_path / "generations" / "vision" / "vision_v001_self.md").exists()

    plan, retrospective, _ = planner.ensure_block_material("seed", 1)
    assert retrospective is None
    assert plan is not None
    assert plan.primary_pillar == "self"
    assert (tmp_path / "generations" / "planning_docs" / "block_001_plan.md").exists()


def test_planner_writes_retrospective_and_next_block(tmp_path: Path) -> None:
    config = AppConfig.from_root(tmp_path)
    journal = JournalStore(config.journal_path)
    memory = MemoryStore(config.memory_path)
    planner = Planner(config, StubModel(), journal, memory)
    planner.ensure_long_term_vision("seed", 0)
    planner.ensure_block_material("seed", 1)

    plan, retrospective, _ = planner.ensure_block_material("seed", 11)
    assert retrospective is not None
    assert plan is not None
    assert plan.primary_pillar == "game"
    assert retrospective.summary == "The block stayed coherent."


def test_planner_sanitizes_path_like_artifacts(tmp_path: Path) -> None:
    config = AppConfig.from_root(tmp_path)
    journal = JournalStore(config.journal_path)
    memory = MemoryStore(config.memory_path)
    planner = Planner(config, StubModel(), journal, memory)
    planner.ensure_long_term_vision("seed", 0)

    dirty_plan = BlockPlan(
        block_id=1,
        planning_loop=1,
        execution_range=(2, 10),
        primary_pillar="self",
        why_this_pillar_now="Tighten generations/platform/validation.py and clarify docs/platform_architecture.md",
        target_outcomes=["Strengthen platform/loop_manager.py discipline"],
        sub_goals=["Improve website/journey_generator.py outputs"],
        allowed_support_work=["Record memory/loop_001.json snapshots"],
        explicit_non_goals=["Do not chase ci/workflow.yml work yet"],
        success_signals=["Cleaner generations/website/journey.html behavior"],
        failure_signals=["More docs/platform_architecture.md drift"],
        expected_artifacts=["generations/platform/validation.py", "memory/state_schema.json"],
        metrics_to_watch=["review_quality"],
        risks=["platform/loop_manager.py drift"],
        review_focus=["website/journey_generator.py clarity"],
    )

    cleaned = planner._sanitize_block_plan(dirty_plan)
    all_text = " ".join(
        [
            cleaned.why_this_pillar_now,
            *cleaned.target_outcomes,
            *cleaned.sub_goals,
            *cleaned.allowed_support_work,
            *cleaned.explicit_non_goals,
            *cleaned.success_signals,
            *cleaned.failure_signals,
            *cleaned.expected_artifacts,
            *cleaned.risks,
            *cleaned.review_focus,
        ]
    )
    assert "platform/" not in all_text
    assert "website/" not in all_text
    assert "memory/" not in all_text
    assert "generations/" not in all_text
