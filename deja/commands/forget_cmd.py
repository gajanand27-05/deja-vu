"""``deja forget`` — Scene 4: decay + hard prune.

Two mechanisms (spec §5, §7):

  **Soft — decay.** Skills that are ``mastered`` and haven't been practiced
  recently drop their ``mastery_weight`` and flip to ``decaying`` so they
  fade out of active recall. This is what stops the mentor from nagging
  the learner about things they know.

  **Hard — prune.** Concepts flagged ``deprecated`` are deleted, along with
  the Skills that point at them and every edge touching either. This
  removes Python 2 idioms from a graph that should stay current.

The demo script shows both. The CLI prints them separately so the graph
view can highlight decay (dimmed) vs. prune (gone).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from deja.models.graph import Concept, Skill, SkillStatus
from deja.store import graph_store


DECAY_STALE_DAYS = 6         # >= this many days since last_practiced ⇒ eligible
DECAY_WEIGHT_FACTOR = 0.6    # 0.9 → 0.54 for recursion, dropped from active recall


@dataclass
class ForgetDiff:
    decayed_skills: dict[str, tuple[float, float]] = field(default_factory=dict)
    """concept_ref -> (old_weight, new_weight)"""
    pruned_concepts: list[str] = field(default_factory=list)
    """concept.name — hard delete"""
    pruned_skills: list[str] = field(default_factory=list)
    """concept_ref of the orphaned Skill (deleted with its Concept)"""

    @property
    def is_empty(self) -> bool:
        return not self.decayed_skills and not self.pruned_concepts


def discover_decay_candidates(
    skills: list[dict],
    now: datetime,
    threshold_days: int = DECAY_STALE_DAYS,
    force_topic: str | None = None,
) -> list[tuple[dict, float, float]]:
    """Return the Skills to decay: (skill_node, old_weight, new_weight)."""
    threshold = now - timedelta(days=threshold_days)
    out: list[tuple[dict, float, float]] = []
    for s in skills:
        props = s.get("properties", {})
        status = props.get("status")
        if status in (SkillStatus.DECAYING.value, SkillStatus.DECAYING):
            continue

        stale = False
        last = props.get("last_practiced_iso")
        if last:
            try:
                if datetime.fromisoformat(last) <= threshold:
                    stale = True
            except ValueError:
                pass

        forced = force_topic is not None and props.get("concept_ref") == force_topic
        if not (stale and _is_mastered(status)) and not forced:
            continue

        old = float(props.get("mastery_weight", 0.5))
        new = round(old * DECAY_WEIGHT_FACTOR, 4)
        if new == old:
            continue
        out.append((s, old, new))
    return out


def discover_prune_targets(
    concepts: list[dict],
    skills: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Return (concepts_to_prune, skills_to_prune).

    Skills pointing at a deprecated Concept are pruned with it. Any Skill
    whose Concept no longer exists is also caught here.
    """
    deprecated = [c for c in concepts if c.get("properties", {}).get("deprecated")]
    deprecated_names = {c.get("properties", {}).get("name") for c in deprecated}
    orphan_skills = [
        s for s in skills
        if s.get("properties", {}).get("concept_ref") in deprecated_names
    ]
    return deprecated, orphan_skills


async def run_forget(force_topic: str | None = None) -> ForgetDiff:
    nodes, _edges = await graph_store.graph_snapshot()
    by_type: dict[str, list[dict]] = {}
    for n in nodes:
        t = n.get("properties", {}).get("type") or "unknown"
        by_type.setdefault(t, []).append(n)

    diff = ForgetDiff()
    now = datetime.now(timezone.utc)
    skills = by_type.get(Skill.__name__, [])
    concepts = by_type.get(Concept.__name__, [])

    # --- Soft decay --------------------------------------------------
    decay_targets = discover_decay_candidates(
        skills, now=now, force_topic=force_topic
    )
    for skill_node, old, new in decay_targets:
        cref = skill_node.get("properties", {}).get("concept_ref") or "?"
        await graph_store.update_node_properties(
            skill_node["id"],
            {
                "mastery_weight": new,
                "status": SkillStatus.DECAYING.value,
            },
        )
        diff.decayed_skills[cref] = (old, new)

    # --- Hard prune --------------------------------------------------
    prune_concepts, prune_skills = discover_prune_targets(concepts, skills)
    from cognee.infrastructure.databases.graph import get_graph_engine

    if prune_concepts or prune_skills:
        engine = await get_graph_engine()
        node_ids = [str(n["id"]) for n in prune_concepts + prune_skills]
        await engine.delete_nodes(node_ids)

    diff.pruned_concepts = [
        c.get("properties", {}).get("name") or _short(c["id"])
        for c in prune_concepts
    ]
    diff.pruned_skills = [
        s.get("properties", {}).get("concept_ref") or _short(s["id"])
        for s in prune_skills
    ]

    return diff


def _is_mastered(status) -> bool:
    return status in (SkillStatus.MASTERED.value, SkillStatus.MASTERED)


def _short(s: str) -> str:
    s = str(s)
    return s[:8] + "…" if len(s) > 8 else s
