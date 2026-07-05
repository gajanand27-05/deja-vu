"""``deja start`` — Scene 1 cold open.

The three lines the mentor greets you with must fall out of a graph query, not
hardcoded strings. That's the demo's headline promise: "I typed nothing but
'start' and it knew who I am."

Query (spec §5):
  a) highest-weight Skill (mastered)      → "you nailed X"
  b) low-weight Skill with unresolved Mistake → "you stumbled on Y (specifically Z)"
  c) Learner.current_focus                → "you'd just started W"
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from deja.models.graph import Learner, Mistake, Rel, Session, Skill, SkillStatus
from deja.store import graph_store


@dataclass(frozen=True)
class ColdOpen:
    """Structured cold-open result. Rendering is the CLI's job, not this module's."""

    learner_name: str
    mastered_topic: str | None      # (a)
    stumbled_topic: str | None      # (b) concept name
    stumbled_mistake: str | None    # (b) mistake description
    current_focus: str | None       # (c)
    # (d) the most recent persisted Session — proves memory survives a restart.
    # This is the hackathon's whole thesis: no context hangover across runs.
    last_session_summary: str | None = None
    last_session_when: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "learner_name": self.learner_name,
            "mastered_topic": self.mastered_topic,
            "stumbled_topic": self.stumbled_topic,
            "stumbled_mistake": self.stumbled_mistake,
            "current_focus": self.current_focus,
            "last_session_summary": self.last_session_summary,
            "last_session_when": self.last_session_when,
        }


async def build_cold_open() -> ColdOpen:
    """Read the graph and derive the three lines from it.

    Kept as one query + pure Python filtering because the graph is small at
    demo scale. If the graph grows, split into targeted engine queries.
    """
    nodes, edges = await graph_store.graph_snapshot()
    return _derive(nodes, edges)


def _derive(nodes: list[dict], edges: list[dict], now: datetime | None = None) -> ColdOpen:
    """Pure-Python derivation so tests can drive it with fixtures.

    Split from ``build_cold_open`` so the recall logic is testable without
    spinning up cognee's engine.
    """
    by_type: dict[str, list[dict]] = {}
    by_id: dict[str, dict] = {}
    for n in nodes:
        props = n.get("properties", {})
        t = props.get("type") or "unknown"
        by_type.setdefault(t, []).append(n)
        by_id[str(n["id"])] = n

    learners = by_type.get(Learner.__name__, [])
    if not learners:
        return ColdOpen(
            learner_name="you",
            mastered_topic=None,
            stumbled_topic=None,
            stumbled_mistake=None,
            current_focus=None,
        )
    learner_props = learners[0].get("properties", {})
    learner_name = learner_props.get("name") or "you"
    current_focus = learner_props.get("current_focus") or None

    # (a) highest-weight *mastered* Skill.
    skills = by_type.get(Skill.__name__, [])
    mastered = [
        s for s in skills
        if _prop(s, "status") in {SkillStatus.MASTERED.value, SkillStatus.MASTERED}
        and not _prop(_concept_for(s, by_type), "deprecated", default=False)
    ]
    mastered.sort(key=lambda s: float(_prop(s, "mastery_weight", default=0.0)), reverse=True)
    mastered_topic = _prop(mastered[0], "concept_ref") if mastered else None

    # (b) lowest-weight Skill whose linked Mistake is unresolved.
    stumbled_topic: str | None = None
    stumbled_mistake: str | None = None

    mistakes = [m for m in by_type.get(Mistake.__name__, []) if not _prop(m, "resolved", default=False)]
    # For each mistake, find its Concept, then find the Skill on that Concept for the learner.
    weighted_candidates: list[tuple[float, str, str]] = []
    concept_by_name = {
        _prop(c, "name"): c for c in by_type.get("Concept", [])
    }
    skill_by_concept = {_prop(s, "concept_ref"): s for s in skills}
    for m in mistakes:
        concept_name = _prop(m, "concept_ref")
        if concept_name not in skill_by_concept:
            continue
        skill = skill_by_concept[concept_name]
        weight = float(_prop(skill, "mastery_weight", default=1.0))
        weighted_candidates.append(
            (weight, concept_name, _prop(m, "description") or "")
        )
    weighted_candidates.sort()
    if weighted_candidates:
        _, stumbled_topic, stumbled_mistake = weighted_candidates[0]

    # (d) most recent Session — the proof memory persists across process restarts.
    last_summary, last_when = _latest_session(
        by_type.get(Session.__name__, []), now or datetime.now(timezone.utc)
    )

    return ColdOpen(
        learner_name=learner_name,
        mastered_topic=mastered_topic,
        stumbled_topic=stumbled_topic,
        stumbled_mistake=stumbled_mistake,
        current_focus=current_focus,
        last_session_summary=last_summary,
        last_session_when=last_when,
    )


def _latest_session(
    sessions: list[dict], now: datetime
) -> tuple[str | None, str | None]:
    """Return (summary, human-readable-when) for the newest Session, or (None, None).

    Newest by ``timestamp_iso``. The summary is trimmed for a one-line greeting.
    """
    dated: list[tuple[datetime, dict]] = []
    for s in sessions:
        iso = _prop(s, "timestamp_iso")
        try:
            dated.append((datetime.fromisoformat(iso), s))
        except (TypeError, ValueError):
            continue
    if not dated:
        return None, None
    when_dt, newest = max(dated, key=lambda pair: pair[0])
    summary = (_prop(newest, "summary") or "").strip()
    if len(summary) > 90:
        summary = summary[:87].rstrip() + "…"
    return (summary or None), _relative_when(when_dt, now)


def _relative_when(then: datetime, now: datetime) -> str:
    """Coarse, demo-friendly relative time: 'just now' / 'N hours ago' / 'N days ago'."""
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    secs = (now - then).total_seconds()
    if secs < 3600:
        return "just now"
    if secs < 86400:
        hours = int(secs // 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(secs // 86400)
    return f"{days} day{'s' if days != 1 else ''} ago"


def _prop(node: dict | None, key: str, default: Any = None) -> Any:
    if not node:
        return default
    props = node.get("properties", node)
    if key in props:
        return props[key]
    return default


def _concept_for(skill_node: dict, by_type: dict[str, list[dict]]) -> dict | None:
    """Return the Concept node this Skill points at (by concept_ref = name)."""
    ref = _prop(skill_node, "concept_ref")
    if not ref:
        return None
    for c in by_type.get("Concept", []):
        if _prop(c, "name") == ref:
            return c
    return None


def render_cold_open(cold: ColdOpen) -> str:
    """Compose the mentor's greeting from the derived facts.

    The *content* comes from the graph. The *wording* is deterministic here so
    the demo rehearses cleanly. If any field is missing (empty graph) we fall
    back to a plain hello.
    """
    if not cold.mastered_topic and not cold.stumbled_topic and not cold.current_focus:
        return f"Hello. I don't know you yet — try `deja seed` to load the demo memory."

    lines: list[str] = [f"Welcome back, {cold.learner_name}."]
    if cold.last_session_summary:
        when = f" {cold.last_session_when}" if cold.last_session_when else ""
        lines.append(f"You were last here{when} — {cold.last_session_summary}")
    if cold.mastered_topic and cold.stumbled_topic:
        lines.append(
            f"Last time you nailed {cold.mastered_topic} but stumbled on "
            f"{cold.stumbled_topic}."
        )
    elif cold.mastered_topic:
        lines.append(f"Last time you nailed {cold.mastered_topic}.")
    elif cold.stumbled_topic:
        lines.append(f"Last time you stumbled on {cold.stumbled_topic}.")

    if cold.current_focus:
        lines.append(f"You'd also just started on {cold.current_focus}.")

    if cold.stumbled_topic and cold.current_focus:
        lines.append(
            f"Want to revisit the {cold.stumbled_topic} gotcha, "
            f"or push forward on {cold.current_focus}?"
        )
    return "\n".join(lines)
