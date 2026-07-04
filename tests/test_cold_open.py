"""Phase 2 tests: the three cold-open lines are derived from the graph, not hardcoded."""

from __future__ import annotations

from deja.commands.start_cmd import _derive, render_cold_open
from deja.models.graph import Concept, Learner, Mistake, Session, Skill, SkillStatus


def _snapshot_from_seed_style() -> tuple[list[dict], list[dict]]:
    """Hand-built graph fixture matching the seed BEFORE state."""
    learner = Learner(name="Gajanand", current_focus="async error handling")
    recursion = Concept(name="recursion", category="fundamentals")
    mut_defaults = Concept(name="mutable default arguments", category="python-gotchas")
    async_err = Concept(name="async error handling", category="async")
    deprecated = Concept(name="python 2 print statement", category="deprecated", deprecated=True)

    s_recursion = Skill(
        concept_ref="recursion", mastery_weight=0.9, status=SkillStatus.MASTERED
    )
    s_mut = Skill(
        concept_ref="mutable default arguments",
        mastery_weight=0.3,
        status=SkillStatus.IN_PROGRESS,
    )
    s_async = Skill(
        concept_ref="async error handling",
        mastery_weight=0.45,
        status=SkillStatus.IN_PROGRESS,
    )
    s_dep = Skill(
        concept_ref="python 2 print statement",
        mastery_weight=0.6,
        status=SkillStatus.MASTERED,
    )

    m1 = Mistake(
        mistake_key="M1",
        description="Default list reused across calls.",
        concept_ref="mutable default arguments",
        failure_class="shared-mutable-state",
    )
    m2 = Mistake(
        mistake_key="M2",
        description="Same mutable list across concurrent tasks.",
        concept_ref="async error handling",
        failure_class="shared-mutable-state",
    )

    def as_node(dp) -> dict:
        props = dp.model_dump()
        props["type"] = type(dp).__name__
        # Enum → str
        for k, v in list(props.items()):
            if hasattr(v, "value"):
                props[k] = v.value
        return {"id": str(dp.id), "properties": props}

    nodes = [
        as_node(learner),
        as_node(recursion),
        as_node(mut_defaults),
        as_node(async_err),
        as_node(deprecated),
        as_node(s_recursion),
        as_node(s_mut),
        as_node(s_async),
        as_node(s_dep),
        as_node(m1),
        as_node(m2),
    ]
    return nodes, []


def test_cold_open_picks_mastered_over_deprecated_mastered() -> None:
    """Deprecated concept's mastered Skill (weight 0.6) must not steal the mastered slot from recursion (0.9)."""
    nodes, edges = _snapshot_from_seed_style()
    cold = _derive(nodes, edges)
    assert cold.mastered_topic == "recursion"


def test_cold_open_picks_lowest_weight_unresolved_mistake() -> None:
    nodes, edges = _snapshot_from_seed_style()
    cold = _derive(nodes, edges)
    # mutable-defaults skill weight 0.3 < async 0.45, so mut-defaults wins.
    assert cold.stumbled_topic == "mutable default arguments"
    assert cold.stumbled_mistake is not None


def test_cold_open_reads_current_focus_from_learner() -> None:
    nodes, edges = _snapshot_from_seed_style()
    cold = _derive(nodes, edges)
    assert cold.current_focus == "async error handling"


def test_cold_open_greeting_mentions_all_three_topics() -> None:
    nodes, edges = _snapshot_from_seed_style()
    cold = _derive(nodes, edges)
    text = render_cold_open(cold)
    assert "recursion" in text
    assert "mutable default arguments" in text
    assert "async error handling" in text


def test_cold_open_empty_graph_falls_back() -> None:
    cold = _derive([], [])
    text = render_cold_open(cold)
    assert "deja seed" in text
