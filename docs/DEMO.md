# Rehearsal walkthrough

Runtime target: **~4 min core**, compressible to 3 (see bottom).

## Pre-flight (do NOT skip)

```bash
# One-time
python -m venv .venv
source .venv/Scripts/activate           # Windows bash
pip install -e '.[dev]'
cp .env.example .env                    # add LLM_API_KEY (any provider Cognee supports)

# Immediately before the demo — MUST run every time
deja seed
```

`deja seed` wipes the graph and writes the **BEFORE state** the whole demo depends on:

| Skill | weight | status |
|---|---|---|
| recursion | 0.90 | mastered |
| mutable default arguments | 0.30 | in_progress (linked Mistake M1) |
| async error handling | 0.45 | in_progress (linked Mistake M2) |
| python 2 print statement | 0.60 | mastered (deprecated → forget target) |

M1 and M2 share `failure_class = shared-mutable-state`. **They are not linked in the seed.** `memify` will link them live in Scene 3.

Open a second terminal and start the graph view before you go on stage:

```bash
deja ui                                 # http://127.0.0.1:8765/
```

Have a browser window pinned to that URL, positioned so you can flip to it in Scene 3.

## Scene 0 — hook (0:00–0:15)

Spoken, no keyboard:

> "Their landing page has a joke — your AI has a hangover, it wakes up every morning with no memory of last night. That's every coding assistant today. You explain your level, your gaps, your stack — and tomorrow it's forgotten all of it. We fixed that."

## Scene 1 — cold open (0:15–1:00)

```bash
deja start
```

Expected output:

```
Welcome back, Gajanand.
Last time you nailed recursion but stumbled on mutable default arguments.
You'd also just started on async error handling.
Want to revisit the mutable default arguments gotcha, or push forward on async error handling?
```

Say:

> "I gave it nothing. No context, no history in the prompt. It pulled all of that from its memory graph — what I've mastered, what I struggled with, what I was mid-way through. This is the money shot: no re-explaining who I am."

Pause for a beat after the greeting lands.

## Scene 2 — live coaching + feedback (1:00–2:00)

```bash
deja chat --topic "async error handling" \
          --question "My asyncio.gather tasks keep mutating the same list" \
          --feedback up
```

Expected: the mentor reaches into a *different* Concept (mutable-defaults) as evidence because M1 and M2 share `failure_class = shared-mutable-state`, and applies improve to the async Skill (0.45 → 0.55).

Say:

> "Notice it didn't just answer generically — it reached across my history and linked this to a mistake from a different topic. That's the graph reasoning over relationships, not just matching keywords."

Say (after the thumbs-up recorded):

> "That thumbs-up isn't a rating for a leaderboard. It feeds Cognee's improve API — it re-weights the exact graph nodes that produced this answer. Good explanations get stronger."

## Scene 3 — memify (2:00–3:00) · the headline

Flip to the browser window. Point at the graph:

> "This is my skill graph inside Cognee right now. Nodes are concepts, edges are how they relate, thickness is my mastery. Recursion's a strong hub. Async is thin and just got a little thicker from that thumbs-up."

Back to the terminal:

```bash
deja memify
```

Expected effects visible in the browser within ~2 seconds:

- A new **bold magenta edge** appears between the two Mistake nodes (M1 ↔ M2). The UI flashes it yellow for ~1.5s.
- The async and mutable-defaults Skill nodes get slightly thicker.

CLI shows the table:

```
SAME_FAMILY_AS — new cross-topic links
mistake A            concept A                  mistake B            concept B
M1-default-list…     mutable default arguments  M2-async-shared…     async error handling
```

Say:

> "That's memify. It didn't just store my session — it re-organized the whole graph. It inferred that these two bugs I hit are the same class of mistake and linked them. My memory didn't just get bigger, it got smarter. No other memory approach does this — this is why we built on Cognee's graph instead of plain vector storage."

**Fallback if live render is flaky:** show the two pre-captured PNGs. Generate them with:

```bash
pip install -e '.[capture]'
playwright install chromium             # one-time
deja seed && deja capture               # produces captures/graph_before.png and graph_after.png
```

## Scene 4 — forget (3:00–3:30)

```bash
deja forget --topic recursion
```

Expected:

- recursion Skill: 0.90 → 0.54 (decayed, status becomes `decaying`, dimmed grey in UI)
- python 2 print statement Concept: pruned outright + its orphan Skill vanishes

Say:

> "Memory that only grows becomes noise. Mastered topics decay out so it stops nagging me about things I know, and deprecated tech gets pruned so my mentor stays current. That's forget — the verb everybody skips, and the reason this stays useful past week one."

## Scene 5 — close (3:30–4:00)

> "So — start to finish, one product using all four of Cognee's memory verbs doing real work: it remembered me, recalled across sessions, improved from my feedback, re-organized itself with memify, and forgot what I'd outgrown. No hangover. It actually knows who I am as a developer — and it's a better teacher today than it was this morning. That's Déjà."

## 3-minute compression

If the slot is tight, keep Scene 1 (cold open), Scene 3 (memify), Scene 5 (close). Fold thumbs-up into Scene 1 with a quick `deja chat` call. Cut Scene 4 to a single spoken line — no live action. **Never cut memify.**

## Reset between rehearsals

```bash
deja seed          # wipe + reseed. UI auto-refreshes to the BEFORE state within 2s.
```

## Contingency

| failure | mitigation |
|---|---|
| API/LLM dies mid-demo | Pre-recorded 90s screen capture of the full flow, narrate over it |
| Memify graph render fails | Pre-captured `graph_before.png` / `graph_after.png` side by side |
| Cold open recalls the wrong thing | Re-run `deja seed` immediately before going on |
