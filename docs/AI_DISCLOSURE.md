# AI assistant disclosure

Per WeMakeDevs hackathon rules, disclosing use of AI assistants in this submission:

## Assistants used

- **Claude Code (Anthropic — Opus 4.7, 1M context)** — used substantially for scaffolding, schema modeling, Cognee integration, CLI implementation, tests, graph visualization, and documentation.

## Division of labor

**Human author (Gajanand):**
- Product concept, positioning, and value proposition ("the mentor that remembers you").
- Full demo script (4-min rehearsal, scene-by-scene beats, contingency plans).
- Cognee schema specification (node types, edge classes, memify moment design, seed contract).
- Direction of the phase plan and workflow (commit + push per phase; CLAUDE.md kept local).
- Review of every phase before it landed on main.

**Claude Code:**
- Wrote all of `deja/`, `tests/`, `docs/DEMO.md`, and the surrounding scaffolding.
- Turned the human-authored Cognee schema spec into working Pydantic DataPoint subclasses.
- Implemented the six commands (seed, start, chat, memify, forget, ui, capture) against Cognee 1.2.2's graph engine.
- Wrote tests to lock the spec invariants (SAME_FAMILY_AS never in seed, memify is idempotent, cold-open lines derived from graph state, etc.).
- Debugged the Ladybug single-writer lock issue and pivoted to the snapshot-file architecture for the UI.

## Cognee open source track

No AI-generated PRs were submitted to the Cognee upstream open source track. This repo is the standalone hackathon submission, not an upstream contribution.

## Reproducibility

- The design docs (schema spec + demo script) are the source of truth. If you re-run the project generation with the same spec, the shipped shape (schema, phase plan, verb wiring) should match; the demo script also functions as an acceptance test.
- All commits on `main` are attributed to the human author (`gajanand27-05 <gajanandvd2005@gmail.com>`).
