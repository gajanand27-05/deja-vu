# Déjà — the coding mentor that remembers you

> Your AI has a hangover. It wakes up every session with no memory of last night.
>
> Déjà doesn't. It remembers you as a developer — and gets better at teaching you the longer you use it.

Déjà is a CLI coding mentor built on **Cognee 1.2.2**. It keeps a persistent, typed knowledge graph of your learning — the concepts you've mastered, the mistakes you've made, and how they connect — so every session opens where you left off, coaching is grounded in your history, and the memory re-organizes itself to get smarter over time.

Fully local — SQLite + LanceDB + Kuzu, no servers. Python. **42/42 tests passing.**

---

## Why this is a real memory system, not "RAG with extra steps"

Most agent-memory demos use two verbs: *store* and *retrieve*. Déjà uses **all four** of Cognee's memory verbs as load-bearing features — and the one that matters most is the one almost nobody demos:

> **`memify` — the verb every other memory system doesn't have.**
>
> After a session, Déjà's graph *infers a new connection nobody wrote*: it links a mutable-defaults bug and an async shared-state bug as the same failure family, because they share an underlying failure class. The memory didn't just get bigger — it got smarter.

| Verb       | Command                       | What it does here |
|------------|-------------------------------|-------------------|
| `remember` | `deja seed`, `deja chat`      | Writes typed DataPoint nodes (`Learner`, `Concept`, `Skill`, `Session`, `Mistake`) + explicit edges into the graph |
| `recall`   | `deja start`, `deja chat`     | Cold open derives three lines from graph state (not hardcoded); coaching pulls cross-topic mistake evidence via graph traversal |
| `improve`  | `deja chat --feedback up`     | Re-weights `mastery_weight` + `confidence` on the *exact* nodes that produced the answer — not a global counter |
| `memify`   | `deja memify`                 | Infers and adds `Mistake —SAME_FAMILY_AS→ Mistake` across topics with a shared failure class; re-weights skills; idempotent |
| `forget`   | `deja forget`                 | Soft-decays stale mastered skills out of active coaching; hard-prunes deprecated concepts and orphaned nodes |

---

## Quickstart

```bash
# 1. Install
git clone https://github.com/gajanand27-05/deja-vu
cd deja-vu
pip install -e .

# 2. Configure (an LLM key is needed to boot Cognee's stack)
cp .env.example .env
# edit .env → set LLM_API_KEY

# 3. Seed the learner's history (locks the BEFORE state)
deja seed
```

Then run the flow:

```bash
deja start                 # cold open — the mentor already knows you (now also recalls your last session across restarts)
deja chat                  # ask a coding question; pulls cross-topic evidence
deja chat --feedback up    # reinforce a good explanation (improve)
deja ask "why do I keep hitting this?"   # recall via Cognee's own cognee.search over the graph
deja compare               # same question, answered WITHOUT memory vs. WITH the graph — the hangover, dramatized
deja memify                # the graph re-organizes itself — the SAME_FAMILY_AS edge appears
deja forget                # mastered topics decay; deprecated tech is pruned
```

---

## See the graph re-organize (the money shot)

In a spare terminal:

```bash
deja ui        # serves the live graph at http://127.0.0.1:8765/
```

Open the browser, then run `deja memify` in your main terminal. On the 2-second poll the graph re-renders: the new `SAME_FAMILY_AS` edge flashes in (bold magenta), the camera pans to it, a **"cross-topic family inferred"** caption fades in, and re-weighted skill nodes visibly thicken.

Optional `--llm` on `deja chat` rewords the same graph-derived facts through an LLM for nicer prose. Templated output is the default and is provably graph-driven (see below).

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

## Architecture

**Custom Cognee `graph_model`.** Nodes are Pydantic subclasses of Cognee's `DataPoint`, with `Annotated[..., Dedup(), Embeddable()]` — deterministic ids and explicitly LLM-eligible fields. This is what keeps memory typed and personal instead of a bag of text chunks.

**Skill is separated from Concept.** `Concept` is the objective, shared idea ("mutable default arguments"). `Skill` is this learner's weighted, mutable relationship to it. That split is what makes the graph *about you* — and gives memify/improve a node whose weight can visibly change.

**Explicit vs. inferred edges.** Explicit edges are written from real activity. Inferred edges (`SAME_FAMILY_AS`, `RELATED_TO`) are produced *only* by `memify` — never seeded. The seed invariant (0 inferred edges) is enforced by tests, so the "graph re-organized itself" moment is real, not staged.

**Provably graph-driven coaching.** Default coaching prose is derived directly from graph facts. So when Déjà links two bugs across different topics, that connection is demonstrably the memory graph reasoning — traceable to `used_node_ids` — not an LLM guessing. The `--llm` mode rewords those same facts and is validated post-hoc: any concept the LLM names that isn't in the allowed graph-derived set gets rejected and the templated answer returned. It *cannot* hallucinate a connection the graph didn't produce (10 dedicated safety tests, including an adversarial fake-LLM that tries to inject an unrelated concept — verified caught).

**Local, single-writer aware.** Runs on Cognee's embedded stack (SQLite + LanceDB + Kuzu). Because the graph store is single-writer, every mutating command flushes `data/ui_snapshot.json`; the FastAPI + vis.js viewer serves and polls that file, so UI and CLI run concurrently without contending for the DB.

---

## Tests

```bash
pytest tests/    # 42/42 pass
```

Coverage: schema split + seed weights + no-inferred-edges-in-seed; cold-open selection logic + cross-restart session recall; cross-topic evidence with no global counter; memify cross-topic rule + same-topic rejection + idempotence; forget decay/prune paths; `--llm` hallucination-safety (10); CLI smoke.

---

## Repo layout

```
deja-vu/
├── README.md, pyproject.toml, .env.example
├── docs/
│   ├── DEMO.md            ← rehearsal walkthrough (Scenes 0–4)
│   ├── REPORT.md          ← full completion report
│   └── AI_DISCLOSURE.md   ← AI-assistance disclosure (hackathon Rule 8)
├── deja/
│   ├── cli.py, config.py
│   ├── models/graph.py    ← DataPoint subclasses + relationship constants
│   ├── store/             ← env pinning + graph helpers
│   ├── commands/          ← seed, start, chat, memify, forget, capture
│   └── ui/                ← FastAPI + vis.js live graph viewer
└── tests/                 ← 42 tests
```

---

## Design notes (honest trade-offs)

- **Templated coaching is a feature, not a shortcut.** It makes the graph's cross-topic reasoning *provable*. `--llm` is available when you want LLM-worded prose; the graph-driven guarantee holds in both modes.
- **Single-user demo scope** (`ENABLE_BACKEND_ACCESS_CONTROL=false`) — a scoping choice for the hackathon, not a Cognee limitation. Cognee supports multi-tenant isolation.
- **Screenshot capture is optional** (`[capture]` extra) — a fallback for the live UI, not the demo path.

---

## AI assistance

Built with AI-assisted coding; disclosed per the hackathon rules in [`docs/AI_DISCLOSURE.md`](docs/AI_DISCLOSURE.md).

## License

See [`LICENSE`](LICENSE).
