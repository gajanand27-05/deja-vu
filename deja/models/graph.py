"""Déjà graph model — Pydantic DataPoint subclasses matching the schema spec.

Design principle (from the schema spec): every node and edge exists to make the
before/after ``memify`` re-organization visible and truthful. If a field doesn't
serve remember / recall / improve / memify / forget, it isn't here.

Two non-negotiable design decisions this schema encodes:

1. **Skill is separate from Concept.** Concept is objective and shared;
   Skill is *this learner's* mutable, weighted relationship to a Concept.
2. **Explicit vs. inferred edges.** ``memify`` creates the wow-moment
   ``Mistake -SAME_FAMILY_AS-> Mistake`` edge live — it must never appear
   in the seed. Enforced in seeding + tested.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from cognee.infrastructure.engine import DataPoint
from cognee.infrastructure.engine.models.FieldAnnotations import Dedup, Embeddable


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SkillStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    MASTERED = "mastered"
    DECAYING = "decaying"


class SessionOutcome(str, Enum):
    SOLVED = "solved"
    STRUGGLED = "struggled"
    MIXED = "mixed"


class Feedback(str, Enum):
    UP = "up"
    DOWN = "down"
    NONE = "none"


# ---------------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------------


class Learner(DataPoint):
    """Root of the graph. Single user in the demo."""

    name: Annotated[str, Embeddable(), Dedup()]
    current_focus: str = ""  # drives the cold-open "you'd just started X" line
    created_at_iso: str = datetime.now(timezone.utc).isoformat()


class Concept(DataPoint):
    """Objective, teachable idea. Shared across learners."""

    name: Annotated[str, Embeddable(), Dedup()]
    category: str = "general"
    canonical: bool = True
    deprecated: bool = False  # true marks a forget() target


class Skill(DataPoint):
    """This learner's mastery of one Concept. The star mutable node.

    ``mastery_weight`` is what visibly thickens or thins during memify /
    improve / forget. Identity is the concept it points at — one Skill per
    Concept per learner (single-learner demo).
    """

    concept_ref: Annotated[str, Embeddable(), Dedup()]  # Concept.name
    mastery_weight: float = 0.5  # 0.0..1.0
    confidence: float = 0.5  # 0.0..1.0
    status: SkillStatus = SkillStatus.IN_PROGRESS
    last_practiced_iso: str = datetime.now(timezone.utc).isoformat()


class Session(DataPoint):
    """One coaching interaction. Append-only."""

    session_key: Annotated[str, Dedup()]  # stable id we assign
    summary: Annotated[str, Embeddable()]
    timestamp_iso: str = datetime.now(timezone.utc).isoformat()
    outcome: SessionOutcome = SessionOutcome.MIXED
    feedback: Feedback = Feedback.NONE


class Mistake(DataPoint):
    """A specific error the learner made. The node memify links across topics.

    ``failure_class`` is the magic field: two Mistakes under *different*
    Concepts sharing a failure_class are what memify links into a family.
    """

    mistake_key: Annotated[str, Dedup()]  # stable id we assign
    description: Annotated[str, Embeddable()]
    concept_ref: str  # Concept.name this mistake sits under
    failure_class: str  # e.g. "shared-mutable-state"
    resolved: bool = False
    first_seen_session: str = ""  # Session.session_key


# ---------------------------------------------------------------------------
# Edge relationship names (spec §3)
# ---------------------------------------------------------------------------


class Rel:
    """String constants for edge relationship names.

    Explicit (written by ``remember``) vs. inferred (created by ``memify``) is
    documented here so future readers don't accidentally seed the inferred set.
    """

    # Explicit
    HAS_SKILL = "HAS_SKILL"                     # Learner -> Skill
    OF_CONCEPT = "OF_CONCEPT"                   # Skill -> Concept
    TOUCHED = "TOUCHED"                         # Session -> Concept
    REVEALED = "REVEALED"                       # Session -> Mistake
    INDICATES_GAP_IN = "INDICATES_GAP_IN"       # Mistake -> Concept
    PREREQUISITE_OF = "PREREQUISITE_OF"         # Concept -> Concept

    EXPLICIT = frozenset(
        {HAS_SKILL, OF_CONCEPT, TOUCHED, REVEALED, INDICATES_GAP_IN, PREREQUISITE_OF}
    )

    # Inferred (memify only — must not be in seed)
    SAME_FAMILY_AS = "SAME_FAMILY_AS"           # Mistake -> Mistake
    RELATED_TO = "RELATED_TO"                   # Concept -> Concept

    INFERRED = frozenset({SAME_FAMILY_AS, RELATED_TO})


__all__ = [
    "Concept",
    "Feedback",
    "Learner",
    "Mistake",
    "Rel",
    "Session",
    "SessionOutcome",
    "Skill",
    "SkillStatus",
]
