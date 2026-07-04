"""``deja seed`` — produce the demo BEFORE state (schema spec §6).

Locked seed contract:

  - recursion               → Skill weight 0.9, status mastered
  - mutable default args    → Skill weight 0.3, in_progress + Mistake M1
                              (failure_class = shared-mutable-state)
  - async error handling    → Skill weight 0.45, in_progress + Mistake M2
                              (failure_class = shared-mutable-state)
  - Python 2 print          → Concept deprecated=True (forget target)

Critical invariant: M1 and M2 exist but are NOT linked by SAME_FAMILY_AS.
``memify`` creates that edge live in Scene 3. Enforced in tests.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from deja.models.graph import (
    Concept,
    Feedback,
    Learner,
    Mistake,
    Rel,
    Session,
    SessionOutcome,
    Skill,
    SkillStatus,
)
from deja.store import graph_store


LEARNER_NAME = "Gajanand"
LEARNER_FOCUS = "async error handling"


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _seed_datapoints() -> tuple[
    Learner, list[Concept], list[Skill], list[Session], list[Mistake]
]:
    """Build every DataPoint the seed needs. Pure — no I/O.

    Returned in dependency order so callers can add them in that order.
    """
    now = datetime.now(timezone.utc)
    last_week = now - timedelta(days=7)
    yesterday = now - timedelta(days=1)

    # ------------------------------------------------------------------
    # Learner
    # ------------------------------------------------------------------
    learner = Learner(
        name=LEARNER_NAME,
        current_focus=LEARNER_FOCUS,
        created_at_iso=_iso(now - timedelta(days=30)),
    )

    # ------------------------------------------------------------------
    # Concepts — canonical curriculum + the deprecated forget target
    # ------------------------------------------------------------------
    concepts = [
        Concept(name="recursion", category="fundamentals", canonical=True),
        Concept(name="mutable default arguments", category="python-gotchas", canonical=True),
        Concept(name="async error handling", category="async", canonical=True),
        Concept(name="shared mutable state", category="python-gotchas", canonical=True),
        Concept(
            name="python 2 print statement",
            category="deprecated",
            canonical=True,
            deprecated=True,
        ),
    ]

    # ------------------------------------------------------------------
    # Skills — locked weights from the spec
    # ------------------------------------------------------------------
    skills = [
        Skill(
            concept_ref="recursion",
            mastery_weight=0.9,
            confidence=0.85,
            status=SkillStatus.MASTERED,
            last_practiced_iso=_iso(last_week),
        ),
        Skill(
            concept_ref="mutable default arguments",
            mastery_weight=0.3,
            confidence=0.4,
            status=SkillStatus.IN_PROGRESS,
            last_practiced_iso=_iso(last_week),
        ),
        Skill(
            concept_ref="async error handling",
            mastery_weight=0.45,
            confidence=0.5,
            status=SkillStatus.IN_PROGRESS,
            last_practiced_iso=_iso(yesterday),
        ),
        # The deprecated concept has a Skill too — it gets pruned by ``forget``.
        Skill(
            concept_ref="python 2 print statement",
            mastery_weight=0.6,
            confidence=0.7,
            status=SkillStatus.MASTERED,
            last_practiced_iso=_iso(last_week - timedelta(days=180)),
        ),
    ]

    # ------------------------------------------------------------------
    # Sessions + Mistakes — the linkable pair (M1, M2) that memify will fuse
    # ------------------------------------------------------------------
    session_a = Session(
        session_key="session-A-mutable-defaults",
        summary=(
            "Learner tried to append to a helper's default list argument across calls; "
            "state persisted between invocations. Talked through why default args "
            "are evaluated once at function definition."
        ),
        timestamp_iso=_iso(last_week),
        outcome=SessionOutcome.STRUGGLED,
        feedback=Feedback.NONE,
    )
    session_b = Session(
        session_key="session-B-async-shared-state",
        summary=(
            "Learner had two concurrent tasks mutating the same list under "
            "asyncio.gather. Explored asyncio.Lock and immutable defaults; "
            "explanation mostly landed."
        ),
        timestamp_iso=_iso(yesterday),
        outcome=SessionOutcome.MIXED,
        feedback=Feedback.NONE,
    )
    sessions = [session_a, session_b]

    m1 = Mistake(
        mistake_key="M1-default-list-reused",
        description="Default list argument reused across calls, accumulating state.",
        concept_ref="mutable default arguments",
        failure_class="shared-mutable-state",
        resolved=False,
        first_seen_session=session_a.session_key,
    )
    m2 = Mistake(
        mistake_key="M2-async-shared-mutable-object",
        description="Same mutable list mutated by concurrent asyncio tasks.",
        concept_ref="async error handling",
        failure_class="shared-mutable-state",
        resolved=False,
        first_seen_session=session_b.session_key,
    )
    mistakes = [m1, m2]

    return learner, concepts, skills, sessions, mistakes


def _explicit_edges(
    learner: Learner,
    concepts: list[Concept],
    skills: list[Skill],
    sessions: list[Session],
    mistakes: list[Mistake],
) -> list[tuple[str, str, str, dict]]:
    """Every edge from spec §3 (explicit set only). No SAME_FAMILY_AS."""
    concept_by_name = {c.name: c for c in concepts}
    session_by_key = {s.session_key: s for s in sessions}

    edges: list[tuple[str, str, str, dict]] = []

    for skill in skills:
        edges.append((str(learner.id), str(skill.id), Rel.HAS_SKILL, {}))
        concept = concept_by_name[skill.concept_ref]
        edges.append((str(skill.id), str(concept.id), Rel.OF_CONCEPT, {}))

    session_a, session_b = sessions
    edges.append(
        (
            str(session_a.id),
            str(concept_by_name["mutable default arguments"].id),
            Rel.TOUCHED,
            {},
        )
    )
    edges.append(
        (
            str(session_b.id),
            str(concept_by_name["async error handling"].id),
            Rel.TOUCHED,
            {},
        )
    )

    for mistake in mistakes:
        session = session_by_key[mistake.first_seen_session]
        edges.append((str(session.id), str(mistake.id), Rel.REVEALED, {}))
        concept = concept_by_name[mistake.concept_ref]
        edges.append(
            (str(mistake.id), str(concept.id), Rel.INDICATES_GAP_IN, {})
        )

    return edges


async def seed(wipe_first: bool = True) -> dict:
    """Run the seed. Returns a summary dict for the CLI to print."""
    await graph_store.ensure_setup()
    if wipe_first:
        await graph_store.wipe()

    learner, concepts, skills, sessions, mistakes = _seed_datapoints()
    all_nodes = [learner, *concepts, *skills, *sessions, *mistakes]
    await graph_store.add_nodes(all_nodes)

    edges = _explicit_edges(learner, concepts, skills, sessions, mistakes)
    await graph_store.add_edges(edges)

    return {
        "learner": learner.name,
        "concepts": [c.name for c in concepts],
        "skills": {s.concept_ref: s.mastery_weight for s in skills},
        "sessions": [s.session_key for s in sessions],
        "mistakes": [m.mistake_key for m in mistakes],
        "edges_added": len(edges),
        "same_family_as_edges": 0,  # invariant — memify creates these
    }
