# Memory template for projects worked on with agents

(`plantilla` is Spanish for "template".) The same structure for all your projects, so the agent picks the context back up without rereading everything. It applies common practices (a short `AGENTS.md` that is always loaded, an Obsidian vault with links, skills with progressive loading) and relies on Claude Code's documentation about memory (<https://code.claude.com/docs/en/memory>).

**Core idea:** every session starts with no memories. Memory is about deciding what is always loaded (little), what is loaded if needed and what is only consulted.

## What it includes

This folder (`plantilla/`) goes inside the `iniciar-memoria` skill, next to its `SKILL.md`.

```
plantilla/
├─ README.md
├─ new-project.ps1               creates or completes the structure in a project
├─ extras/mcp.memory.example.json  level 2, optional (memory graph through MCP)
├─ extras/graphify/              level 3, optional: guide and .graphifyignore for the code graph (installs nothing)
├─ extras/rag/                   level 4, optional: automatic vault retrieval (local RAG); creating the project installs nothing
└─ base/                         what gets copied into the project
   ├─ AGENTS.md                  rules and map; always loaded (≤100 lines)
   ├─ docs/STATE.md              where the work stands (rewritten)
   ├─ docs/DECISIONS.md          short decision log (appended)
   ├─ .claude/skills/
   │   ├─ memory/                how to read and write the memory
   │   ├─ close-task/            closing routine
   │   └─ audit-memory/          periodic cleanup
   ├─ .gitignore
   └─ knowledge/                 Obsidian vault (long-term memory)
      ├─ 00 Home · 00 Inbox · 01 Context · 02 Domain and process
      ├─ 03 Lessons · 04 Decisions · 05 Sources
      └─ Templates (ADR, Lesson)
```

## The layers

| Layer | Where | Loaded |
|---|---|---|
| Rules and map | `AGENTS.md` | Always |
| Live state | `docs/STATE.md` | At the start (`AGENTS.md` asks for it) |
| Procedures | `.claude/skills/*` | Name and description always; the body, on demand |
| Long term | `knowledge/` | Only what the task needs, entering through `00 Home` |
| Raw material | `knowledge/05 Sources/` | Never whole; with grep |
| Graph lookup (optional) | MCP `memory` | When asked |
| Code graph (optional) | Graphify, prepared in `docs/GRAPH.md` | When the project has a fair amount of code |
| Automatic retrieval (optional) | Local RAG in `.rag/` | On every message, if it is about the vault |

Equivalence with a common four-folder second-brain layout: `00-inbox` → `00 Inbox`; `01-projects` → the vault already belongs to one project; `02-best-practices` → `03 Lessons` (and a global vault of your own, see below); `03-decisions` → `04 Decisions`.

## How to use it

New or existing project (it does not overwrite what already exists):

```powershell
powershell -ExecutionPolicy Bypass -File "<template folder>\new-project.ps1" `
  -Destination "<project folder>" `
  -Name "My Project" -Description "What it is, in one line" -Stack "Python and FastAPI" -WithGit
```

Options: `-WithGit` runs `git init` without a commit; `-WithMemoryMcp` creates a `.mcp.json` with the memory server; `-WithGraphify` leaves the code graph prepared (see "Optional level 3"); `-GraphifyOnly` does only that on a project that already exists, touching nothing else; `-WithRag` and `-RagOnly` leave automatic retrieval prepared (see "Optional level 4"); `-Force` overwrites. To use an Obsidian vault you already have, see the next section.

The parameters were Spanish in earlier versions (`-Destino`, `-Nombre`, `-Descripcion`, `-ConGit`, `-ConMcpMemoria`, `-ConGraphify`, `-SoloGraphify`, `-ConRag`, `-SoloRag`, `-Forzar`, `-Carpeta`, `-CrearVault`, `-SoloVault`); the old names still work as aliases.

## Connect an Obsidian vault of your own
By default the vault is `knowledge/` inside the project. To use another one, the **single source of truth** is the `## Memory` block of `AGENTS.md`: it holds the vault path and the folders (index, inbox, lessons, decisions, sources). The three skills read that block, so changing it is enough.

