# Déjà — completion report

Handed off before the final push. Everything below is verifiable from a clean clone.

## 1 · What was built

A CLI coding mentor that remembers the learner across sessions, built on Cognee 1.2.2's memory graph. The product exists to prove — end to end, in ~4 minutes — that all four Cognee memory verbs (`remember` / `recall` / `improve` / `memify` / `forget`) can carry real product weight, with the graph re-organization ("memify") as the headline moment.

Repo: https://github.com/gajanand27-05/deja-vu

## 2 · Cognee verb coverage

| Verb | Where it lives | What it does here |
|---|---|---|
| `remember` | `deja seed`, `deja chat` | Writes Learner/Concept/Skill/Session/Mistake DataPoint nodes and every explicit edge from spec §3 (`HAS_SKILL`, `OF_CONCEPT`, `TOUCHED`, `REVEALED`, `INDICATES_GAP_IN`). |
| `recall` | `deja start`, `deja chat` | Reads the graph snapshot to produce the three cold-open lines from graph state (not hardcoded), and pulls cross-topic Mistake evidence into the coaching turn. |
| `improve` | `deja chat --feedback up` | Bumps `mastery_weight` (+0.1) and `confidence` (+0.1) on the *specific* Skill and Mistake nodes that produced the answer — not a global counter. |
| `memify` | `deja memify` | Adds `Mistake —SAME_FAMILY_AS→ Mistake` between Mistakes on *different* Concepts sharing `failure_class`; adds `Concept —RELATED_TO→ Concept` from Session co-occurrence; re-weights involved Skills upward. Idempotent. |
| `forget` | `deja forget` | Soft: decays mastered Skills that have gone stale (mastery_weight × 0.6, status → decaying). Hard: prunes Concepts with `deprecated=True` along with their orphan Skills. |

## 3 · The demo's headline invariant, verified

From spec §3: the `SAME_FAMILY_AS` edge must not exist in the seed — memify creates it live in Scene 3, or there's nothing to show.

Verified two ways:

1. **Unit tests** (`tests/test_schema_and_seed.py::test_seed_edges_are_explicit_only`, `tests/test_memify.py::test_seed_state_produces_exactly_one_family_edge`): the seed's edge builder never emits `SAME_FAMILY_AS` or `RELATED_TO`, and the memify inference on the seeded Mistake pair produces exactly one family edge.
2. **End-to-end**: after `deja seed`, the snapshot contains 14 edges with zero `SAME_FAMILY_AS`. After `deja memify`, the snapshot contains 15 edges with exactly one `SAME_FAMILY_AS` linking M1 (mutable-defaults) to M2 (async error handling). Running `deja memify` a second time reports "nothing to re-organize" — idempotent.

## 4 · End-to-end demo flow, confirmed

```
deja seed     → 14 nodes / 14 edges, 0 SAME_FAMILY_AS
deja start    → cold open reads recursion (mastered 0.9), mutable-defaults
                (0.3 + unresolved Mistake), current_focus "async error handling"
                — all three lines from graph state, none hardcoded
deja chat --topic "async error handling" --feedback up
              → mentor references the mutable-defaults Mistake as evidence
                (same failure_class as M2); async Skill 0.45 → 0.55
deja memify   → adds M1—SAME_FAMILY_AS—M2; bumps mutable-defaults (0.30 → 0.35)
                and async (0.55 → 0.60); snapshot 15 edges
deja forget --topic recursion
              → recursion Skill 0.90 → 0.54, status decaying (dimmed in UI);
                python 2 print statement Concept and its orphan Skill pruned;
                snapshot 12 nodes / 13 edges
```

Every step was verified against a live cognee/Ladybug graph. Confirmations printed above.

## 5 · Architecture

- **Language**: Python 3.12 (supports 3.10+).
- **Memory backend**: Cognee 1.2.2 with embedded Ladybug (default). No servers.
- **Custom graph model**: Pydantic subclasses of `cognee.infrastructure.engine.DataPoint` with `Annotated[..., Dedup(), Embeddable()]` markers so identity is deterministic and embedding-eligible fields are declared. Concept + Skill kept as separate classes — the "personalized/mutable" story depends on that split (spec §2).
- **CLI**: Typer + Rich, dark-theme tables for the demo screens.
- **Graph view**: FastAPI + vis.js (CDN). Nodes sized by `mastery_weight` so weight changes are visible; `SAME_FAMILY_AS` rendered bold magenta and briefly flashed yellow when it first appears.
- **Concurrency**: Ladybug is single-writer, so the UI can't hold the DB while the CLI mutates. Solved by having every mutation command flush a JSON snapshot to `data/ui_snapshot.json`; the server serves that file, refreshed on a 2s poll. Tested: UI and CLI ran concurrently through the full seed → memify → forget cycle without lock conflicts.

## 6 · Testing

`pytest tests/` — **27 tests, all pass**. Coverage highlights:

