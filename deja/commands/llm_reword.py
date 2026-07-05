"""Optional LLM reword pass for the coaching response.

Design contract — read this before touching:

**Templated stays the default. This module is an opt-in polish, not a
replacement for the graph-driven answer.**

Two modes exist because they each answer a different judge:

1. Templated (default, recorded-demo path): "The coaching text is derived
   from graph facts, so the cross-topic link is provably graph reasoning,
   not the LLM guessing." Prove it by showing ``used_node_ids`` — the
   same link falls out with no LLM in the loop.

2. ``--llm`` (this module): "Same facts, LLM-worded." Surface polish for
   the video and first-glance read. The LLM is *forbidden* from
   introducing a concept, mistake, or cross-topic connection that was
   not in the FACTS block derived from ``used_node_ids``. Enforced two
   ways:

   - **Prompt constraint**: strict instruction to only reword the DRAFT
     using the supplied FACTS, and to omit any sentence it cannot ground.
   - **Post-hoc validator**: if the LLM output mentions any Concept name
     from the wider graph that is NOT in the allowed set, we throw the
     LLM output away and return the templated draft unchanged. That is
     the "prove it can't hallucinate a link" test — verified with a
     mock LLM that tries to inject a foreign Concept in the tests.

If the LLM call fails (dummy key, timeout, rate limit, provider down),
this returns the templated draft unchanged. Failures never surface as
demo-time exceptions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable


logger = logging.getLogger(__name__)


DUMMY_KEY_PREFIXES = ("sk-dummy", "sk-fake", "test-", "dummy")

# ``deja chat`` uses a fast, cheap model by default; override via env.
DEFAULT_MODEL = "gpt-4o-mini"

PROMPT_SYSTEM = """You are Déjà, a warm, practical coding mentor.

You will be given a DRAFT explanation and a FACTS block. Your job is to
rewrite the DRAFT into 2-3 short paragraphs in a natural mentor voice,
using only the concepts, mistakes, and connections listed in FACTS.

STRICT RULES:

1. Do NOT name any concept, topic, mistake, or cross-topic connection
   that is not present in FACTS. If you cannot ground a sentence in
   FACTS, omit that sentence.
2. Do NOT invent a new link between topics. The connections in FACTS
   are the ONLY allowed connections. If FACTS says two mistakes share
   a "failure_class," you may say that. You may not say two topics
   are related because they "both use Python" or any other reason.
