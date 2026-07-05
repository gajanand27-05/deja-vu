"""``deja ask "<question>"`` — recall via Cognee's own ``cognee.search`` API.

This is the command that makes the "Best Use of Cognee" story literal: a real
``cognee.search`` call runs against the memory graph. Because that call is
best-effort (see ``deja.store.search``), we ALSO compute a local graph answer
from the ``SAME_FAMILY_AS`` neighborhood so the command is always useful in the
demo — even if the installed cognee's search returns nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from deja.models.graph import Mistake, Rel
from deja.store import graph_store
from deja.store.search import SearchOutcome, search_memory


@dataclass
class AskResult:
    query: str
    outcome: SearchOutcome        # what cognee.search returned
    local_answer: str             # graph-derived answer (always present)


async def ask(query_text: str) -> AskResult:
    """Run a real cognee.search AND a local graph lookup; return both."""
    outcome = await search_memory(query_text)
    local = await _local_memory_answer()
    return AskResult(query=query_text, outcome=outcome, local_answer=local)


async def _local_memory_answer() -> str:
    """Answer from the graph itself — the SAME_FAMILY_AS families memify built.

    Deterministic and dependency-free, so ``deja ask`` always has something to
    show. After ``deja memify`` this surfaces the cross-topic family; before it,
    it lists the learner's open gaps.
    """
    nodes, edges = await graph_store.graph_snapshot()
    by_id = {str(n["id"]): n for n in nodes}

    families: list[tuple[dict, dict]] = []
    for e in edges:
        if e.get("relationship_name") == Rel.SAME_FAMILY_AS:
            a = by_id.get(str(e["source"]))
            b = by_id.get(str(e["target"]))
            if a and b:
                families.append((a, b))

    if families:
        lines = ["Your memory has connected mistakes across different topics:"]
        for a, b in families:
            fc = _p(a, "failure_class") or _p(b, "failure_class") or "the same failure class"
            lines.append(
                f"  • “{_p(a, 'description')}” ({_p(a, 'concept_ref')}) and "
                f"“{_p(b, 'description')}” ({_p(b, 'concept_ref')}) are the same "
                f"family — both are {fc}."
            )
        lines.append(
            "That's why you keep hitting it: it's one root cause wearing different "
            "clothes. Fix the class, not the symptom."
        )
        return "\n".join(lines)

    open_mistakes = [
        n for n in nodes
        if _p(n, "type") == Mistake.__name__ and not _p(n, "resolved", False)
    ]
    if open_mistakes:
        gaps = ", ".join(sorted({_p(m, "concept_ref") for m in open_mistakes if _p(m, "concept_ref")}))
        return (
            f"Open gaps in your memory: {gaps}. Run `deja memify` and ask again — "
            "the graph may connect them into a single failure family."
        )
    return "Nothing in memory yet — run `deja seed` first."


def _p(node: dict | None, key: str, default: Any = None) -> Any:
    if not node:
        return default
    props = node.get("properties", node)
    return props.get(key, default)
