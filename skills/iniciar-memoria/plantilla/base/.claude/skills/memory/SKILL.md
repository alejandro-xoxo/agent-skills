---
name: memory
description: Reads and writes the project's memory (the Obsidian vault and the docs/ folder). Use it when you need earlier context, past decisions, lessons or project conventions, or when there is something new worth remembering for future sessions.
---

# Project memory

> **Requirement:** the project must have the `## Memory` block in `AGENTS.md`. If it does not, the memory is not set up: use the `iniciar-memoria` skill first (or tell the user) and do not go on.

**Paths:** read the `## Memory` block of `AGENTS.md`. It holds the vault path and the folders (index, inbox, lessons, decisions, sources). Below they are called `<vault>`, `<index>`, `<inbox>`, `<lessons>`, `<decisions>` and `<sources>`. If the vault is outside the working directory and you cannot read it, ask the user for access before going on.

The memory is layered. Enter through the cheapest layer and go deeper only if needed.

## To look something up (in this order)
1. `docs/STATE.md`: where the work stands.
2. `<index>`: follow only the `[[links]]` the task needs.
3. To find something specific: `grep -ril "word" "<vault>" --include=*.md` and open only the notes that come up.
4. `<sources>` is raw material. Never read it whole; search with grep and read the fragment.
5. Before using a stored fact (path, function, figure, status), check it against the source. If it is no longer true, fix the note.

## To write
First look for an existing note on the subject (`grep`). If there is one, update it; do not duplicate.

| What it is | Where | Format |
|---|---|---|
| Loose idea or question | `<inbox>` | One line or a paragraph with a date |
| How the domain or process works | the vault, in its domain folder | One idea per note |
| Lesson learned | `<lessons>` | The vault's `Lesson.md` template, if it exists |
| Decision with reasons | `<decisions>` | The vault's `ADR.md` template, numbered `ADR-NNNN Title.md` |
| Raw material | `<sources>` | Unedited copy + a line in its index |

Writing rules:
- Front matter with `tags` and `created`. For decisions, also `status` (proposed, accepted, superseded).
- One idea per note. Clear title. File names without `: ? " < > | / \`.
- Store the **why** and the **source** with its date, not just the fact.
- Link with `[[wikilinks]]` and add the new note to the index it belongs to.
- Write in the language of the project and without people's names or personal data unless essential.
- Never delete or overwrite existing notes without asking.

## What NOT to store
- What is already in the code or in git.
- Secrets, keys or passwords.
- Personal data.
- Ephemeral state of a single session (that goes to `docs/STATE.md`).

## Decisions
If the decision changes how something is built, create an ADR note and add 5 lines to `docs/DECISIONS.md` with the link.