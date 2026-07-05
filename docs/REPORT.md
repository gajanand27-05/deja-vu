# Déjà, completion report

Everything below is verifiable from a clean clone.

## 1. What was built

A CLI coding mentor that remembers the learner across sessions, built on Cognee's memory graph. It proves, end to end, that Cognee's memory verbs (remember, recall, improve, memify, forget) can carry real product weight, with the graph re-organization ("memify") as the headline moment. It runs fully local on Cognee's embedded stack (SQLite, LanceDB, Kuzu), with an optional Cognee Cloud path.

On top of the core verb flow it also ships:

- `deja ask "<question>"`, which routes recall through Cognee's own `cognee.search` over the populated graph.
- `deja compare`, which answers the same question without memory and with the graph side by side (the "context hangover", dramatized).
- Cross-restart session recall: `deja start` recalls the last real session after the process is killed and reopened.
- `SearchType.FEEDBACK` on thumbs-up, so improve attaches a score to the exact graph elements that produced the answer.
- `deja ask --cloud`, which runs the same recall against Cognee Cloud.

Repo: https://github.com/gajanand27-05/deja-vu

## 2. Cognee verb coverage

| Verb | Where it lives | What it does here |
|---|---|---|
| remember | `deja seed`, `deja chat` | Writes Learner / Concept / Skill / Session / Mistake DataPoint nodes and every explicit edge (HAS_SKILL, OF_CONCEPT, TOUCHED, REVEALED, INDICATES_GAP_IN). |
| recall | `deja start`, `deja chat`, `deja ask` | Reads graph state for the cold open (three lines, not hardcoded) and recalls the last persisted Session across restarts; coaching pulls cross-topic Mistake evidence; `deja ask` runs a real `cognee.search` (INSIGHTS, then GRAPH_COMPLETION, then SUMMARIES) over the graph. |
| improve | `deja chat --feedback up` | Bumps mastery_weight and confidence on the specific Skill and Mistake nodes that produced the answer (not a global counter), and additively fires Cognee's `SearchType.FEEDBACK` on that interaction. |
| memify | `deja memify` | Adds Mistake SAME_FAMILY_AS Mistake between Mistakes on different Concepts sharing failure_class; adds Concept RELATED_TO Concept from Session co-occurrence; re-weights involved Skills upward. Idempotent. |
| forget | `deja forget` | Soft: decays mastered Skills that have gone stale (mastery_weight x 0.6, status becomes decaying). Hard: prunes Concepts with deprecated=True along with their orphan Skills. |

## 3. Command surface

`seed`, `start`, `chat`, `ask`, `compare`, `memify`, `forget`, `ui`, `doctor`, `capture`, `version`. Each is a Typer subcommand with Rich output. `deja doctor` prints the resolved data dir, learner, LLM config, and key status for a fast sanity check on a fresh machine.

## 4. The demo's headline invariant, verified

The `SAME_FAMILY_AS` edge must not exist in the seed. memify creates it live, or there is nothing to show.

Verified two ways:

1. Unit tests (`tests/test_schema_and_seed.py::test_seed_edges_are_explicit_only`, `tests/test_memify.py::test_seed_state_produces_exactly_one_family_edge`): the seed's edge builder never emits `SAME_FAMILY_AS` or `RELATED_TO`, and memify inference on the seeded Mistake pair produces exactly one family edge.
2. End to end: after `deja seed`, the snapshot contains 14 edges with zero `SAME_FAMILY_AS`. After `deja memify`, it contains 15 edges with exactly one `SAME_FAMILY_AS` linking M1 (mutable-defaults) to M2 (async error handling). A second `deja memify` reports "nothing to re-organize" (idempotent).

## 5. End-to-end flow, confirmed

```
deja seed     -> 14 nodes / 14 edges, 0 SAME_FAMILY_AS
deja start    -> cold open reads recursion (mastered 0.9), mutable-defaults
                 (0.3 + unresolved Mistake), current_focus "async error handling",
                 plus a recall line for the last persisted session. None hardcoded.
deja chat --topic "async error handling" --feedback up
              -> mentor references the mutable-defaults Mistake as evidence
                 (same failure_class as M2); async Skill 0.45 -> 0.55
deja ask "why do I keep hitting this?"
              -> cognee.search over the graph, shown next to the graph-derived answer
deja compare  -> same question answered without memory vs. with the graph (read-only)
deja memify   -> adds M1 SAME_FAMILY_AS M2; bumps mutable-defaults (0.30 -> 0.35)
                 and async (0.55 -> 0.60); snapshot 15 edges
deja forget --topic recursion
              -> recursion Skill 0.90 -> 0.54, status decaying (dimmed in UI);
                 "python 2 print statement" Concept and its orphan Skill pruned
```

## 6. Cognee integration, honest scope

The templated, graph-derived path is the verified default and the recorded-demo path: the cross-topic link falls out of `used_node_ids` with no LLM in the loop, so the "graph reasoning, not LLM guessing" story is provable, not asserted.

The `cognee.search`, `SearchType.FEEDBACK`, and `--cloud` calls are real Cognee API calls made best-effort and timeout-guarded. They enrich the output when the installed Cognee version supports them, and fall back to the deterministic local answer otherwise, so the core flow never breaks. `spike_cognee.py` confirms the exact search shape on a target machine.

## 7. Architecture