| Situation | How |
|---|---|
| New or empty vault | `-Vault "D:\Obsidian\MyVault"` (add `-CreateVault` if the folder does not exist yet) |
| Vault shared among projects | `-Vault "D:\Obsidian\Brain" -Folder "My Project"`: the structure goes in a subfolder and no other `.obsidian` is nested |
| Only create the structure in the vault, without touching the project | add `-VaultOnly` |
| Vault that already has notes with another structure | No folders are created: edit the `## Memory` block by hand with the real folders |

The script never overwrites existing notes. In a shared vault, the template notes (Inbox, Glossary, Decisions...) are named the same in every project and Obsidian may resolve a link to another project's note; use names of your own.

### The `iniciar-memoria` skill
It does all of the above in conversation. It is the `SKILL.md` of the parent folder (`iniciar-memoria/`). To install it, copy that whole folder, with `plantilla/` inside, to your agent's skills folder (for example `~/.claude/skills/`) and restart the session. When a project starts it detects whether the memory is missing and applies the template; if it already exists, it loads the state and the index; and if you say "connect it to my vault" and give the path, it validates the vault, gets access to that folder, picks the mode and updates the `## Memory` block. It finds the template by its relative path (`plantilla/` next to the `SKILL.md`): if you separate the two folders, the skill will ask you where it is.

**Automatic loading in every session** does not depend on the skill but on `AGENTS.md` ("Start here"). A skill is activated when the agent thinks it fits its description, not on every startup.

## Why it does not use RAG or a graph by default
It is a decision about size and trust, not a shortcoming.

- **RAG (vector search).** It splits the notes into chunks and brings back the ones similar to the question. With dozens of notes it is worse than what is already there: chunks lose their context (the why of a decision gets separated from its date and its source), it needs an index that goes stale every time a note changes, and you cannot audit why it brought one chunk and not another. Here the agent enters through an index, follows `[[links]]` and searches with grep: it is predictable and verifiable.
- **Graph.** The vault is already a graph: every `[[wikilink]]` is a relationship and Obsidian draws it. A separate graph (entities, relationships, observations) duplicates what the notes say and gets messy without a strict schema; two sources of truth end up contradicting each other.
- **Starting criterion:** begin with the simplest thing and do not set up heavy infrastructure on day one; classic RAG is rarely the simplest or most efficient option for a small project.

**There is a graph, but optional:** `-WithMemoryMcp` adds the memory server as a lookup accelerator. The notes rule.

**When it would be worth adding them:**
- A code graph (for example `codebase-memory-mcp`, which I have not verified) when the repository is large and the agent spends a lot reading files to find out who calls what.
- RAG or semantic search over the **raw sources** when they are many or huge (hundreds of documents, conversations of thousands of lines), keeping the curated notes as the main layer. It is available as an option (`-WithRag`, see "Optional level 4").
- A temporal graph (Zep or Graphiti) in autonomous production agents, for example in n8n, where the data changes by itself and old facts have to be invalidated.
- Practical signal to take the step: when grep returns too many irrelevant results or the index no longer fits on one screen.

## First 10 minutes in a project
1. Fill in the commands and 3 to 7 golden rules of your own in `AGENTS.md`.
2. Fill in `knowledge/01 Context/Project and goal.md`.
3. Open the `knowledge` folder as a vault in Obsidian.
4. Record in `05 Sources/Sources.md` the raw material that already exists.
5. Work; when you finish an important task, ask for the `close-task` skill.

## AGENTS.md and Claude Code
According to Claude Code's documentation, it reads `AGENTS.md` directly (version 2.1.277 or later) **only if there is no `CLAUDE.md` or `CLAUDE.local.md` in the project folder or in the ones above it**. If either exists, it reads those and leaves `AGENTS.md` aside. That is why the template **does not include `CLAUDE.md`**.

