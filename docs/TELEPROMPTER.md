# Déjà — demo teleprompter (target 2:45)

> Read straight through in one continuous take. 2:45 target leaves ~15s buffer under a 3:00 hard cap. Two columns: `[SCREEN]` is what you're doing on camera, plain text is spoken verbatim.

## Before you hit record

- Seed off-camera: `deja seed`
- `deja ui` running, browser open on the BEFORE graph
- CLI in a second window
- Both windows framed so the browser is visible when you run `deja memify`
- One silent practice pass of the clicks so your hands know the sequence — then record reading this straight through

---

[SCREEN: your face, or a title card. No terminal yet.]

Every AI coding assistant has a hangover. It wakes up each session with no memory of last night — you re-explain your level, your gaps, your stack, every single time. This is Déjà. It remembers you as a developer, and it gets better at teaching you the longer you use it.

[SCREEN: cut to the browser showing the BEFORE graph. Let it sit.]

Under the hood it's a Python CLI on Cognee's memory graph — running fully local, no servers: SQLite, LanceDB, Kuzu. This graph is the memory. Every node is typed — and critically, a learner's skill is separate from a concept, so the graph isn't generic knowledge, it's a model of you. All four of Cognee's memory verbs do real work here. Let me show you.

[SCREEN: switch to terminal. Type `deja start`.]

I've typed nothing but "start." No history, no context in the prompt.

[SCREEN: the three cold-open lines appear.]

And it already knows me — I nailed recursion, I stumbled on mutable default arguments, and I'd just started on async error handling. That's recall, reading straight from the graph.

[SCREEN: type `deja chat` — ask the async question.]

I ask an async question. Watch what it reaches for.

[SCREEN: the cross-topic evidence line appears. Point at it.]

It pulls a bug from a different lesson — my mutable-defaults mistake — because it's the same shape. And because this coaching text is derived directly from graph facts, that cross-topic link is provably the memory reasoning, not the model guessing.

[SCREEN: type `deja chat --feedback up`.]

I thumbs-up the explanation. That's improve — it re-weights the exact nodes that produced the answer.

[SCREEN: switch to the browser. Then run `deja memify` in the terminal. Cut back to the browser.]

Now the part no other memory system does. This is **memify — the verb every other memory system doesn't have.**

[SCREEN: the magenta SAME_FAMILY_AS edge flashes in, camera pans, caption fades. PAUSE — 3 full seconds of silence. Let it land.]

It just inferred a connection nobody wrote — that my mutable-defaults bug and my async bug are the same failure family. The memory didn't get bigger. It got smarter.

[SCREEN: terminal. Type `deja forget`.]

And memory that only grows becomes noise. `forget` decays what I've mastered so it stops nagging me, and prunes deprecated tech so my mentor stays current.

[SCREEN: face, or the graph.]

All four memory verbs — remember, recall, improve, memify, forget — one product, no hangover. It doesn't just store what I said. It understands who I am as a developer, and it's a better teacher now than it was five minutes ago. That's Déjà, built on Cognee.

---

## Reading notes

- The one non-negotiable pause is after the magenta edge appears. Silence sells it. Count three in your head before you speak — it'll feel too long and it won't be.
- Don't rush the cold open. "I've typed nothing but start" needs a half-beat before the lines appear, so the contrast registers.
- The pinned line — **"the verb every other memory system doesn't have"** — read it exactly, don't paraphrase. It's your Cognee-depth scoring line.
- If a take runs long, the cuttable sentence is the second half of the architecture block (the "generic knowledge, it's a model of you" clause) — trim there, never the memify beat.
- If the live UI stutters mid-take, stop and restart the take rather than pushing through a broken render — the memify visual is the whole point. Your Playwright capture fallback is insurance for that, but a clean live take beats it every time.
