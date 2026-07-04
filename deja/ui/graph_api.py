"""Serialize the graph for the browser.

Node/edge styling encoding lives in one place so both the JSON payload and the
JS-side vis.js config agree on what makes a Skill green or an edge magenta.
"""

from __future__ import annotations

from typing import Any

from deja.models.graph import (
    Concept,
    Learner,
    Mistake,
    Rel,
    Session,
    Skill,
    SkillStatus,
)
from deja.store import graph_store


# Simple palette. Tweaked so the SAME_FAMILY_AS edge visibly dominates.
NODE_COLORS = {
    Learner.__name__: "#a78bfa",
    Concept.__name__: "#60a5fa",
    Skill.__name__: "#34d399",
    Session.__name__: "#94a3b8",
    Mistake.__name__: "#f87171",
}
EDGE_COLORS = {
    Rel.HAS_SKILL: "#94a3b8",
    Rel.OF_CONCEPT: "#94a3b8",
    Rel.TOUCHED: "#94a3b8",
    Rel.REVEALED: "#f87171",
    Rel.INDICATES_GAP_IN: "#f87171",
    Rel.PREREQUISITE_OF: "#94a3b8",
    Rel.SAME_FAMILY_AS: "#ec4899",   # the headline
    Rel.RELATED_TO: "#38bdf8",
}
INFERRED_REL_NAMES = {Rel.SAME_FAMILY_AS, Rel.RELATED_TO}


async def build_graph_payload() -> dict[str, Any]:
    nodes, edges = await graph_store.graph_snapshot()

    vis_nodes: list[dict[str, Any]] = []
    for n in nodes:
        props = n.get("properties", {})
        t = props.get("type") or "unknown"
        vis_nodes.append(_node_dict(str(n["id"]), t, props))

    vis_edges: list[dict[str, Any]] = []
    for i, e in enumerate(edges):
        rel = e.get("relationship_name") or "?"
        vis_edges.append(_edge_dict(i, e["source"], e["target"], rel))

    return {"nodes": vis_nodes, "edges": vis_edges}


def _node_dict(node_id: str, node_type: str, props: dict) -> dict[str, Any]:
    label = _label_for(node_type, props)
    color = NODE_COLORS.get(node_type, "#cbd5e1")
    size = _size_for(node_type, props)
    status = props.get("status")
    if node_type == Skill.__name__ and status in (SkillStatus.DECAYING.value, SkillStatus.DECAYING):
        color = "#cbd5e1"  # dim decayed Skills
    return {
        "id": node_id,
        "label": label,
        "title": _tooltip(node_type, props),
        "type": node_type,
        "color": color,
        "size": size,
    }


def _edge_dict(i: int, source: str, target: str, rel: str) -> dict[str, Any]:
    color = EDGE_COLORS.get(rel, "#94a3b8")
    width = 4 if rel == Rel.SAME_FAMILY_AS else 1.5
    dashes = rel in INFERRED_REL_NAMES and rel != Rel.SAME_FAMILY_AS
    return {
        "id": f"e{i}",
        "from": str(source),
        "to": str(target),
        "label": rel,
        "arrows": "to",
        "color": {"color": color, "highlight": color},
        "width": width,
        "dashes": dashes,
        "relationship_name": rel,
    }


def _label_for(node_type: str, props: dict) -> str:
    if node_type == Learner.__name__:
        return f"👤 {props.get('name', 'learner')}"
    if node_type == Concept.__name__:
        name = props.get("name", "?")
        return f"📚 {name}" + (" [deprecated]" if props.get("deprecated") else "")
    if node_type == Skill.__name__:
        return f"🧠 {props.get('concept_ref', '?')}\n{float(props.get('mastery_weight', 0.5)):.2f}"
    if node_type == Session.__name__:
        return f"💬 {props.get('session_key', 'session')[:24]}"
    if node_type == Mistake.__name__:
        return f"⚠ {props.get('mistake_key', 'mistake')}"
    return props.get("name") or props.get("id", "?")


def _tooltip(node_type: str, props: dict) -> str:
    parts = [f"<b>{node_type}</b>"]
    for k in ("name", "concept_ref", "mastery_weight", "confidence", "status",
              "failure_class", "resolved", "current_focus", "deprecated",
              "outcome", "feedback", "summary", "description"):
        if k in props and props[k] not in (None, ""):
            parts.append(f"{k}: <i>{props[k]}</i>")
    return "<br>".join(parts)


def _size_for(node_type: str, props: dict) -> float:
    if node_type == Skill.__name__:
        # Weight drives visible thickness — the memify effect.
        return 15 + 30 * float(props.get("mastery_weight", 0.5))
    if node_type == Learner.__name__:
        return 32
    if node_type == Concept.__name__:
        return 22
    return 18