- Your personal `~/.claude/CLAUDE.md` and the rules in `.claude/rules/` do not count: they keep loading alongside `AGENTS.md`.
- If in some environment it does not read it (old version, or `/plugin` turned the support off), create a `CLAUDE.md` with a single line: `@AGENTS.md`.
- The documentation recommends fewer than 200 lines; the template stays at 100 to leave margin.

## Skills
`.claude/skills/<name>/SKILL.md` is Claude Code's format: the `name` and `description` of the header are always visible, and the body is loaded when the task matches. Other agents do not necessarily load them on their own; that is why `AGENTS.md` names them and they are plain Markdown that any agent can read.

## Optional level 2: memory graph
`-WithMemoryMcp` generates a `.mcp.json` with `@modelcontextprotocol/server-memory` (entities, relationships and observations in a local `.jsonl` in `.memory/`). Claude Code will ask for approval the first time. Use it as a lookup accelerator, not as a source of truth: the notes in `knowledge/` rule.

Another option mentioned in the community is `codebase-memory-mcp`, for mapping code. I did not include it: I have not verified it and it only adds value in projects with a lot of code.

## Optional level 3: code graph (Graphify)
The idea is to **leave the ground ready** for when the project grows, without paying its cost ahead of time. `-WithGraphify` (or `-GraphifyOnly` on a project that already exists) leaves:

- `.graphifyignore`: what Graphify must not read. By default it excludes sources with personal data, the vault, the agent's memory, dependencies and credentials.
- `docs/GRAPH.md`: what it is, when to turn it on, how to do it step by step, what not to do and how to remove it.
- A line in the `AGENTS.md` map that points to that guide, and `graphify-out/` in `.gitignore`.

**It installs and runs nothing.** Turning it on is a later decision, when the repository has a fair amount of code and the agent spends a lot reading files.

Cautions that `docs/GRAPH.md` records, because they clash with this template:
- `graphify claude install` writes to `CLAUDE.md`, and with that file present Claude Code stops reading `AGENTS.md` (see the section above). Do not use it.
- Its strict-mode hooks can deny file reads, including those of the vault.
- The documents, PDFs and images it indexes are sent to the assistant's model; code is processed locally. That is why `.graphifyignore` excludes the raw sources.
- The token-savings figures come from the tool's author and are worth measuring in your project.

The tool belongs to a third party ([Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify), Apache-2.0): its code is not included here.

## Optional level 4: automatic vault retrieval (local RAG)
For when the raw sources are large (for example, a conversation of thousands of lines) and `grep` is not enough: a Claude Code hook adds to every message the most relevant chunks of the vault and of `docs/`, with file and lines, using a search by meaning mixed with exact words. Everything runs on the machine, and curated notes weigh more than raw material.

It is turned on in two steps, so that creating a project never installs or downloads anything without you deciding:
1. `-WithRag` (or `-RagOnly` on a project that already exists) copies `.rag/` (the `rag.py` engine, the `prepare.ps1` script, a guide and an evaluation example), adds a line to `AGENTS.md` and ignores `.rag/` in git.
2. `.rag\prepare.ps1` does the heavy part: Python environment (3.10 to 3.13), `fastembed`, index, hooks in `.claude/settings.local.json` (merging with what is there, with a backup) and a local server. The first time it downloads about 0.6 GB of model, which is shared among projects.

What you need to know:
- It is optional and has costs: about 700 MB of memory while the server is active, between 500 and 900 more tokens for each related message, and `.rag/index/` stores the full text of the sources (it must not be shared).
- It only injects if the message is about the vault (similarity threshold 0.50). Giving no context is better than giving the wrong one.
- It improves which chunks reach the agent, it does not guarantee that it gets things right: each chunk carries file and lines so it can be verified.
- It is measured with `rag.py evaluate` and questions of your own (`evaluation.example.json`). In the project where it was tried, with 20 questions written by someone who knew the notes, the mix hit in the top 3 95% of the time and the keywords alone 70%.
- Windows and Python 3.10 to 3.13 (tested with 3.12). The detail is in `.rag/README.md`.
- `rag.py` also accepts the older Spanish command names (`indexar`, `buscar`, `servidor`, `arrancar`, `parar`, `ganchos`, `evaluar`) and environment variables (`RAG_DESACTIVAR`, `RAG_UMBRAL`, `RAG_MODELO`, `RAG_MODELOS`, `RAG_PESO_CURADO`).