- `test_schema_and_seed.py` (5): schema split, exact seed weights, no inferred edges in seed, every explicit rel type actually used, deterministic learner id.
- `test_cold_open.py` (5): cold open picks mastered-over-deprecated, picks lowest-weight-unresolved-Mistake, reads current_focus from Learner, mentions all three topics, empty-graph fallback.
- `test_chat.py` (2): find_by_prop, used-node-ids includes evidence (no global counter).
- `test_memify.py` (7): cross-topic linkage rule, same-topic rejected, different failure_class rejected, idempotence, exact seed shape produces one family edge, RELATED_TO co-occurrence, RELATED_TO idempotence.
- `test_forget.py` (6): mastered+stale decays, in-progress doesn't decay when stale, recent doesn't decay, already-decaying skipped (idempotent), --topic force decay, deprecated Concept pruned with its orphan Skill.
- `test_smoke.py` (2): version, help lists all planned commands.

## 7 · File layout (shipped)

```
deja-vu/
├── README.md                     # user-facing, terse
├── pyproject.toml                # deja package + [dev] + [capture] extras
├── .env.example                  # LLM_API_KEY template
├── .gitignore                    # excludes .venv, data/, captures/, CLAUDE.md
├── docs/
│   ├── AI_DISCLOSURE.md          # hackathon rule compliance
│   ├── DEMO.md                   # 4-min rehearsal walkthrough
│   └── REPORT.md                 # this file
├── deja/
│   ├── cli.py                    # Typer entry: seed, start, chat, memify,
│   │                             #             forget, ui, capture, doctor, version
│   ├── config.py                 # env + settings
│   ├── models/
│   │   └── graph.py              # Pydantic DataPoint subclasses + Rel constants
│   ├── store/
│   │   ├── env.py                # cognee data-root pinning
│   │   └── graph_store.py        # ensure_setup, wipe, add_nodes/edges,
│   │                             #  graph_snapshot, update_node_properties,
│   │                             #  export_snapshot_to_file
│   ├── commands/
│   │   ├── seed_cmd.py           # deterministic BEFORE state
│   │   ├── start_cmd.py          # cold-open recall (three lines from graph)
│   │   ├── chat_cmd.py           # coaching + cross-topic evidence + improve
│   │   ├── memify_cmd.py         # SAME_FAMILY_AS + RELATED_TO + re-weight
│   │   ├── forget_cmd.py         # decay + prune
│   │   └── capture_cmd.py        # Playwright before/after PNGs
│   └── ui/
│       ├── server.py             # FastAPI serving snapshot JSON
│       ├── graph_api.py          # node/edge → vis.js payload
│       └── static/index.html     # vis.js viewer with 2s polling + flash on new edges
└── tests/
    ├── test_smoke.py
    ├── test_schema_and_seed.py
    ├── test_cold_open.py
    ├── test_chat.py
    ├── test_memify.py
    └── test_forget.py
```

`CLAUDE.md` is a repo-local design brief kept in the working tree but gitignored on purpose — internal agent context, not a project doc.

## 8 · Known limitations, risks, and non-goals

- **Prose is deterministic, not LLM-generated.** The coaching response is templated from graph facts so the demo rehearses cleanly. Cognee's `LLM_API_KEY` is still needed for the DB stack to boot, but no LLM call is made per turn. This trades "the mentor is an LLM" for "the mentor's cross-topic reach is provably graph-driven" — a fair trade for a hackathon judged on Cognee integration depth.
- **Single-user demo.** Multi-user access control is turned off (`ENABLE_BACKEND_ACCESS_CONTROL=false`). Not a limitation of Cognee — a scoping choice.
- **Ladybug single-writer.** Solved for the demo via the snapshot-file pattern. Migrating to Postgres/Neo4j would remove that constraint if scaled beyond one learner.
- **Playwright capture is optional.** Requires the `[capture]` extra plus `playwright install chromium` (~150 MB). The demo does not depend on it — it's the Scene 3 fallback.
- **Windows line-endings warnings** from git are expected on Windows (CRLF conversion). No functional impact.

## 9 · Rehearsal-lock rules (please observe)

- Re-run `deja seed` immediately before going on stage. Do not touch the DB between seed and demo.
- Do not open two `deja` mutation commands concurrently (Ladybug single-writer). UI + one CLI is fine.
- Do not add `SAME_FAMILY_AS` seeded edges "to make the graph look denser." That kills the memify beat.

## 10 · Commit history

```
6491b0c  Phase 6 — live graph view + before/after capture
1d5b9f1  Phase 5 — forget: soft decay + hard prune (Scene 4)
6f21d30  Phase 4 — memify: the SAME_FAMILY_AS wow moment (Scene 3)
f1bbb6e  Phase 3 — coaching loop + improve on the exact nodes used (Scene 2)
2435bd8  Phase 2 — cold open (Scene 1): three greeting lines derived from the graph
4bebec2  Phase 1 — Schema (Pydantic graph models) + deterministic seed
87812ea  Phase 0 — Scaffold
806f67a  Initial commit
```

Every commit is authored by `gajanand27-05 <gajanandvd2005@gmail.com>` on `main`.

## 11 · What ships to `main` after this report

The final push adds:
- `docs/DEMO.md` — the rehearsal walkthrough,
- `docs/REPORT.md` — this report,
- Updated `docs/AI_DISCLOSURE.md`,
- A short polish/lint pass if anything shows up during the final `pytest` run.

Nothing else. The functional code has been shipping per-phase all along.
