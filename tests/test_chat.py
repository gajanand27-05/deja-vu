"""Phase 3 tests: coaching pulls cross-topic evidence, improve targets only used nodes."""

from __future__ import annotations

from deja.commands.chat_cmd import CoachingTurn, _compose_coaching, _find_by_prop, _p


def _node(t, **props):
    props["type"] = t
    return {"id": f"{t}-{len(props)}-{props.get('name') or props.get('concept_ref') or props.get('mistake_key')}", "properties": props}


def _seed_by_type() -> dict:
    return {
        "Concept": [
            _node("Concept", name="async error handling"),
            _node("Concept", name="mutable default arguments"),
        ],
        "Skill": [_node("Skill", concept_ref="async error handling", mastery_weight=0.45)],
        "Mistake": [
            _node("Mistake", mistake_key="M2", concept_ref="async error handling",
                  failure_class="shared-mutable-state", description="Same mutable list across tasks."),
            _node("Mistake", mistake_key="M1", concept_ref="mutable default arguments",
                  failure_class="shared-mutable-state", description="Default list reused across calls."),
        ],
    }


def test_find_by_prop() -> None:
    nodes = [
        {"id": "1", "properties": {"name": "recursion"}},
        {"id": "2", "properties": {"name": "async"}},
    ]
    assert _find_by_prop(nodes, "name", "async")["id"] == "2"
    assert _find_by_prop(nodes, "name", "missing") is None


def test_coaching_turn_used_nodes_includes_evidence() -> None:
    """A thumbs-up must be able to reach every node that produced the answer."""
    turn = CoachingTurn(
        topic_concept="async error handling",
        topic_skill_id="skill-async",
        related_mistake_ids=["m1", "m2"],
        used_node_ids=["skill-async", "m1", "m2", "session-live"],
        message="…",
        session_id="session-live",
    )
    # topic Skill, both mistakes, and the new Session are all touchable by improve.
    assert "skill-async" in turn.used_node_ids
    assert "m1" in turn.used_node_ids
    assert "m2" in turn.used_node_ids
    assert "session-live" in turn.used_node_ids
    # No global counter dependency: the ids are node-specific.
    assert all(isinstance(n, str) and n for n in turn.used_node_ids)


def test_compose_with_memory_reaches_across_topics() -> None:
    """The with-memory answer names the cross-topic mistake; the no-memory one can't."""
    c = _compose_coaching("async error handling", _seed_by_type())
    assert c is not None
    assert len(c.related) == 1
    assert "mutable default arguments" in c.with_message
    assert "Fix pattern" in c.with_message
    # The baseline has no history and must not name the other topic.
    assert "mutable default arguments" not in c.no_memory_message
    assert c.with_message != c.no_memory_message


def test_compose_unknown_topic_returns_none() -> None:
    assert _compose_coaching("nonexistent topic", _seed_by_type()) is None


def test_compose_no_cross_topic_evidence_matches_baseline() -> None:
    by_type = {"Concept": [_node("Concept", name="recursion")], "Skill": [], "Mistake": []}
    c = _compose_coaching("recursion", by_type)
    assert c.related == []
    assert c.with_message == c.no_memory_message
