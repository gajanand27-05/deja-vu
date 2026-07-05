<div align="center">

# Déjà

### The coding mentor that remembers you.

*Your AI has a hangover: it wakes up every session with no memory of last night. Déjà doesn't.*

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-42%2F42%20passing-brightgreen.svg)](#testing)
[![Built on Cognee](https://img.shields.io/badge/built%20on-Cognee-8A2BE2.svg)](https://www.cognee.ai/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

Déjà is a command-line coding mentor built on **[Cognee](https://www.cognee.ai/)**. It keeps a persistent, **typed knowledge graph** of your learning (the concepts you've mastered, the mistakes you've made, and how they connect) so every session opens where you left off, coaching is grounded in your real history, and the memory **re-organizes itself** to get smarter over time.

It runs **fully local** on Cognee's embedded stack (SQLite + LanceDB + Kuzu), no servers, no cloud required, and is **Python** end to end.

### Highlights

- 🧠 **`memify`: the verb nobody demos.** The graph infers a *new* cross-topic link nobody wrote: two bugs from different topics recognized as the same failure family. Memory that gets **smarter**, not just bigger.
- 🔁 **No context hangover, across restarts.** `deja start` recalls your last real session after you kill the process and reopen: memory lives in the graph on disk, not a chat log.
- ⚖️ **With-memory vs. without, side by side.** `deja compare` answers the same question twice: only the graph-backed answer reaches across your history.
- 🔌 **Grounded in Cognee's real APIs.** `deja ask` routes recall through Cognee's own **`cognee.search`**; a thumbs-up additionally fires Cognee's **`SearchType.FEEDBACK`** on the exact interaction; `--cloud` runs recall on Cognee Cloud.
- 🔎 **Provably graph-driven.** The cross-topic link falls out of `used_node_ids` with *no LLM in the loop*: traceable, not asserted.

---

## Table of contents

- [Why this is a real memory system](#why-this-is-a-real-memory-system-not-rag-with-extra-steps)
- [Quickstart](#quickstart)
- [Command reference](#command-reference)
- [See the graph re-organize (the money shot)](#see-the-graph-re-organize-the-money-shot)
- [The verified flow](#the-verified-flow)
- [How Déjà uses Cognee](#how-déjà-uses-cognee)
- [Architecture](#architecture)
- [Configuration](#configuration)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Design notes](#design-notes-honest-trade-offs)
- [Troubleshooting](#troubleshooting)
- [AI assistance](#ai-assistance) · [License](#license)

---

## Why this is a real memory system, not "RAG with extra steps"

Most agent-memory demos use two verbs: *store* and *retrieve*. Déjà uses **all four** of Cognee's memory verbs as load-bearing features, and leans hardest on the one almost nobody demos:

> **`memify`: the verb every other memory system doesn't have.**
>
> After a session, Déjà's graph *infers a connection nobody wrote*: it links a mutable-defaults bug and an async shared-state bug as the same failure family, because they share an underlying failure class. The memory didn't just get bigger: it got smarter.

| Verb | Commands | What it does here |
|------|----------|-------------------|
| `remember` | `deja seed`, `deja chat` | Writes typed `DataPoint` nodes (`Learner`, `Concept`, `Skill`, `Session`, `Mistake`) + explicit edges into the graph |
| `recall` | `deja start`, `deja chat`, `deja ask` | Cold open derives its greeting from graph state (not hardcoded) **and** recalls your last session across restarts; coaching pulls cross-topic mistake evidence; `deja ask "<q>"` runs a real `cognee.search` over the graph |
| `improve` | `deja chat --feedback up` | Re-weights `mastery_weight` + `confidence` on the *exact* nodes that produced the answer (not a global counter), and additively fires Cognee's own `SearchType.FEEDBACK` on that interaction |
| `memify` | `deja memify` | Infers and adds `Mistake -SAME_FAMILY_AS→ Mistake` across topics with a shared failure class; re-weights skills; idempotent |
| `forget` | `deja forget` | Soft-decays stale mastered skills out of active coaching; hard-prunes deprecated concepts and orphaned nodes |

---

## Quickstart

**Requirements:** Python 3.10–3.14, and an LLM provider key (used to boot Cognee's stack).

```bash
# 1. Install
git clone https://github.com/gajanand27-05/deja-vu
cd deja-vu
pip install -e .

# 2. Configure
cp .env.example .env
#   edit .env → set LLM_API_KEY   (see Configuration below)

# 3. Seed the learner's history (locks the demo BEFORE state)
deja seed
```

Then run the flow:

```bash
deja start                                # cold open: the mentor already knows you (recalls your last session)
deja chat                                 # ask a coding question; pulls cross-topic evidence
deja chat --feedback up                   # reinforce a good explanation (improve)
deja ask "why do I keep hitting this?"    # recall via Cognee's own cognee.search over the graph
deja compare                              # same question WITHOUT memory vs. WITH the graph: the hangover, dramatized
deja memify                               # the graph re-organizes itself: the SAME_FAMILY_AS edge appears
deja forget                               # mastered topics decay; deprecated tech is pruned
```

> **New to a repo?** `deja doctor` prints the resolved data dir, learner, LLM config, and whether your key is set. Run it first if anything looks off.

---

## Command reference

| Command | Purpose | Key options |
|---------|---------|-------------|
| `deja seed` | Build the demo BEFORE state: typed nodes + explicit edges, **zero** inferred edges | None |
| `deja start` | Cold open: recall who you are from graph state, including your last session | None |
| `deja chat` | Coaching turn: cross-topic evidence + thumbs feedback (improve) | `-t/--topic`, `-q/--question`, `-f/--feedback up\|down\|none`, `--llm` |
| `deja ask "<q>"` | Recall via Cognee's own `cognee.search`, shown next to a graph-derived answer | `--cloud` |
| `deja compare` | Same question answered without memory vs. with the graph (read-only) | `-t/--topic`, `-q/--question` |
| `deja memify` | Re-organize the graph: infer `SAME_FAMILY_AS` links + re-weight skills (idempotent) | None |
| `deja forget` | Decay stale mastered skills; prune deprecated concepts + orphans | `-t/--topic` |
| `deja ui` | Serve the live vis.js graph viewer | `--host`, `--port` (default `127.0.0.1:8765`) |
| `deja doctor` | Print resolved env / data dir / LLM config / key status | None |
| `deja capture` | Write BEFORE/AFTER PNGs of the graph (Scene 3 fallback; needs the `[capture]` extra) | `--host`, `--port` |
| `deja version` | Print the installed version | None |

`--llm` on `deja chat` is opt-in surface polish: it rewords the **templated, graph-derived** answer through an LLM, constrained to only rephrase facts traceable to `used_node_ids`, and falls back to the templated answer on any failure or hallucination. Templated is the default and the graph-driven guarantee holds either way.

---

## See the graph re-organize (the money shot)

In a spare terminal:

```bash
deja ui        # serves the live graph at http://127.0.0.1:8765/
```

Open the browser, then run `deja memify` in your main terminal. On the 2-second poll the graph re-renders: the new `SAME_FAMILY_AS` edge flashes in (bold magenta), the camera pans to it, a **"cross-topic family inferred"** caption fades in, and re-weighted skill nodes visibly thicken.

---

## The verified flow

A full end-to-end run, with the exact graph deltas at each stage:

```
deja seed    → 14 nodes / 14 edges, 0 SAME_FAMILY_AS      (invariant: no inferred edges in seed)
deja start   → three greeting lines derived from graph state
deja chat    → mutable-defaults Mistake pulled as cross-topic evidence for an async question
               improve: async skill 0.45 → 0.55           (still 0 SAME_FAMILY_AS)
deja memify  → +1 SAME_FAMILY_AS (M1 ↔ M2); skills thicken (mutable-defaults 0.30→0.35, async 0.55→0.60)
deja forget  → recursion 0.90 → 0.54 (decaying); Python-2 concept + orphan skill pruned
deja memify  → "nothing to re-organize"                   (idempotent)
```

---

## How Déjà uses Cognee

Déjà is built to exercise Cognee's memory lifecycle as *load-bearing* features, not decoration:

- **Custom `graph_model`.** Nodes are Pydantic subclasses of Cognee's `DataPoint` with `Annotated[..., Dedup(), Embeddable()]`: deterministic ids and explicitly LLM-eligible fields. This is what keeps memory *typed and personal* instead of a bag of text chunks.
- **`recall` through the real API.** `deja ask` calls `cognee.search` over the populated graph (trying `INSIGHTS` → `GRAPH_COMPLETION` → `SUMMARIES`). The call is **best-effort and timeout-guarded**: if the installed Cognee version's search returns nothing, Déjà transparently shows the deterministic graph-derived answer instead, so the demo never stalls. Confirm the exact search shape on your machine with `spike_cognee.py`.
- **`improve` through `SearchType.FEEDBACK`.** A thumbs-up re-weights the exact nodes that produced the answer **and** additively fires Cognee's `FEEDBACK` search so the score attaches to the graph elements that helped, not a global counter.
- **Optional Cognee Cloud.** `deja ask --cloud` routes the same recall to the hosted service (`COGNEE_API_KEY`), falling back to local on any hiccup.

> **Honest scope:** the templated, graph-derived path is the verified default and the recorded-demo path. The `cognee.search` / `FEEDBACK` / `--cloud` calls are real API calls made best-effort with graceful local fallback. They enrich the output when available and never break the core flow when they aren't.

---

## Architecture

**Skill is separated from Concept.** `Concept` is the objective, shared idea ("mutable default arguments"). `Skill` is *this learner's* weighted, mutable relationship to it. That split is what makes the graph *about you*, and gives `memify`/`improve` a node whose weight can visibly change.

**Explicit vs. inferred edges.** Explicit edges are written from real activity. Inferred edges (`SAME_FAMILY_AS`, `RELATED_TO`) are produced *only* by `memify`, never seeded. The seed invariant (0 inferred edges) is enforced by tests, so the "graph re-organized itself" moment is real, not staged.

**Provably graph-driven coaching.** Default coaching prose is derived directly from graph facts, traceable to `used_node_ids`. When Déjà links two bugs across topics, that connection is demonstrably the memory graph reasoning, not an LLM guessing. `--llm` mode rewords those same facts and is validated post-hoc: any concept the LLM names that isn't in the allowed graph-derived set is rejected and the templated answer returned. It **cannot** hallucinate a connection the graph didn't produce (10 dedicated safety tests, including an adversarial fake-LLM that tries to inject an unrelated concept, verified caught).

**Local, single-writer aware.** Cognee's embedded graph store is single-writer, so the UI server can't hold the DB while a mutating command runs. Every mutating command flushes `data/ui_snapshot.json`; the FastAPI + vis.js viewer serves and polls that file, so the UI and CLI run concurrently without contending for the DB. Trade-off: the UI shows the graph as of the last mutation, but its 2-second poll keeps live demo transitions landing.

---

## Configuration

Copy `.env.example` → `.env` and set at minimum `LLM_API_KEY`. All settings resolve from env vars with sensible defaults in [`deja/config.py`](deja/config.py).

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_API_KEY` | *(required)* | LLM provider key: used to boot Cognee's cognify stack |
| `LLM_PROVIDER` | `openai` | LLM provider |
| `LLM_MODEL` | `gpt-4o-mini` | LLM model |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model |
| `DEJA_DATA_DIR` | `./data` | Local data root for SQLite / LanceDB / Kuzu |
| `DEJA_LEARNER_NAME` | `you` | Learner identity (single-user demo) |
| `COGNEE_SERVICE_URL` | *(unset)* | Cognee Cloud tenant URL: enables `deja ask --cloud` |
| `COGNEE_API_KEY` | *(unset)* | Cognee Cloud API key ([free tier](https://platform.cognee.ai), no card) |

---

## Testing

```bash
pip install -e ".[dev]"
pytest tests/            # 42/42 pass
```

**Coverage:** schema split + seed weights + no-inferred-edges-in-seed invariant; cold-open selection logic + cross-restart session recall; cross-topic evidence with no global counter; `memify` cross-topic rule + same-topic rejection + idempotence; `forget` decay/prune paths; `--llm` hallucination-safety (10 tests, incl. adversarial injection); CLI smoke.

---

## Project structure

```
deja-vu/
├── README.md, pyproject.toml, .env.example
├── docs/
│   ├── REPORT.md          ← full completion report
│   └── AI_DISCLOSURE.md   ← AI-assistance disclosure (hackathon Rule 8)
├── deja/
│   ├── cli.py, config.py
│   ├── models/graph.py    ← DataPoint subclasses + relationship constants
│   ├── store/             ← env pinning, graph helpers, cognee.search + cloud
│   ├── commands/          ← seed, start, chat, ask, compare, memify, forget, capture
│   └── ui/                ← FastAPI + vis.js live graph viewer
└── tests/                 ← 42 tests
```

---

## Design notes (honest trade-offs)

- **Templated coaching is a feature, not a shortcut.** It makes the graph's cross-topic reasoning *provable*. `--llm` is there when you want LLM-worded prose; the graph-driven guarantee holds in both modes.
- **Single-user demo scope** (`ENABLE_BACKEND_ACCESS_CONTROL=false`): a scoping choice for the hackathon, not a Cognee limitation. Cognee supports multi-tenant isolation.
- **Screenshot capture is optional** (`[capture]` extra): a fallback for the live UI, not the demo path.

---

## Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `LLM_API_KEY` missing on `deja doctor` | Set `LLM_API_KEY` in `.env`; Cognee needs it to cognify locally. |
| `deja start` shows a generic greeting | Run `deja seed` first: there's no history to recall yet. |
| `deja ask` shows only the graph answer (no `cognee.search` panel) | Expected fallback if the installed Cognee's search returns nothing; run `spike_cognee.py` to confirm the search shape on your machine. |
| `deja ask --cloud` says "Cloud unavailable" | Set `COGNEE_SERVICE_URL` + `COGNEE_API_KEY`; it falls back to local memory otherwise. |
| UI doesn't update after `memify` | The viewer polls `data/ui_snapshot.json` every 2s; give it a beat, or re-run the mutating command. |

---

## AI assistance

Built with AI-assisted coding; disclosed per the hackathon rules in [`docs/AI_DISCLOSURE.md`](docs/AI_DISCLOSURE.md).

## License

MIT: see [`LICENSE`](LICENSE).
