# {{NAME}}

{{DESCRIPTION}}

> This file is loaded in every session: keep it at 100 lines or fewer. Long material lives in the vault.

## Memory
- Obsidian vault: `{{VAULT}}`
- Inside the vault (relative paths): index `00 Home.md` · inbox `00 Inbox/` · lessons `03 Lessons/` · decisions `04 Decisions/` · sources `05 Sources/`
- Outside the vault: live state `docs/STATE.md` · short log `docs/DECISIONS.md`
- If you connect another vault with a different structure, change the paths here (the global skill `iniciar-memoria` does it). All the skills read this block.

## Start here
1. Read `docs/STATE.md`: where the work stands and what the next step is.
2. If you need context, open the vault index and follow only the `[[links]]` the task requires. Do not read whole folders.
3. The sources folder is raw material: do not read it whole; search with grep.
4. Before acting on a stored fact (path, function, figure, status), check it against the source. The memory may be stale.

## Stack and commands
- Stack: {{STACK}}
- Install: (fill in)
- Run: (fill in)
- Test: (fill in)

## Golden rules
- (Fill in with 3 to 7 rules specific to the project.)
- Do not invent data: every figure carries its source and its date.
- No credentials or personal data in the repository or in the notes.
- If two sources contradict each other, say so; do not pick one silently.

## How to save memory
| What | Where | How |
|---|---|---|
| Where the work stands | `docs/STATE.md` | Rewritten, not accumulated |
| Decision (summary) | `docs/DECISIONS.md` | Appended: 5 lines at most |
| Decision with reasons | the vault's decisions | Numbered ADR note |
| Reusable lesson | the vault's lessons | One idea per note |
| Loose idea | the vault's inbox | Review and move every week |

When writing: one idea per note, with date, source and the why; link with `[[wikilinks]]`; check whether it already exists and update before duplicating; delete what stopped being true.

When closing an important task use the `close-task` skill.

## Skills
Procedures in `.claude/skills/<name>/SKILL.md`. If your agent has no skills, read the file directly.
- `memory`: read and write in the vault.
- `close-task`: closing routine for a task.
- `audit-memory`: periodic memory cleanup.

## Repository map
- `docs/`: state and decisions.
- `knowledge/`: default local vault; it does not exist if the vault is external.
- (Add the code folders here once they exist.)