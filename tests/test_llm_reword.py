"""Polish C tests: the LLM reword mode is provably hallucination-safe.

The key claim: with ``--llm`` enabled, the LLM's role is *only* to reword
the templated DRAFT using the supplied FACTS. It may not introduce a
Concept, Mistake, or cross-topic connection the FACTS didn't give it.

Templated remains the demo default; these tests confirm that when LLM
mode IS engaged, the graph-driven story is not undermined by an LLM that
guessed at a link.
"""

from __future__ import annotations

from deja.commands.llm_reword import (
    build_allowed_concepts,
    build_facts_block,
    is_dummy_key,
    reword,
    validate_no_hallucinated_concepts,
)


ALL_GRAPH_CONCEPTS = [
    "recursion",
    "mutable default arguments",
    "async error handling",
    "shared mutable state",
    "python 2 print statement",
]


TEMPLATED_DRAFT = (
    "This looks like the same shape as the mutable default arguments bug you "
    "hit before — Default list reused across calls. Both are shared-mutable-"
    "state: state you thought was fresh is actually shared across calls or tasks."
)


def test_dummy_key_bypasses_llm() -> None:
    """A dummy key returns the templated draft unchanged — no accidental cost."""
    result = reword(
        templated_draft=TEMPLATED_DRAFT,
        topic_concept="async error handling",
        related=[("mutable default arguments", "Default list reused")],
        fix_hint="never share mutable state",
        all_graph_concepts=ALL_GRAPH_CONCEPTS,
        api_key="sk-dummy-1234",
    )
    assert result.used_llm is False
    assert result.text == TEMPLATED_DRAFT
    assert "LLM_API_KEY" in result.reason or "templated" in result.reason.lower()


def test_missing_key_bypasses_llm() -> None:
    result = reword(
        templated_draft=TEMPLATED_DRAFT,
        topic_concept="async error handling",
        related=[],
        fix_hint="",
        all_graph_concepts=ALL_GRAPH_CONCEPTS,
        api_key=None,
    )
    assert result.used_llm is False


def test_validator_rejects_hallucinated_foreign_concept() -> None:
    """The critical anti-hallucination test.

    The LLM tries to inject a Concept name from the graph that was NOT in
    the allowed set (from used_node_ids). Validator MUST catch it — that's
    what preserves the "connections come from the graph, not the LLM."
    """
    allowed = build_allowed_concepts(
        topic_concept="async error handling",
        related=[("mutable default arguments", "Default list reused")],
    )
    # The LLM has slipped "recursion" (a foreign Concept present in the wider
    # graph) into its answer — that's an invented cross-topic link.
    llm_output = (
        "Your async bug is actually the same failure pattern as the "
        "recursion base case bug — both let state escape one scope."
    )
    ok, reason = validate_no_hallucinated_concepts(
        llm_output, ALL_GRAPH_CONCEPTS, allowed
    )
    assert ok is False
    assert "recursion" in reason.lower()


def test_validator_accepts_output_using_only_allowed_concepts() -> None:
    """Clean rewording that only uses supplied FACTS must be accepted."""
    allowed = build_allowed_concepts(
        topic_concept="async error handling",
        related=[("mutable default arguments", "Default list reused")],
    )
    llm_output = (
        "You're running into the same failure shape you saw with mutable "
        "default arguments a week ago — state you assumed was fresh is "
        "actually shared. For async error handling, the cure is to make "
        "each task own its own collection."
    )
    ok, reason = validate_no_hallucinated_concepts(
        llm_output, ALL_GRAPH_CONCEPTS, allowed
    )
    assert ok is True, reason


def test_validator_allows_general_vocabulary() -> None:
    """General terms ('asyncio', 'lock', 'mutable state') are not graph Concept names — allowed."""
    allowed = build_allowed_concepts(
        topic_concept="async error handling",
        related=[],
    )
    llm_output = (
        "Consider guarding the shared list with an asyncio.Lock when sharing "
        "is deliberate. Otherwise give each task its own collection."
    )
    ok, _ = validate_no_hallucinated_concepts(
        llm_output, ALL_GRAPH_CONCEPTS, allowed
    )
    assert ok is True