## Your global layer (the script does not touch it)
- `~/.claude/CLAUDE.md` and `~/.claude/rules/` for preferences that apply to all projects.
- A vault of your own with best practices across projects (a "second brain"). Each `AGENTS.md` can point to it with one line.

## Maintenance
- Old or contradictory memory is worse than none: use the `audit-memory` skill from time to time or when `AGENTS.md` goes past 100 lines.
- Before acting on a stored fact, check it against the source.
- Claude Code's auto-memory (notes it writes by itself) coexists with this: what is personal and per-repository goes there; what is shared and versioned, here.

## What was tested and what was not
**Tested** (the template was first written with Spanish names and later translated to English; the first four items were run on the Spanish version, and the installer and engine were then re-run after the translation, see the last item):
- The script in temporary folders: a normal project (19 files, markers filled in, Obsidian's `{{date}}` intact, no broken links, no `CLAUDE.md`), a second run without overwriting, an empty external vault, a shared vault with `-Folder` (the other note and the existing `.obsidian` stay intact, no nested `.obsidian`), `-VaultOnly` (does not create the project) and the expected errors (nonexistent vault without `-CreateVault`, `-VaultOnly` without `-Vault`).
- The memory server starting with the generated configuration, with its 9 tools and writing its file.
- `-WithGraphify` and `-GraphifyOnly` (in temporary folders): a new project with the option, a repeat without duplicating anything, without the option (nothing about Graphify appears), an existing project with an `AGENTS.md` of its own with CRLF line endings (the line endings are kept and a section is added), a folder with no `AGENTS.md`, `.gitignore` or git (it only creates the two guide files), and the expected errors (nonexistent destination and disallowed combinations), without creating `knowledge/`, `.claude/` or `CLAUDE.md`.
- `-WithRag` and `-RagOnly` (in temporary folders): a new project with the option (it only creates files: no environment, no model and no `CLAUDE.md`), a repeat without duplicating, without the option, an existing project with an `AGENTS.md` of its own with CRLF, combined with `-GraphifyOnly`, expected errors, and the registration of hooks over an existing configuration (it keeps permissions, model and other hooks, makes a backup, does not duplicate and does not touch invalid or unexpected JSON). Also, `prepare.ps1` (then called `preparar.ps1`) from start to finish on a new project: 61 s with the model already in the shared cache, without downloading it again.
- After the English translation: `new-project.ps1` with `-WithGit -WithGraphify -WithRag` and with the old Spanish parameter names on a shared external vault (19 files, no unfilled markers, no broken links); and the `rag.py` logic (indexing, hybrid/semantic/keyword search, raw-source detection, local server, hook gating and `RAG_DISABLE`, hook registration, evaluation) with a stand-in vector function instead of the real model, 25 checks passed.

**Not tested:**
- The `iniciar-memoria` skill end to end in a real conversation.
- Loading a generated project in a new Claude Code session (`.mcp.json` approval, skills triggering).
- Opening the generated vault in Obsidian.
- Connecting a vault that already has its own structure (the "Existing" mode depends on the agent's judgment, not on the script).
- Use with agents other than Claude Code.
- Graphify itself: it was neither installed nor run. `docs/GRAPH.md` is based on its README (and on a reference file from its installation for Claude), so its commands must be confirmed with `graphify --help` when turning it on.
- Automatic retrieval: `prepare.ps1` with the real model after the English rename, `prepare.ps1` with a model download from scratch (the shared cache already existed) and with Pythons other than 3.12; whether the server stays alive between real messages over the long term; macOS and Linux.
