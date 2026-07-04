"""Phase 4 tests: the headline moment must produce the SAME_FAMILY_AS edge live.

Rules being tested (spec §3, §4):
- SAME_FAMILY_AS never appears in seed edges (guarded in Phase 1 tests).
- memify creates SAME_FAMILY_AS for Mistake pairs that share failure_class
  BUT sit on DIFFERENT Concepts (cross-topic — that's the wow).
- Two Mistakes on the SAME Concept are not linked by memify (same-topic
  linkage is not the demo's story and would be noisy).
- memify is idempotent: running it twice does not add duplicate edges.
"""

from __future__ import annotations

from deja.commands.memify_cmd import discover_family_edges, discover_related_concepts
from deja.models.graph import Rel


def _m(node_id: str, concept: str, failure_class: str, mistake_key: str = "") -> dict:
    return {
        "id": node_id,
        "properties": {
            "type": "Mistake",
            "concept_ref": concept,
            "failure_class": failure_class,
            "mistake_key": mistake_key or node_id,
        },
    }


def test_cross_topic_shared_failure_class_gets_linked() -> None:
    m1 = _m("id-1", "mutable default arguments", "shared-mutable-state", "M1")
    m2 = _m("id-2", "async error handling", "shared-mutable-state", "M2")
    pairs = discover_family_edges([m1, m2], existing_edges=[])
    assert len(pairs) == 1
    a, b = pairs[0]
    assert {a["id"], b["id"]} == {"id-1", "id-2"}


def test_same_topic_shared_failure_class_is_not_linked() -> None:
    """Two Mistakes on the same Concept must not get SAME_FAMILY_AS.

    Same-topic linkage is not the demo story (§3 design rule).
    """
    m1 = _m("id-1", "mutable default arguments", "shared-mutable-state", "M1")
    m2 = _m("id-2", "mutable default arguments", "shared-mutable-state", "M1-dup")
    pairs = discover_family_edges([m1, m2], existing_edges=[])
    assert pairs == []


def test_different_failure_class_is_not_linked() -> None:
    m1 = _m("id-1", "async error handling", "shared-mutable-state")
    m2 = _m("id-2", "recursion", "stack-overflow")
    pairs = discover_family_edges([m1, m2], existing_edges=[])
    assert pairs == []


def test_memify_is_idempotent() -> None:
    m1 = _m("id-1", "mutable default arguments", "shared-mutable-state")
    m2 = _m("id-2", "async error handling", "shared-mutable-state")

    existing = [
        {
            "source": "id-1",
            "target": "id-2",
            "relationship_name": Rel.SAME_FAMILY_AS,
            "properties": {},
        }
    ]
    pairs = discover_family_edges([m1, m2], existing_edges=existing)
    assert pairs == []


def test_seed_state_produces_exactly_one_family_edge() -> None:
    """The exact BEFORE-state Mistakes (M1, M2 shared-mutable-state) must
    yield exactly one SAME_FAMILY_AS pair — the Scene 3 headline.
    """
    m1 = _m("id-M1", "mutable default arguments", "shared-mutable-state", "M1")
    m2 = _m("id-M2", "async error handling", "shared-mutable-state", "M2")
    pairs = discover_family_edges([m1, m2], existing_edges=[])
    assert len(pairs) == 1


def test_related_concepts_co_touched_by_session() -> None:
    """One Session touching two Concepts implies a RELATED_TO edge."""
    session = {"id": "s1", "properties": {"type": "Session"}}
    edges = [
        {"source": "s1", "target": "c1", "relationship_name": Rel.TOUCHED, "properties": {}},
        {"source": "s1", "target": "c2", "relationship_name": Rel.TOUCHED, "properties": {}},
    ]
    pairs = discover_related_concepts([session], edges)
    assert len(pairs) == 1
    assert set(pairs[0]) == {"c1", "c2"}


def test_related_concepts_idempotent() -> None:
    session = {"id": "s1", "properties": {"type": "Session"}}
    edges = [
        {"source": "s1", "target": "c1", "relationship_name": Rel.TOUCHED, "properties": {}},
        {"source": "s1", "target": "c2", "relationship_name": Rel.TOUCHED, "properties": {}},
        {"source": "c1", "target": "c2", "relationship_name": Rel.RELATED_TO, "properties": {}},
    ]
    pairs = discover_related_concepts([session], edges)
    assert pairs == []