def test_end_to_end_fake_llm_that_hallucinates_falls_back_to_templated() -> None:
    """The full reword() path with an injected LLM that tries to hallucinate.

    This is the "prove it can't hallucinate a link" test: the fake LLM
    produces output that names a foreign Concept ('recursion') that wasn't
    in the FACTS. reword() MUST return the templated draft, not the LLM
    output.
    """

    def fake_hallucinating_llm(**_kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "You're seeing what you saw with recursion — the "
                            "base-case problem shows up here too."
                        )
                    }
                }
            ]
        }

    result = reword(
        templated_draft=TEMPLATED_DRAFT,
        topic_concept="async error handling",
        related=[("mutable default arguments", "Default list reused")],
        fix_hint="never share mutable state",
        all_graph_concepts=ALL_GRAPH_CONCEPTS,
        api_key="sk-real-looking-key-abc",
        completion_fn=fake_hallucinating_llm,
    )
    assert result.used_llm is False, (
        "hallucinated LLM output must not be accepted — this is the whole "
        "'graph reasoning, not LLM guessing' claim"
    )
    assert result.text == TEMPLATED_DRAFT
    assert "recursion" in result.reason.lower()


def test_end_to_end_fake_llm_clean_output_is_used() -> None:
    """When the LLM plays by the rules, reword() surfaces its output."""

    def fake_clean_llm(**_kwargs):
        return {
            "choices": [
                {
                    "message": {
                        "content": (
                            "Same failure family as your mutable default "
                            "arguments session — mutable state escaping its "
                            "scope. Give each task its own collection or "
                            "guard the shared one with an asyncio.Lock."
                        )
                    }
                }
            ]
        }

    result = reword(
        templated_draft=TEMPLATED_DRAFT,
        topic_concept="async error handling",
        related=[("mutable default arguments", "Default list reused")],
        fix_hint="never share mutable state",
        all_graph_concepts=ALL_GRAPH_CONCEPTS,
        api_key="sk-real-looking-key-abc",
        completion_fn=fake_clean_llm,
    )
    assert result.used_llm is True
    assert "mutable default arguments" in result.text


def test_end_to_end_llm_error_falls_back_to_templated() -> None:
    """API error / rate limit / provider down all fall back to templated silently."""

    def fake_failing_llm(**_kwargs):
        raise RuntimeError("simulated provider timeout")

    result = reword(
        templated_draft=TEMPLATED_DRAFT,
        topic_concept="async error handling",
        related=[],
        fix_hint="",
        all_graph_concepts=ALL_GRAPH_CONCEPTS,
        api_key="sk-real-looking-key-abc",
        completion_fn=fake_failing_llm,
    )
    assert result.used_llm is False
    assert result.text == TEMPLATED_DRAFT
    assert "RuntimeError" in result.reason


def test_facts_block_contains_only_supplied_evidence() -> None:
    """The FACTS block is the LLM's ground truth — must include exactly what we supplied."""
    facts = build_facts_block(
        topic_concept="async error handling",
        related=[
            ("mutable default arguments", "Default list reused across calls"),
        ],
        fix_hint="never share mutable state",
    )
    assert "async error handling" in facts
    assert "mutable default arguments" in facts
    assert "Default list reused across calls" in facts
    # Nothing from outside the supplied set.
    assert "recursion" not in facts
    assert "python 2" not in facts


def test_is_dummy_key_catches_common_placeholders() -> None:
    assert is_dummy_key("") is True
    assert is_dummy_key(None) is True
    assert is_dummy_key("sk-dummy") is True
    assert is_dummy_key("sk-dummy-not-called") is True
    assert is_dummy_key("test-key") is True
    assert is_dummy_key("sk-real-abc123") is False
