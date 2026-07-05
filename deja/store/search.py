"""The ``recall`` verb via Cognee's OWN public API — ``cognee.search``.

Déjà writes typed nodes straight through the graph engine (not the ``cognify``
pipeline), so vector-only search types (``GRAPH_COMPLETION`` / ``CHUNKS``) may
return nothing. ``INSIGHTS`` and ``CYPHER`` run over the Kuzu graph we already
populated, so they return results without any embedding plumbing — that's the
path ``deja ask`` relies on.

Contract: **best-effort, never raises.** If Cognee's search API isn't shaped the
way we expect on the installed version, we log and fall back to a local graph
answer. Run ``spike_cognee.py`` on the target machine to confirm the exact shape
and, if needed, tighten ``_SEARCH_TYPE_PATHS`` / ``_call_search`` here.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Best-effort Cognee calls are timeout-guarded so a slow/hanging cloud or LLM
# round-trip can never stall the (templated, deterministic) demo path.
_BEST_EFFORT_TIMEOUT_S = 8.0

# Where SearchType lives has moved across cognee versions — try known homes.
_SEARCH_TYPE_PATHS = (
    "cognee.modules.search.types",
    "cognee.modules.search.types.SearchType",
    "cognee.api.v1.search",
    "cognee",
)


@dataclass(frozen=True)
class SearchOutcome:
    """What a real ``cognee.search`` call produced (or why it didn't)."""

    search_type: str | None       # e.g. "INSIGHTS"; None if no call succeeded
    results: list[Any]            # raw results from cognee.search
    attempted: list[str]          # the SearchTypes we tried, in order
    error: str | None = None      # last failure reason, if all attempts failed

    @property
    def ok(self) -> bool:
        return self.search_type is not None


def _resolve_search_type_enum():
    """Return cognee's ``SearchType`` enum from whichever path exists."""
    for path in _SEARCH_TYPE_PATHS:
        mod_name, _, attr = path.rpartition(".")
        try:
            if attr == "SearchType" and mod_name:
                mod = __import__(mod_name, fromlist=["SearchType"])
                return getattr(mod, "SearchType")
            mod = __import__(path, fromlist=["SearchType"])
            return getattr(mod, "SearchType")
        except (ImportError, AttributeError):
            continue
    return None


async def _call_search(cognee, query_type, query_text: str):
    """Call ``cognee.search`` tolerating the two arg shapes seen across versions."""
    try:
        return await cognee.search(query_type=query_type, query_text=query_text)
    except TypeError:
        # Older/newer signature: (query_text, query_type) or query=...
        try:
            return await cognee.search(query_text, query_type=query_type)
        except TypeError:
            return await cognee.search(query=query_text, query_type=query_type)


async def search_memory(
    query_text: str,
    *,
    prefer: tuple[str, ...] = ("INSIGHTS", "GRAPH_COMPLETION", "SUMMARIES"),
) -> SearchOutcome:
    """Run a real ``cognee.search`` over the populated graph. Never raises.

    Tries each SearchType in ``prefer`` order and returns the first that yields
    a non-empty result. Falls through to an empty outcome if the API is absent
    or every attempt fails — the caller then shows the local graph answer.
    """
    attempted: list[str] = []
    last_error: str | None = None
    try:
        import cognee
    except ImportError as exc:  # cognee not installed — pure fallback
        return SearchOutcome(None, [], attempted, f"cognee import failed: {exc}")

    search_type = _resolve_search_type_enum()
    if search_type is None:
        return SearchOutcome(None, [], attempted, "SearchType enum not found")

    for name in prefer:
        st = getattr(search_type, name, None)
        if st is None:
            continue
        attempted.append(name)
        try:
            res = await _call_search(cognee, st, query_text)
        except Exception as exc:  # noqa: BLE001 — best-effort recall, any failure falls back
            last_error = f"{name}: {type(exc).__name__}: {exc}"
            logger.warning("cognee.search %s failed: %s", name, exc)
            continue
        if res:
            return SearchOutcome(name, list(res), attempted)
    return SearchOutcome(None, [], attempted, last_error)


async def save_interaction(query_text: str) -> str | None:
    """Best-effort: run a graph-backed ``cognee.search`` with ``save_interaction=True``.

    This is what gives Cognee's FEEDBACK loop something to attach a score to
    later (see ``send_feedback``). Timeout-guarded and swallows every failure —
    the templated ``deja chat`` answer is unaffected either way. Returns the
    SearchType name it recorded under, or None.
    """
    try:
        import cognee
    except ImportError:
        return None
    search_type = _resolve_search_type_enum()
    if search_type is None:
        return None

    for name in ("INSIGHTS", "GRAPH_COMPLETION"):
        st = getattr(search_type, name, None)
        if st is None:
            continue
        try:
            await asyncio.wait_for(
                cognee.search(query_type=st, query_text=query_text, save_interaction=True),
                timeout=_BEST_EFFORT_TIMEOUT_S,
            )
            return name
        except TypeError:
            # This cognee version's search() doesn't take save_interaction — the
            # FEEDBACK loop isn't available; give up quietly.
            return None
        except Exception as exc:  # noqa: BLE001 — best-effort, never raise
            logger.warning("save_interaction %s failed: %s", name, exc)
            continue
    return None


async def send_feedback(note: str, *, last_k: int = 1) -> bool:
    """Best-effort: reinforce the last interaction via ``SearchType.FEEDBACK``.

    Cognee ties the feedback score onto the graph elements that produced the
    last answer — the real API behind ``deja chat``'s "reinforce the exact
    nodes that helped" story. Timeout-guarded; returns True iff the call ran.
    """
    try:
        import cognee
    except ImportError:
        return False
    search_type = _resolve_search_type_enum()
    fb = getattr(search_type, "FEEDBACK", None) if search_type else None
    if fb is None:
        return False
    try:
        await asyncio.wait_for(
            cognee.search(query_type=fb, query_text=note, last_k=last_k),
            timeout=_BEST_EFFORT_TIMEOUT_S,
        )
        return True
    except Exception as exc:  # noqa: BLE001 — best-effort, never raise
        logger.warning("send_feedback failed: %s", exc)
        return False
