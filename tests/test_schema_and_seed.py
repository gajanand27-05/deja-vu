"""Phase 1 tests: schema + seed integrity.

These tests do not touch cognee's DB — they exercise the pure pieces (Pydantic
models, seed datapoint builder, edge builder) so they run fast and prove the
spec invariants without an LLM key.

The full end-to-end seed against cognee's graph engine is validated by
``deja seed`` at runtime (Phase 1 acceptance is the CLI table).
"""

from __future__ import annotations

from deja.commands.seed_cmd import _explicit_edges, _seed_datapoints
from deja.models.graph import Concept, Learner, Mistake, Rel, Session, Skill, SkillStatus


def test_schema_split_holds() -> None:
    """Skill and Concept must be different classes — the personalized story dies otherwise."""
    assert Skill is not Concept
    assert not issubclass(Skill, Concept)


def test_seed_produces_expected_before_state() -> None:
    learner, concepts, skills, sessions, mistakes = _seed_datapoints()

    assert isinstance(learner, Learner)
    assert learner.current_focus == "async error handling"

    concept_names = {c.name for c in concepts}
    assert concept_names == {
        "recursion",
        "mutable default arguments",
        "async error handling",
        "shared mutable state",
        "python 2 print statement",
    }
    assert any(c.deprecated for c in concepts), "need a deprecated concept for forget"

    weights = {s.concept_ref: s.mastery_weight for s in skills}
    assert weights["recursion"] == 0.9
    assert weights["mutable default arguments"] == 0.3
    assert weights["async error handling"] == 0.45

    statuses = {s.concept_ref: s.status for s in skills}
    assert statuses["recursion"] == SkillStatus.MASTERED
    assert statuses["mutable default arguments"] == SkillStatus.IN_PROGRESS
    assert statuses["async error handling"] == SkillStatus.IN_PROGRESS

    assert len(sessions) == 2
    assert len(mistakes) == 2

    # Failure_class is the memify hinge.
    for m in mistakes:
        assert m.failure_class == "shared-mutable-state"
        assert m.resolved is False

    # Mistakes live under DIFFERENT concepts — that's what makes memify's link
    # cross-topic and impressive.
    m_concepts = {m.concept_ref for m in mistakes}
    assert len(m_concepts) == 2


def test_seed_edges_are_explicit_only() -> None:
    """SAME_FAMILY_AS must not appear in seed edges — memify creates it live (spec §3)."""
    learner, concepts, skills, sessions, mistakes = _seed_datapoints()
    edges = _explicit_edges(learner, concepts, skills, sessions, mistakes)

    rels = {rel for _, _, rel, _ in edges}
    assert Rel.SAME_FAMILY_AS not in rels
    assert Rel.RELATED_TO not in rels

    # And every rel used *must* be from the explicit set.
    assert rels.issubset(Rel.EXPLICIT), f"non-explicit edge in seed: {rels - Rel.EXPLICIT}"


def test_every_explicit_edge_type_is_used() -> None:
    """Sanity check that we're actually exercising the schema, not shipping half of it."""
    learner, concepts, skills, sessions, mistakes = _seed_datapoints()
    edges = _explicit_edges(learner, concepts, skills, sessions, mistakes)

    used = {rel for _, _, rel, _ in edges}
    required = {
        Rel.HAS_SKILL,
        Rel.OF_CONCEPT,
        Rel.TOUCHED,
        Rel.REVEALED,
        Rel.INDICATES_GAP_IN,
    }
    missing = required - used
    assert not missing, f"seed skipped required explicit edges: {missing}"


def test_learner_id_is_deterministic() -> None:
    """Deterministic ids let memify + forget find nodes by identity across runs."""
    l1 = Learner(name="Gajanand")
    l2 = Learner(name="Gajanand")
    assert l1.id == l2.id
