---
name: close-task
description: Closing routine for when an important task ends or before the session finishes. Rewrites docs/STATE.md, appends 5 lines to docs/DECISIONS.md and saves decisions and lessons in the vault. Use it when a block of work is completed, a technical decision is made or the user says they are closing the session.
---

# Close a task

> **Requirement:** the project must have the `## Memory` block in `AGENTS.md` and the file `docs/STATE.md`. If either is missing, the memory is not set up: use the `iniciar-memoria` skill first (or tell the user) and do not go on.

The vault paths (`<vault>`, `<decisions>`, `<lessons>`, `<index>`) are in the `## Memory` block of `AGENTS.md`. Do these steps in order. If something does not apply, skip it and say so.

1. **Review what changed.** If there is git, look at `git status` and `git diff --stat`. If not, go over the files you touched.
2. **Rewrite `docs/STATE.md`.** Replace its content; do not pile onto it. Include:
   - Where the work stands.
   - The concrete next step.
   - Blockers and open questions.
   - What is **verified** and what is **unverified**. Be honest: if you did not test something, write it down.
   Keep the file at 40 lines or fewer and update `updated:` with today's date.
3. **Append to `docs/DECISIONS.md`** an entry of at most 5 lines if there was a decision: what, why, what changes and a link. If there was no decision, add nothing.
4. **Big decision** (it changes how something is built): create an ADR note in `<decisions>` with the vault's `ADR.md` template and add it to its index.
5. **Reusable lesson** (a mistake that cost time, something that worked): a note in `<lessons>` with the `Lesson.md` template and a line in its index.
6. **Indexes.** If you created notes, link them from `<index>` or from the index of their folder.
7. **Links.** Check that you left no broken links (see the `audit-memory` skill).
8. **Summarize for the user** in three lines what was saved and where.

Do not save secrets or personal data. Do not delete notes without asking.