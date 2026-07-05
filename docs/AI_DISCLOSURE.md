# AI Assistance Disclosure

Per the Hangover Part AI Hackathon rules (Rule 8), this project used AI assistance, disclosed here in full.

## Tools used

- **Claude (Anthropic)** — chat interface, used for planning and written deliverables.
- **Claude Code (Anthropic)** — agentic coding tool, used to write and edit the implementation.

## What AI was used for

**Planning and strategy (Claude, chat).**
Concept ideation, choosing the project direction, architecture design, the data-model / schema spec, the demo script and teleprompter, this README, and this disclosure. AI acted as a planning partner; all strategic decisions — track choice, scope cuts, what to build and what to skip — were made by the human author.

**Implementation (Claude Code).**
The Python codebase — CLI, Cognee graph models, command implementations, the FastAPI + vis.js viewer, and the test suite — was written with Claude Code under human direction, working from the human-approved schema spec and demo requirements.

## What the human author did

- Directed all planning: set goals, chose the track, made scoping and design decisions, and approved or rejected AI proposals.
- Reviewed all generated code and documentation.
- Ran and verified the system end to end — the full seed → start → chat → memify → forget flow — and confirmed the test suite (42/42 passing) and the memify seed invariant.
- Authored the open-source-track issue analysis and interactions on the maintainers' repository.
- Recorded the demo video and submitted the project.

All commits are authored by the human participant. AI-generated output was treated as a draft to be reviewed, tested, and accepted — not shipped unverified.

## Note

If any additional AI tools were used during the hackathon, add them to the "Tools used" list above before submitting, so this disclosure remains complete and accurate.
