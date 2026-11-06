---
name: iniciar-memoria
description: Starts or loads a project's memory and, if the user asks, connects it to an Obsidian vault that they point to. Use it when starting work on a project that has no memory set up, when the user says "start the memory", "load the project context", "connect to Obsidian" or "connect it to my vault", or when they want to switch vaults. It applies the memory template if it is missing; if it already exists, it loads the state and the index. It can also prepare, without installing anything, the code graph (Graphify) when the user wants the ground ready for when the project grows. It can also prepare and turn on automatic vault retrieval (local semantic search that adds the relevant chunks to every message).
---

# Start the memory and connect Obsidian

(`iniciar-memoria` is Spanish for "start memory"; the folder name is kept so existing installs keep working.)

**Template:** the `plantilla/` folder ("template" in Spanish) that sits next to this `SKILL.md` (script `new-project.ps1`, folder `base/`, `README.md`). If you cannot find it there, tell the user and ask where it is; do not recreate it from memory.

**What this skill does and does not do:** loading the memory automatically in every session is done by `AGENTS.md` (the "Start here" section). This skill is for **setting up** a project, for **loading the memory on request** and for **connecting an Obsidian vault**. Obsidian does not need to be open or have plugins: the vault is files, and they are read and written directly.

## Step 1: what state is the project in?
In the working directory, check:
- Is there an `AGENTS.md` with a `## Memory` block?
- Is there a `docs/STATE.md`?
- Is there a `CLAUDE.md` or `CLAUDE.local.md`? If there is, Claude Code **does not read** `AGENTS.md`.
- Is there git and project files of its own?

Classify: **A** no memory, **B** with memory, **C** partial.

## A: no memory, apply the template
1. Ask in one go for whatever is missing (do not repeat what the user already said): project name, one-line description, stack (optional), whether they want `git init`, and whether the vault goes **inside the project** (by default, `knowledge/`) or is **an existing Obsidian one** (then ask for the path and follow the "Connect to a vault" section). If the project is going to have a fair amount of code, also offer to leave the **code graph** (Graphify) **prepared**: it is optional and only leaves guide files, it installs nothing. If the vault will have large sources (conversations of thousands of lines, many documents), also offer **automatic retrieval** (local semantic search): when creating the project it only leaves prepared files.
2. If the project already has an `AGENTS.md` of its own, do not replace it. If it has a `CLAUDE.md`, explain that it hides `AGENTS.md` and offer: (a) adding `@AGENTS.md` inside `CLAUDE.md`, or (b) migrating its content. Do only what they choose.
3. Run the script (it does not overwrite what exists, and it says so):
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<this skill's folder>\plantilla\new-project.ps1" -Destination "<project path>" -Name "<name>" -Description "<description>" [-Stack "<stack>"] [-WithGit] [-WithGraphify] [-WithRag] [-Vault "<path>" [-Folder "<name>"]]
```
4. Check: `AGENTS.md` without `{{...}}` markers, `docs/STATE.md` created and the vault accessible.
5. Summarize what was created and what is left to fill in: commands and golden rules in `AGENTS.md`, and the vault's "Project and goal" note. If they asked for the code graph, say it was left prepared and that it is turned on later by following `docs/GRAPH.md`. If they asked for automatic retrieval, say it was left prepared and that turning it on is a separate step (section "Automatic vault retrieval").

## B: with memory, load it
1. Read `docs/STATE.md` and the `## Memory` block of `AGENTS.md`.
2. Check that the vault exists and you can read it (if it is outside the working directory, see "Access" below). Read its index.
3. Summarize for the user in 5 lines at most: where the work stands, next step, blockers or open questions, and what is unverified.
4. Do not read more. The rest is consulted with the `memory` skill when the task calls for it. Verify against the source whatever you are going to use.
5. If `docs/GRAPH.md` exists and the project already has a fair amount of code, mention **once** that the code graph can now be turned on; do not turn it on unless the user asks. If `docs/GRAPH.md` does not exist and the project already has a fair amount of code, offer it (section "Prepare the code graph").
6. If the vault has large sources and `.rag/` does not exist, offer automatic retrieval. If `.rag/` exists but `.rag/.venv` does not, it is prepared but not turned on: say so once and do not turn it on unless the user asks.

## C: partial
Complete whatever is missing with the same script (it does not overwrite). Say what you added.

