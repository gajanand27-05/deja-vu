"""``deja chat`` — Scene 2 coaching loop with thumbs-up feedback.

Design goals from the demo script:

- The response must reach across history: when the user asks about async, the
  mentor pulls a Mistake from a *different* Concept that shares the same
  ``failure_class``. That's the "graph reasoning, not keyword match" beat.
- Thumbs-up feeds ``improve`` against the *specific* nodes used to produce the
  answer, not a global counter (spec §7 gotcha).

The prose is generated deterministically from graph facts so the demo is
rehearsable without an LLM call. If ``LLM_API_KEY`` is set we still write the
Session via the graph so ``recall`` and ``memify`` see it — the LLM's role is
prose, not truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from deja.models.graph import (
    Concept,
    Feedback,
    Learner,
    Mistake,
    Rel,
    Session,
    SessionOutcome,
    Skill,
)
from deja.store import graph_store
from deja.store.search import save_interaction, send_feedback


IMPROVE_WEIGHT_STEP = 0.1
IMPROVE_CONFIDENCE_STEP = 0.1
DECAY_WEIGHT_STEP = 0.05  # for thumbs-down (Phase 5 also uses decay, distinct threshold)


@dataclass
class Composed:
    """The coaching text computed from the graph, before anything is persisted.

    ``with_message`` uses the learner's memory (cross-topic evidence when it
    exists); ``no_memory_message`` is what the same mentor could say with *zero*
    history — the honest baseline the ``deja compare`` view sets side by side.
    """

    concept: dict
    skill: dict | None
    related: list[dict]
    with_message: str
    no_memory_message: str
    fix_hint: str


@dataclass
class CoachingTurn:
    """Everything produced by a single chat turn.

    ``used_node_ids`` is the closure of nodes that produced the answer — this
    is what a thumbs-up must reinforce (spec §7). It includes the topic Skill
    and every Mistake we pulled in as cross-topic evidence.

    ``related`` is the (concept_ref, description) pair list for each Mistake
    pulled as evidence — the raw material for the FACTS block the ``--llm``
    reword mode is constrained to.
    """

    topic_concept: str
    topic_skill_id: str | None
    related_mistake_ids: list[str] = field(default_factory=list)
    related: list[tuple[str, str]] = field(default_factory=list)
    used_node_ids: list[str] = field(default_factory=list)
    message: str = ""
    session_id: str | None = None
    fix_hint: str = ""
    # Cognee's own feedback loop (best-effort, additive to the local reweight):
    # the SearchType this turn was recorded under, and whether thumbs-up reached
    # SearchType.FEEDBACK. Both stay None/False if the installed cognee lacks it.
    cognee_interaction: str | None = None
    cognee_feedback_sent: bool = False


async def coach_on_topic(topic: str, user_question: str) -> CoachingTurn:
    """Produce a coaching turn on ``topic``. Persists a Session node.

    ``topic`` must match a Concept.name (or the Skill.concept_ref that points
    at one). We keep the pipeline pure-graph so behavior is testable without
    an LLM.
    """
    by_type, by_id = await graph_store.get_snapshot_indexes()

    composed = _compose_coaching(topic, by_type)
    if composed is None:
        return CoachingTurn(
            topic_concept=topic,
            topic_skill_id=None,
            message=f"I don't know '{topic}' yet — try `deja seed`.",
        )
    concept = composed.concept
    skill = composed.skill
    related = composed.related
    fix_hint = composed.fix_hint

    # ------------------------------------------------------------------
    # Persist a Session — this is what ``remember`` writes and what
    # ``recall`` will surface later. Also records which nodes we drew on.
    # ------------------------------------------------------------------
    session_key = f"session-live-{topic}-{datetime.now(timezone.utc).timestamp():.0f}"
    session = Session(
        session_key=session_key,
        summary=(user_question or f"Live coaching turn on {topic}."),
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        outcome=SessionOutcome.MIXED,
        feedback=Feedback.NONE,
    )
    await graph_store.add_nodes([session])
    edges: list[tuple[str, str, str, dict]] = [
        (str(session.id), str(concept["id"]), Rel.TOUCHED, {}),
    ]
    for rm in related:
        # Preserve the cross-topic evidence as a Session-level TOUCHED edge to
        # that Mistake's Concept, so ``recall`` sees the connection.
        rm_concept_name = _p(rm, "concept_ref")
        rm_concept_node = _find_by_prop(
            by_type.get(Concept.__name__, []), "name", rm_concept_name
        )
        if rm_concept_node:
            edges.append(
                (str(session.id), str(rm_concept_node["id"]), Rel.TOUCHED, {})
            )
    await graph_store.add_edges(edges)

    # Also record this turn through Cognee's OWN pipeline so a later thumbs-up can
    # reinforce it via SearchType.FEEDBACK. Best-effort: None if unsupported.
    cognee_interaction = await save_interaction(user_question or f"coaching on {topic}")

    used = []
    if skill:
        used.append(str(skill["id"]))
    used.extend(str(m["id"]) for m in related)
    used.append(str(session.id))

    return CoachingTurn(
        topic_concept=topic,
        topic_skill_id=str(skill["id"]) if skill else None,
        related_mistake_ids=[str(m["id"]) for m in related],
        related=[
            (_p(m, "concept_ref") or "", _p(m, "description") or "")
            for m in related
        ],
        used_node_ids=used,
        message=composed.with_message,
        session_id=str(session.id),
        fix_hint=fix_hint,
        cognee_interaction=cognee_interaction,
    )


def _compose_coaching(topic: str, by_type: dict[str, list[dict]]) -> Composed | None:
    """Pure: build the coaching text from graph state. No persistence, no I/O.

    Returns ``None`` if the topic isn't a known Concept. ``with_message`` reaches
    across topics (the Scene 2 beat) when a Mistake on another Concept shares a
    ``failure_class``; ``no_memory_message`` is the same mentor with no history —
    used by ``deja compare`` to show what the memory graph actually adds.
    """
    concept = _find_by_prop(by_type.get(Concept.__name__, []), "name", topic)
    if concept is None:
        return None

    skill = _find_by_prop(by_type.get(Skill.__name__, []), "concept_ref", topic)

    all_mistakes = by_type.get(Mistake.__name__, [])
    my_mistakes = [m for m in all_mistakes if _p(m, "concept_ref") == topic]
    my_failure_classes = {_p(m, "failure_class") for m in my_mistakes if _p(m, "failure_class")}
    related = [
        m for m in all_mistakes
        if _p(m, "concept_ref") != topic
        and _p(m, "failure_class") in my_failure_classes
    ]

    # The baseline: what any mentor says with zero memory of this learner.
    no_memory_message = (
        f"Let's work through the {topic} question. Tell me the exact error "
        f"you're seeing and I'll walk you through it."
    )

    fix_hint = ""
    if related:
        rm = related[0]
        rm_concept = _p(rm, "concept_ref")
        rm_class = _p(rm, "failure_class")
        rm_desc = _p(rm, "description") or ""
        fix_hint = (
            f"never let a mutable object outlive one logical scope — for "
            f"{topic}, either create a new collection per task, or guard "
            f"mutations with an ``asyncio.Lock`` when sharing is deliberate"
        )
        with_message = (
            f"This looks like the same shape as the {rm_concept} bug you hit "
            f"before — {rm_desc.rstrip('.')}. "
            f"Both are {rm_class}: state you thought was fresh is actually "
            f"shared across calls or tasks."
            f"\n\nFix pattern: {fix_hint}."
        )
    else:
        with_message = no_memory_message

    return Composed(
        concept=concept,
        skill=skill,
        related=related,
        with_message=with_message,
        no_memory_message=no_memory_message,
        fix_hint=fix_hint,
    )


async def compare_answers(topic: str, question: str) -> tuple[str, str, bool]:
    """Read-only: return (no_memory_message, with_memory_message, memory_helped).

    Does NOT persist a Session — this is an illustrative view, not a real turn.
    ``memory_helped`` is True when cross-topic evidence changed the answer.
    """
    by_type, _ = await graph_store.get_snapshot_indexes()
    composed = _compose_coaching(topic, by_type)
    if composed is None:
        msg = f"I don't know '{topic}' yet — try `deja seed`."
        return msg, msg, False
    return (
        composed.no_memory_message,
        composed.with_message,
        bool(composed.related),
    )


async def maybe_llm_reword(
    turn: CoachingTurn, api_key: str | None, *, model: str | None = None
) -> "RewordResult":
    """Opt-in surface polish; templated stays the default and the truth.

    Called only when the CLI passes ``--llm``. The reword module's contract
    guarantees any failure or hallucination falls back to the templated
    draft — never raises, never lets an untrusted concept name through.

    ``used_node_ids`` and ``related_mistake_ids`` on the turn are untouched
    by this call. The graph-reasoning proof is unchanged whether or not
    the reword succeeds.
    """
    from deja.commands.llm_reword import DEFAULT_MODEL, reword

    all_concepts = await _all_graph_concept_names()
    return reword(
        templated_draft=turn.message,
        topic_concept=turn.topic_concept,
        related=turn.related,
        fix_hint=turn.fix_hint,
        all_graph_concepts=all_concepts,
        api_key=api_key,
        model=model or DEFAULT_MODEL,
    )


async def _all_graph_concept_names() -> list[str]:
    by_type, _ = await graph_store.get_snapshot_indexes()
    return [
        (n.get("properties", {}).get("name") or "")
        for n in by_type.get(Concept.__name__, [])
    ]


async def apply_feedback(turn: CoachingTurn, thumbs: Feedback) -> dict[str, float]:
    """Improve/decay the nodes that produced the answer (spec §7 gotcha).

    Thumbs-up bumps mastery_weight + confidence on the topic Skill and
    confidence on cross-topic Mistakes (evidence that the link helped).
    Thumbs-down decays the Skill lightly — a signal, not a punishment.

    Returns a mapping ``node_id -> new_mastery_weight`` for the caller to show.
    """
    if thumbs is Feedback.NONE:
        return {}

    step_w = IMPROVE_WEIGHT_STEP if thumbs is Feedback.UP else -DECAY_WEIGHT_STEP
    step_c = IMPROVE_CONFIDENCE_STEP if thumbs is Feedback.UP else 0.0

    changes: dict[str, float] = {}

    if turn.topic_skill_id:
        skill_node = await graph_store.get_node(turn.topic_skill_id)
        if skill_node:
            props = skill_node if "mastery_weight" in skill_node else skill_node.get("properties", {})
            old_w = float(props.get("mastery_weight", 0.5))
            old_c = float(props.get("confidence", 0.5))
            new_w = _clamp(old_w + step_w)
            new_c = _clamp(old_c + step_c)
            await graph_store.update_node_properties(
                turn.topic_skill_id,
                {"mastery_weight": new_w, "confidence": new_c},
            )
            changes[turn.topic_skill_id] = new_w

    # Reinforce the *evidence* — Mistakes that helped the answer.
    for mid in turn.related_mistake_ids:
        node = await graph_store.get_node(mid)
        if node:
            props = node if "concept_ref" in node else node.get("properties", {})
            old_c = float(props.get("confidence", props.get("importance_weight", 0.5)))
            new_c = _clamp(old_c + step_c)
            await graph_store.update_node_properties(mid, {"confidence": new_c})

    # Record the feedback on the Session so ``recall`` can later prefer sessions
    # that landed for the learner.
    if turn.session_id:
        await graph_store.update_node_properties(
            turn.session_id, {"feedback": thumbs.value}
        )

    # Cognee's OWN improve loop: reinforce the exact interaction that produced
    # this answer via SearchType.FEEDBACK — additive to the local reweight above,
    # and the real API behind the "reinforce the nodes that helped" story.
    if thumbs is Feedback.UP and turn.cognee_interaction:
        turn.cognee_feedback_sent = await send_feedback(
            "Helpful — the cross-topic connection was correct.", last_k=1
        )

    return changes


def _find_by_prop(nodes: list[dict], key: str, value: str) -> dict | None:
    for n in nodes:
        props = n.get("properties", {})
        if props.get(key) == value:
            return n
    return None


def _p(node: dict | None, key: str, default=None):
    if not node:
        return default
    props = node.get("properties", node)
    return props.get(key, default)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
