"""``deja memify`` — Scene 3, the headline moment.

Two visible effects (spec §4):

1. **New edges appear**: for every pair of Mistake nodes that share
   ``failure_class`` AND live under *different* Concepts, add
   ``Mistake —SAME_FAMILY_AS→ Mistake``. These edges must not exist in the
   seed (enforced in Phase 1 tests + tested here for a live seed).
2. **Re-weight**: Skills whose Concepts now sit in a newly-linked family gain
   a small ``mastery_weight`` bump — the graph visibly thickens where the
   inference happened.

Also infers ``Concept —RELATED_TO→ Concept`` from Session co-occurrence (a
milder inference, but it fills in the graph view). Idempotent: repeat runs
do not add duplicate edges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from deja.models.graph import Concept, Mistake, Rel, Session, Skill
from deja.store import graph_store


MEMIFY_WEIGHT_BUMP = 0.05  # per-inference reinforcement — small on purpose


@dataclass
class MemifyDiff:
    """What memify changed. Rendered by the CLI as the Scene 3 confirmation."""

    same_family_edges: list[tuple[str, str, str, str]] = field(default_factory=list)
    """(src_mistake_key, tgt_mistake_key, src_concept, tgt_concept)"""
    related_concept_edges: list[tuple[str, str]] = field(default_factory=list)
    """(concept_a, concept_b)"""
    reweighted_skills: dict[str, tuple[float, float]] = field(default_factory=dict)
    """concept_ref -> (old_weight, new_weight)"""

    @property
    def is_empty(self) -> bool:
        return (
            not self.same_family_edges
            and not self.related_concept_edges
            and not self.reweighted_skills
        )


def discover_family_edges(
    mistakes_nodes: list[dict],
    existing_edges: list[dict],
) -> list[tuple[dict, dict]]:
    """Find pairs of Mistakes to link with SAME_FAMILY_AS.

    Rule (spec §3): same ``failure_class`` AND different ``concept_ref``.
    Idempotent: skip pairs already linked by SAME_FAMILY_AS in either direction.
    """
    already: set[frozenset[str]] = set()
    for e in existing_edges:
        if e.get("relationship_name") == Rel.SAME_FAMILY_AS:
            already.add(frozenset({str(e["source"]), str(e["target"])}))

    by_class: dict[str, list[dict]] = {}
    for m in mistakes_nodes:
        fc = _p(m, "failure_class")
        if not fc:
            continue
        by_class.setdefault(fc, []).append(m)

    pairs: list[tuple[dict, dict]] = []
    for fc, mistakes in by_class.items():
        for a, b in combinations(mistakes, 2):
            if _p(a, "concept_ref") == _p(b, "concept_ref"):
                # Same Concept — the interesting cross-topic link is not there.
                continue
            key = frozenset({str(a["id"]), str(b["id"])})
            if key in already:
                continue
            pairs.append((a, b))
    return pairs


def discover_related_concepts(
    session_nodes: list[dict],
    existing_edges: list[dict],
) -> list[tuple[str, str]]:
    """Concepts co-touched by any Session get a RELATED_TO edge.

    Uses the TOUCHED edges we already wrote — if one Session touched two
    Concepts, they're related. Idempotent.
    """
    session_ids = {str(s["id"]) for s in session_nodes}
    touched_by_session: dict[str, set[str]] = {}
    for e in existing_edges:
        if e.get("relationship_name") == Rel.TOUCHED:
            src = str(e["source"])
            tgt = str(e["target"])
            if src in session_ids:
                touched_by_session.setdefault(src, set()).add(tgt)

    already: set[frozenset[str]] = set()
    for e in existing_edges:
        if e.get("relationship_name") == Rel.RELATED_TO:
            already.add(frozenset({str(e["source"]), str(e["target"])}))

    new_pairs: list[tuple[str, str]] = []
    for _sid, concept_ids in touched_by_session.items():
        for a, b in combinations(sorted(concept_ids), 2):
            key = frozenset({a, b})
            if key in already or key in {frozenset(p) for p in new_pairs}:
                continue
            new_pairs.append((a, b))
    return new_pairs


async def run_memify() -> MemifyDiff:
    """Perform memify against the live graph. Returns a diff for display."""
    nodes, edges = await graph_store.graph_snapshot()

    by_type: dict[str, list[dict]] = {}
    node_by_id: dict[str, dict] = {}
    for n in nodes:
        t = n.get("properties", {}).get("type") or "unknown"
        by_type.setdefault(t, []).append(n)
        node_by_id[str(n["id"])] = n

    diff = MemifyDiff()

    # ------------------------------------------------------------------
    # 1) SAME_FAMILY_AS between Mistakes on different Concepts.
    # ------------------------------------------------------------------
    mistake_nodes = by_type.get(Mistake.__name__, [])
    family_pairs = discover_family_edges(mistake_nodes, edges)

    family_edges_to_write: list[tuple[str, str, str, dict]] = []
    for a, b in family_pairs:
        family_edges_to_write.append(
            (str(a["id"]), str(b["id"]), Rel.SAME_FAMILY_AS, {})
        )
        diff.same_family_edges.append(
            (
                _p(a, "mistake_key") or _short(a["id"]),
                _p(b, "mistake_key") or _short(b["id"]),
                _p(a, "concept_ref") or "?",
                _p(b, "concept_ref") or "?",
            )
        )

    # ------------------------------------------------------------------
    # 2) RELATED_TO between Concepts co-touched by a Session.
    # ------------------------------------------------------------------
    session_nodes = by_type.get(Session.__name__, [])
    related_pairs = discover_related_concepts(session_nodes, edges)
    related_edges_to_write: list[tuple[str, str, str, dict]] = []
    for a, b in related_pairs:
        related_edges_to_write.append((a, b, Rel.RELATED_TO, {}))
        a_name = _p(node_by_id.get(a), "name") or _short(a)
        b_name = _p(node_by_id.get(b), "name") or _short(b)
        diff.related_concept_edges.append((a_name, b_name))

    all_new_edges = family_edges_to_write + related_edges_to_write
    if all_new_edges:
        await graph_store.add_edges(all_new_edges)

    # ------------------------------------------------------------------
    # 3) Re-weight Skills for Concepts that participated in a family link.
    #    A small, deterministic bump — the visible thickening in the graph view.
    # ------------------------------------------------------------------
    concepts_in_family: set[str] = set()
    for a, b, c_a, c_b in diff.same_family_edges:
        concepts_in_family.add(c_a)
        concepts_in_family.add(c_b)

    skill_nodes = by_type.get(Skill.__name__, [])
    for skill in skill_nodes:
        cref = _p(skill, "concept_ref")
        if cref not in concepts_in_family:
            continue
        old = float(_p(skill, "mastery_weight", default=0.5))
        new = _clamp(old + MEMIFY_WEIGHT_BUMP)
        if new == old:
            continue
        await graph_store.update_node_properties(
            skill["id"], {"mastery_weight": new}
        )
        diff.reweighted_skills[cref] = (old, new)

    return diff


def _p(node: dict | None, key: str, default=None):
    if not node:
        return default
    props = node.get("properties", node)
    return props.get(key, default)


def _short(s: str) -> str:
    s = str(s)
    return s[:8] + "…" if len(s) > 8 else s


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))