## Prepare the code graph (optional)
Use it when the user wants the ground ready for when the project grows, or when there is a fair amount of code and `docs/GRAPH.md` does not exist. **It only leaves things prepared: it does not install or run Graphify.**
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<this skill's folder>\plantilla\new-project.ps1" -Destination "<project path>" -Name "<name>" -GraphifyOnly
```
It copies `.graphifyignore` and `docs/GRAPH.md`, adds a line to the `AGENTS.md` map and ignores `graphify-out/` in `.gitignore`. It does not create the vault or `knowledge/`, nor touch git. Review `.graphifyignore` with the user, above all that it excludes sources with personal data. To really turn it on, follow `docs/GRAPH.md`, and only if the user asks.

## Automatic vault retrieval (optional)
Use it when the user wants the agent to receive on its own, with every message, the most relevant chunks of the vault and of `docs/` (with file and lines), or when the raw sources are large. It takes two steps:

1. **Prepare (fast, installs nothing).** In a new project `-WithRag` in the command of section A is enough. In one that already exists:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<this skill's folder>\plantilla\new-project.ps1" -Destination "<project path>" -Name "<name>" -RagOnly
```
It copies `.rag/` (engine, activation script, guide and evaluation example), adds a line to `AGENTS.md` and ignores `.rag/` in git. It does not create the vault or `knowledge/`, nor touch git.

2. **Turn on (heavy: only with the user's go-ahead).** Before running it, explain what it will do: it creates a Python environment inside `.rag/`, installs `fastembed`, downloads the model the first time (about 0.6 GB, shared by all projects), takes several minutes, leaves a local server in the background and writes two hooks in `.claude/settings.local.json` (with a backup if it already existed). If they accept:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<project path>\.rag\prepare.ps1"
```
It needs Windows, the `py` launcher and Python 3.10 to 3.13. If it fails because of Python, say so as it is and do not improvise alternatives. The hooks are written for Claude Code; with another agent, `rag.py hook` has to be wired by hand or not used.

When it finishes, tell them to open `/hooks` once or restart the session so the hooks get loaded, and tell them what it costs: about 500 to 900 more tokens for each message related to the vault; `.rag/index/` stores the full text of the sources (it must not be shared); it is turned off with the variable `RAG_DISABLE=1`. `.rag/README.md` explains how to measure its quality with questions of their own.

## Connect to an Obsidian vault
When the user says "connect it to my vault", gives a path or wants another vault:

1. **Path.** Ask for it if they did not give it. In the desktop app you can open a folder picker with the `request_directory` tool (with no path). Do not guess paths.
2. **Validate.** Does it exist? It is an Obsidian vault if it contains `.obsidian/`. If it exists without `.obsidian`, ask whether it is a new vault (Obsidian will create it when opening it).
3. **Access.** If it is outside the working directory, get access: `request_directory` with the path (desktop app) or, in a terminal, ask the user to run `/add-dir <path>`. Without access, stop.
4. **Look at what is there** (first-level folders and how many `.md` notes) and pick the mode. If in doubt, ask **a single** question.

| The vault... | Mode | What you do |
|---|---|---|
| Is empty or new | Dedicated | Create the structure with `new-project.ps1 -VaultOnly -Vault "<path>" -Destination "<project>" -Name "<name>"` |
| Is a "second brain" with notes on other topics | Shared | The same, adding `-Folder "<project name>"`. Warn: repeated note names (Inbox, Glossary...) can confuse the links between projects |
| Already has this project's notes with another structure | Existing | **Do not create folders.** List the folders and identify index, inbox, lessons, decisions and sources by name (Home/Index/MOC, Inbox, Lessons, Decisions/ADR, Sources). Confirm the map with the user if anything is ambiguous. Leave whatever does not exist without a path, and say so |

5. **Update the `## Memory` block of `AGENTS.md`.** Edit only that block: the `Obsidian vault:` line with the path (with `/` slashes) and the relative-paths line with the real map. In Shared mode the path includes the subfolder.
6. **Record it.** Add 5 lines to `docs/DECISIONS.md` (which vault, mode and why) and mention it in `docs/STATE.md`.
7. **Check.** Read the index from the new path. If you created structure, run the link check of the `audit-memory` skill.
8. **Tell the user** how to open it: in Obsidian, **Open folder as vault** and choose the **vault** folder (not the project's). Obsidian does not need to be open for you to read and write.

### Change or remove the vault
Change only the vault line and the map in `AGENTS.md`. Do not move or delete notes from the previous vault. Record it in `docs/DECISIONS.md`.

## Rules
- Never overwrite or delete the user's notes. If the script says "already exists, skipped", that is fine.
- Do not create `CLAUDE.md` or `CLAUDE.local.md`.
- Do not run `git commit`. `git init` only if the user asked for it.
- Do not install Obsidian plugins or MCP servers unless asked; they are not needed.
- Do not install or run Graphify: this skill only leaves the ground prepared. Never run `graphify claude install` (it writes `CLAUDE.md`).
- Do not turn on automatic retrieval (`.rag\prepare.ps1`) without the user's go-ahead: it downloads hundreds of MB and leaves a process in the background. Do not edit the hooks of `.claude/settings.local.json` by hand: that script registers them, merging without overwriting what is already there.
- Do not put personal data or secrets in the notes.
- If something does not add up (nonexistent path, vault with no access), stop and say so.