- Language: Python 3.12 (supports 3.10 to 3.14).
- Memory backend: Cognee with the embedded stack (SQLite, LanceDB, Kuzu). No servers required. Optional Cognee Cloud via `deja ask --cloud`.
- Custom graph model: Pydantic subclasses of `cognee.infrastructure.engine.DataPoint` with `Annotated[..., Dedup(), Embeddable()]` markers, so identity is deterministic and embedding-eligible fields are declared. Concept and Skill are separate classes; the personalized, mutable story depends on that split.
- CLI: Typer + Rich.
- Graph view: FastAPI + vis.js. Nodes sized by mastery_weight so weight changes are visible; `SAME_FAMILY_AS` rendered bold magenta and briefly flashed when it first appears.
- Concurrency: the embedded graph store is single-writer, so the UI cannot hold the DB while the CLI mutates. Every mutating command flushes `data/ui_snapshot.json`; the server serves that file on a 2s poll. UI and CLI run concurrently through the full seed to memify to forget cycle without lock conflicts.

## 8. Testing

`pytest tests/`: 42 tests, all pass. Coverage highlights:

- `test_schema_and_seed.py`: schema split, exact seed weights, no inferred edges in seed, every explicit rel type used, deterministic learner id.
- `test_cold_open.py`: cold open picks mastered over deprecated, picks the lowest-weight unresolved Mistake, reads current_focus, mentions all three topics, empty-graph fallback, recalls the most-recent persisted Session (cross-restart proof), omits the recall line when no sessions exist.
- `test_chat.py`: find_by_prop, used-node-ids includes evidence (no global counter), and the with-memory vs. no-memory composer that powers `deja compare` (cross-topic answer names the other topic; baseline cannot; unknown topic returns None).
- `test_memify.py`: cross-topic linkage rule, same-topic rejected, different failure_class rejected, idempotence, exact seed shape produces one family edge, RELATED_TO co-occurrence and its idempotence.
- `test_forget.py`: mastered and stale decays, in-progress does not decay when stale, recent does not decay, already-decaying skipped, `--topic` force decay, deprecated Concept pruned with its orphan Skill.
- `test_llm_reword.py`: dummy-key / empty / failed-call fallbacks, FACTS-block construction, allowed-concept set, and the adversarial hallucination-safety checks (foreign-concept output rejected, templated served).
- `test_smoke.py`: version and help list all commands.

## 9. File layout (shipped)

```
deja-vu/
├── README.md, pyproject.toml, .env.example, LICENSE
├── docs/
│   ├── AI_DISCLOSURE.md          # hackathon rule compliance
│   └── REPORT.md                 # this file
├── deja/
│   ├── cli.py                    # Typer entry: seed, start, chat, ask, compare,
│   │                             #   memify, forget, ui, doctor, capture, version
│   ├── config.py                 # env + settings
│   ├── models/graph.py           # Pydantic DataPoint subclasses + Rel constants
│   ├── store/
│   │   ├── env.py                # cognee data-root pinning
│   │   ├── graph_store.py        # ensure_setup, wipe, add_nodes/edges, snapshot, export
│   │   ├── search.py             # recall via cognee.search + SearchType.FEEDBACK
│   │   └── cloud.py              # optional Cognee Cloud connection
│   ├── commands/
│   │   ├── seed_cmd.py           # deterministic BEFORE state
│   │   ├── start_cmd.py          # cold-open recall + cross-restart session recall
│   │   ├── chat_cmd.py           # coaching + cross-topic evidence + improve + compare
│   │   ├── ask_cmd.py            # deja ask: cognee.search over the graph
│   │   ├── memify_cmd.py         # SAME_FAMILY_AS + RELATED_TO + re-weight
│   │   ├── forget_cmd.py         # decay + prune
│   │   └── capture_cmd.py        # Playwright before/after PNGs (optional)
│   └── ui/
│       ├── server.py             # FastAPI serving snapshot JSON
│       ├── graph_api.py          # node/edge to vis.js payload
│       └── static/index.html     # vis.js viewer, 2s poll, flash on new edges
└── tests/                        # 42 tests (7 modules)
```

`CLAUDE.md` is a repo-local design brief kept in the working tree but gitignored on purpose. It is internal agent context, not a project doc.

## 10. Known limitations and non-goals

- Two coaching modes, templated is the default. The default `deja chat` builds a deterministic response from graph facts; that is the credibility flex. `deja chat --llm` is opt-in surface polish that reworks the same graph facts through an LLM constrained to a pre-selected FACTS block, with a post-hoc validator that rejects any output naming a Concept the graph did not authorize. On rejection or LLM failure, the templated draft is served, so the demo path is uninterruptible. See `deja/commands/llm_reword.py` and the ten hallucination-safety tests.
- Best-effort Cognee calls. `cognee.search`, `SearchType.FEEDBACK`, and `--cloud` are timeout-guarded and fall back to the local graph answer, so an unexpected Cognee version or a slow cloud never stalls the demo.
- Single-user demo. Multi-user access control is off (`ENABLE_BACKEND_ACCESS_CONTROL=false`). A scoping choice, not a Cognee limitation.
- Playwright capture is optional. It needs the `[capture]` extra plus `playwright install chromium`. The demo does not depend on it.

## 11. Authorship

See `git log` on `main` for the full history. All commits are authored by the team's human participants; AI-generated output was reviewed, tested, and accepted rather than shipped unverified (see `docs/AI_DISCLOSURE.md`).
