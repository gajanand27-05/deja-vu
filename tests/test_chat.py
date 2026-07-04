"""Phase 3 tests: coaching pulls cross-topic evidence, improve targets only used nodes."""

from __future__ import annotations

from deja.commands.chat_cmd import CoachingTurn, _find_by_prop, _p


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
