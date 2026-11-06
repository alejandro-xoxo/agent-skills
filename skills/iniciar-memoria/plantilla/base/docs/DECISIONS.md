# Decision log — {{NAME}}

> It is **appended** to at the end; it is not rewritten. Each entry has at most 5 lines: what was decided, why, what changes and, if there is one, the link to the ADR note in `knowledge/04 Decisions/`.

## {{DATE}} — The memory template is adopted
- Decision: the project's memory lives in `AGENTS.md` (always loaded), `docs/STATE.md` (live state) and `knowledge/` (long term).
- Why: every session starts with no memories; this way little is loaded and the rest is consulted on demand.
- What changes: when an important task is closed, `STATE.md` and `DECISIONS.md` are updated.