"""Thin async wrapper around Cognee's graph engine.

The store handles the low-level "write typed nodes + explicit edges" work so
higher layers (seed, memify, forget, ui) don't touch the graph adapter directly.

Deterministic writes go through here. LLM-driven writes (``deja chat``) will use
cognee.remember() with our custom graph_model in Phase 3.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.infrastructure.engine import DataPoint
from cognee.modules.engine.operations.setup import setup as cognee_setup

from deja.models.graph import Concept, Learner, Mistake, Rel, Session, Skill


@dataclass(frozen=True)
class NodeCount:
    learners: int
    concepts: int
    skills: int
    sessions: int
    mistakes: int
    total: int

    def as_dict(self) -> dict[str, int]:
        return {
            "learners": self.learners,
            "concepts": self.concepts,
            "skills": self.skills,
            "sessions": self.sessions,
            "mistakes": self.mistakes,
            "total": self.total,
        }


async def ensure_setup() -> None:
    """Ensure cognee's DB tables exist. Idempotent."""
    await cognee_setup()


async def wipe() -> None:
    """Delete every node/edge in the local graph. Used by ``deja seed``."""
    engine = await get_graph_engine()
    await engine.delete_graph()


async def add_nodes(nodes: list[DataPoint]) -> None:
    engine = await get_graph_engine()
    await engine.add_nodes(nodes)


async def add_edges(edges: list[tuple[str, str, str, dict[str, Any]]]) -> None:
    """Add explicit edges. Tuple format: (source_id, target_id, rel_name, props)."""
    engine = await get_graph_engine()
    await engine.add_edges(edges)


async def graph_snapshot() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (nodes, edges) as plain dicts for UI / assertions.

    Edges are normalized to ``{"source", "target", "relationship_name",
    "properties"}`` regardless of adapter-specific shapes.
    """
    engine = await get_graph_engine()
    nodes, edges = await engine.get_graph_data()

    normalized_nodes = []
    for n in nodes:
        if isinstance(n, tuple):
            node_id, props = n
        elif isinstance(n, dict):
            node_id = n.get("id") or n.get("node_id")
            props = n
        else:
            node_id = getattr(n, "id", None)
            props = n
        normalized_nodes.append({"id": str(node_id), "properties": _to_plain(props)})

    normalized_edges = []
    for e in edges:
        if isinstance(e, tuple):
            # (source, target, relationship_name, properties)
            src, tgt, rel, props = e[0], e[1], e[2], (e[3] if len(e) > 3 else {})
        elif isinstance(e, dict):
            src = e.get("source_node_id") or e.get("source")
            tgt = e.get("target_node_id") or e.get("target")
            rel = e.get("relationship_name") or e.get("relationship") or e.get("type")
            props = {k: v for k, v in e.items() if k not in {"source", "target", "relationship_name", "relationship", "type"}}
        else:
            continue
        normalized_edges.append(
            {
                "source": str(src),
                "target": str(tgt),
                "relationship_name": rel,
                "properties": _to_plain(props),
            }
        )

    return normalized_nodes, normalized_edges


async def count_nodes() -> NodeCount:
    nodes, _edges = await graph_snapshot()
    per_type: dict[str, int] = {}
    for n in nodes:
        t = n.get("properties", {}).get("type") or "unknown"
        per_type[t] = per_type.get(t, 0) + 1
    return NodeCount(
        learners=per_type.get(Learner.__name__, 0),
        concepts=per_type.get(Concept.__name__, 0),
        skills=per_type.get(Skill.__name__, 0),
        sessions=per_type.get(Session.__name__, 0),
        mistakes=per_type.get(Mistake.__name__, 0),
        total=len(nodes),
    )


async def has_edge(source_id: UUID | str, target_id: UUID | str, rel_name: str) -> bool:
    engine = await get_graph_engine()
    src = str(source_id)
    tgt = str(target_id)
    result = await engine.has_edge(src, tgt, rel_name)
    return bool(result)


async def get_node(node_id: UUID | str) -> dict[str, Any] | None:
    engine = await get_graph_engine()
    node = await engine.get_node(str(node_id))
    if node is None:
        return None
    return _to_plain(node)


async def update_node_properties(node_id: UUID | str, updates: dict[str, Any]) -> bool:
    """Merge ``updates`` into a node's stored custom properties.

    Ladybug stores our custom fields (mastery_weight, confidence, status, ...) in
    a JSON blob column named ``properties``. To mutate, read the row, merge,
    write. Core fields (id, name, type) live outside that blob and are left
    alone here.

    Returns True on success, False if the node wasn't found.
    """
    import json

    engine = await get_graph_engine()
    node_id_str = str(node_id)
    row = await engine.query(
        "MATCH (n:Node) WHERE n.id = $id RETURN n.properties AS props",
        {"id": node_id_str},
    )
    if not row:
        return False
    props_json = row[0][0] if isinstance(row[0], (tuple, list)) else row[0]
    try:
        props = json.loads(props_json) if props_json else {}
    except (TypeError, ValueError):
        props = {}

    props.update({k: _plain_value(v) for k, v in updates.items()})

    await engine.query(
        "MATCH (n:Node) WHERE n.id = $id SET n.properties = $props",
        {"id": node_id_str, "props": json.dumps(props)},
    )
    return True


async def get_snapshot_indexes() -> tuple[dict[str, list[dict]], dict[str, dict]]:
    """Return (nodes-by-type, node-by-id) for quick in-Python graph work.

    Convenience for command implementations that want the whole graph in memory
    (small at demo scale). Callers should treat the dicts as read-only.
    """
    nodes, _edges = await graph_snapshot()
    by_type: dict[str, list[dict]] = {}
    by_id: dict[str, dict] = {}
    for n in nodes:
        props = n.get("properties", {})
        t = props.get("type") or "unknown"
        by_type.setdefault(t, []).append(n)
        by_id[str(n["id"])] = n
    return by_type, by_id


def _to_plain(obj: Any) -> dict[str, Any]:
    """Best-effort conversion of node/edge property blobs to a serializable dict."""
    if isinstance(obj, dict):
        return {k: _plain_value(v) for k, v in obj.items()}
    if hasattr(obj, "model_dump"):
        return {k: _plain_value(v) for k, v in obj.model_dump().items()}
    if hasattr(obj, "__dict__"):
        return {k: _plain_value(v) for k, v in vars(obj).items()}
    return {"value": _plain_value(obj)}


def _plain_value(v: Any) -> Any:
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, dict):
        return {k: _plain_value(vv) for k, vv in v.items()}
    if isinstance(v, list):
        return [_plain_value(x) for x in v]
    if hasattr(v, "value"):  # Enum
        try:
            return v.value
        except Exception:  # noqa: BLE001
            pass
    return v