3. General programming vocabulary is fine ("mutable state", "asyncio
   task", "async function"). What is NOT fine is naming a specific
   topic, library, or concept the FACTS block did not give you.
4. Keep it practical — no marketing, no filler, no "as an AI".

Output only the rewritten prose. No preamble, no headings, no bullet
points unless you're listing exactly the two fixes the DRAFT lists."""


@dataclass(frozen=True)
class RewordResult:
    """Result of a reword attempt.

    ``text`` is either the LLM's rewording (when ``used_llm`` is True)
    or the original templated draft (when the LLM was disabled, failed,
    or produced output the validator rejected). ``reason`` explains why
    ``used_llm`` is False — surfaced in the CLI so the demo operator
    knows which mode they're recording.
    """

    text: str
    used_llm: bool
    reason: str = ""


def is_dummy_key(api_key: str | None) -> bool:
    if not api_key:
        return True
    lower = api_key.lower()
    return any(lower.startswith(p) for p in DUMMY_KEY_PREFIXES)


def build_facts_block(
    topic_concept: str,
    related: list[tuple[str, str]],
    fix_hint: str,
) -> str:
    """Turn the coaching turn's node closure into a strict FACTS block.

    ``related`` is a list of (concept_ref, description) pairs — one per
    related Mistake pulled as cross-topic evidence.
    """
    lines = [
        f"- Topic the learner is coaching on: {topic_concept}",
    ]
    if related:
        lines.append("- Cross-topic evidence from the learner's memory:")
        for concept_ref, description in related:
            lines.append(
                f'    * On the concept "{concept_ref}", the learner has an '
                f'unresolved mistake: "{description}" '
                f"(same failure_class as the current topic)."
            )
    else:
        lines.append("- No cross-topic evidence pulled for this turn.")
    if fix_hint:
        lines.append(f"- Suggested fix pattern (only reword this, do not invent alternatives): {fix_hint}")
    return "\n".join(lines)


def build_allowed_concepts(
    topic_concept: str,
    related: list[tuple[str, str]],
) -> set[str]:
    """Concepts the LLM is allowed to name by identity.

    Case-normalized (lowercase) for downstream substring matching.
    """
    return {topic_concept.lower(), *(c.lower() for c, _ in related)}


def validate_no_hallucinated_concepts(
    output: str,
    all_graph_concepts: list[str],
    allowed_concepts: set[str],
) -> tuple[bool, str]:
    """Reject if the output names a graph Concept that isn't in the allowed set.

    Returns ``(ok, reason)``. ``ok=False`` means we must throw the LLM
    output away and fall back to templated.

    Only checks specific Concept **names** from the graph — not general
    vocabulary. That's the point: general phrasing is fine, naming a
    specific topic the FACTS didn't give the LLM is not.
    """
    lower = output.lower()
    for concept in all_graph_concepts:
        name = (concept or "").strip().lower()
        if not name:
            continue
        if name in allowed_concepts:
            continue
        # Word-boundary match to avoid nonsense hits inside longer words.
        pattern = r"\b" + re.escape(name) + r"\b"
        if re.search(pattern, lower):
            return False, f"LLM named a foreign concept: {concept!r}"
    if not output.strip():
        return False, "LLM returned empty output"
    return True, ""


def reword(
    templated_draft: str,
    topic_concept: str,
    related: list[tuple[str, str]],
    fix_hint: str,
    all_graph_concepts: list[str],
    api_key: str | None,
    *,
    model: str = DEFAULT_MODEL,
    completion_fn: Callable | None = None,
) -> RewordResult:
    """Attempt to reword ``templated_draft`` via LLM. Never raises.

    ``completion_fn`` is injectable so tests can drive the validator with
    canned LLM outputs (including hallucinated ones — that's the test
    that matters).
    """
    if is_dummy_key(api_key):
        return RewordResult(
            text=templated_draft,
            used_llm=False,
            reason="no real LLM_API_KEY set — templated mode",
        )

    facts = build_facts_block(topic_concept, related, fix_hint)
    allowed = build_allowed_concepts(topic_concept, related)
    prompt_user = f"FACTS:\n{facts}\n\nDRAFT:\n{templated_draft}"

    try:
        if completion_fn is None:
            import litellm  # heavyweight; imported lazily
            completion_fn = litellm.completion

        response = completion_fn(
            model=model,
            messages=[
                {"role": "system", "content": PROMPT_SYSTEM},
                {"role": "user", "content": prompt_user},
            ],
            temperature=0.4,
            max_tokens=400,
            api_key=api_key,
        )
        output = _extract_content(response)
    except Exception as exc:  # noqa: BLE001 — any LLM failure falls back
        logger.warning("LLM reword failed: %s", exc)
        return RewordResult(
            text=templated_draft,
            used_llm=False,
            reason=f"LLM call failed: {type(exc).__name__}",
        )

    ok, reason = validate_no_hallucinated_concepts(
        output, all_graph_concepts, allowed
    )
    if not ok:
        return RewordResult(
            text=templated_draft,
            used_llm=False,
            reason=f"validator rejected LLM output ({reason})",
        )

    return RewordResult(text=output.strip(), used_llm=True)


def _extract_content(response) -> str:
    """Normalize a litellm/openai-shaped response into a plain string."""
    if isinstance(response, str):
        return response
    # dict-shaped
    if isinstance(response, dict):
        try:
            return response["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return ""
    # object-shaped (litellm.ModelResponse)
    choices = getattr(response, "choices", None)
    if choices:
        first = choices[0]
        message = getattr(first, "message", None) or (first.get("message") if isinstance(first, dict) else None)
        if message:
            content = getattr(message, "content", None)
            if content is None and isinstance(message, dict):
                content = message.get("content")
            return content or ""
    return ""
