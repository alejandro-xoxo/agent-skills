# agent-skills

Skills for AI agents that can run shell commands. **They do not depend on a specific agent**: they are folders with instructions (`SKILL.md`) and ordinary scripts that any agent can read and run. With them, an agent can drive the browser without extensions, split a big job among several command-line agents keep a project's memory organized (state, decisions, lessons and an Obsidian vault) and work in Git under a professional GitFlow routine.

The skills were first written in Spanish and are now in English. The folder names (`navegador-cdp`, `workflow-orquestar`, `iniciar-memoria`) and the names of the commands of `navegador-cdp` are kept in Spanish so existing installs keep working; each `SKILL.md` includes a table that translates them. The `git-work` skill is still written in Spanish.

## Skills

| Skill | What it is for |
|---|---|
| [`navegador-cdp`](skills/navegador-cdp) ("CDP browser") | Drives Chrome or Edge **without extensions**, with Node scripts that have no dependencies. It is for one-off tasks on a website (open, read, click, type, upload files, screenshots) and for **creating, saving and reusing repeatable processes**: a new process is only saved to memory after it has run from start to finish with no errors and with its result verified. |
| [`workflow-orquestar`](skills/workflow-orquestar) ("orchestrate workflow") | Orchestrates a large job by splitting it among CLI agents (OpenCode, agy and Codex), with dependency graphs, self-healing with tests, a live visual monitor, change merging and token and cost telemetry. The leading agent is chosen in `orchestrator.json`. |
| [`iniciar-memoria`](skills/iniciar-memoria) ("start memory") | Sets up a **project's memory** from a bundled template (`plantilla/`): a short `AGENTS.md` that is always loaded, `docs/STATE.md` (where the work stands), `docs/DECISIONS.md`, three memory skills (`memory`, `close-task`, `audit-memory`) and an Obsidian vault. It can **connect a vault you already have** without touching it. Optionally it prepares the ground for a code graph (Graphify, not installed) and for **automatic retrieval** of the vault: a local semantic search that adds the most relevant chunks to every message. Nothing heavy is installed without your go-ahead. |
| [`git-work`](skills/git-work) ("git workflow") | A professional Git routine under **GitFlow**: work branches (`feat/*`, `fix/*`, `refactor/*`) that start from and merge into `develop`, a controlled step from `develop` to `main` by SemVer release, short atomic commits under Conventional Commits with no AI watermarks, and a toolbox for merge and rebase conflicts, worktrees and recovery. It includes `scripts/git_doctor.py`, a repository check. |

The first two complement each other: with `workflow-orquestar`, several agents can build or run several `navegador-cdp` processes at once, each in its own tab of the same browser.

## Requirements

- **`navegador-cdp`**: Node.js 22 or later and Chrome or Edge installed.
- **`iniciar-memoria`**: Windows with PowerShell 5.1 or later (the template script, `new-project.ps1`, is PowerShell). For the optional automatic retrieval, also the `py` launcher with Python 3.10 to 3.13 (tested with 3.12) and about 0.6 GB of download the first time. Obsidian is optional.
- **`git-work`**: git, and Python 3 for `scripts/git_doctor.py`.
- **`workflow-orquestar`**: Python 3, git, and at least one worker CLI installed (`opencode`, `agy` or `codex`). It includes `selftest.py`, which tests the orchestrator with a fake worker, without spending quota or calling any model.

## Installation

A skill is a folder with a `SKILL.md` (the instructions for the agent) and the scripts that text tells it to run. There is nothing to compile or to install with a package manager.

```bash
git clone https://github.com/alejandro-xoxo/agent-skills.git
```

Then, depending on your agent:

- **If your agent loads skills from a folder** (for example, from `~/.claude/skills/`), copy the folders of `skills/` that you want there:

  ```powershell
  # Windows (PowerShell)
  Copy-Item -Recurse agent-skills\skills\navegador-cdp $HOME\.claude\skills\
  ```
  ```bash
  # macOS / Linux
  cp -r agent-skills/skills/navegador-cdp ~/.claude/skills/
  ```

- **If your agent does not load skills**, leave the folder wherever you like and tell it to read the `SKILL.md`: for example, add a line to its instructions file (such as `AGENTS.md`):

  ```
  To drive the browser, read and follow skills/navegador-cdp/SKILL.md
  ```

Copy the `iniciar-memoria` folder **whole**, with its `plantilla/` subfolder inside: the skill looks for the template next to its `SKILL.md`. If you separate the two, the skill will ask you where it is.

You may have to restart the agent session for it to recognize the new skills.

## Quick start: `navegador-cdp`

The scripts can be used directly, with any agent (or by hand). The command names are Spanish (`abrir` = open, `leer` = read, `cerrar` = close, `ayuda` = help, `listar` = list):

```bash
node skills/navegador-cdp/scripts/nav.mjs abrir --url https://example.com   # opens a separate browser
node skills/navegador-cdp/scripts/nav.mjs leer                              # reads the text of the page
node skills/navegador-cdp/scripts/nav.mjs cerrar
node skills/navegador-cdp/scripts/nav.mjs ayuda                             # lists all the commands

node skills/navegador-cdp/scripts/proceso.mjs listar                        # saved processes
```

An agent that reads `SKILL.md` knows how to build and reuse processes. In agents that expose skills as commands, you ask for it like this (the command name may vary depending on the agent):

```
/navegador-cdp create download-statement Go to my bank, download this month's statement and check that the file exists
/navegador-cdp list
/navegador-cdp run download-statement month=october
```

The core idea: **a process that has not been seen working from start to finish does not count as memory**. `guardar` (save) rejects any draft whose last attempt did not run clean, that has no verification of the real result, or whose script changed after it was tested. The detail is in [`SKILL.md`](skills/navegador-cdp/SKILL.md) and [`referencia.md`](skills/navegador-cdp/referencia.md).

## Quick start: `iniciar-memoria`

With an agent that loads the skill, just ask it ("start the memory of this project", "connect it to my Obsidian vault"). You can also use the script directly, without an agent:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File skills\iniciar-memoria\plantilla\new-project.ps1 `
  -Destination "C:\path\to\my-project" -Name "My project" -Description "What it does" -WithGit
```

It creates `AGENTS.md`, `docs/` and a vault in `knowledge/` **without overwriting** anything that already exists (`-Force` allows it). With `-Vault "<path>"` it uses an Obsidian vault you already have instead of creating one. `-WithGraphify` and `-WithRag` only copy files and add lines to `AGENTS.md` and `.gitignore`; turning on the RAG is a separate step (`.rag\prepare.ps1`) that the skill only runs if you explicitly ask it to ("turn on the RAG"). The details, the memory levels and what has been verified are in [`plantilla/README.md`](skills/iniciar-memoria/plantilla/README.md).

## Quick start: `workflow-orquestar`

The leading agent writes a short script with the orchestrator's primitives (`agent`, `parallel`, `dag`, `auto_integrate`...) and launches it with `python wf.py script.py`. See [`SKILL.md`](skills/workflow-orquestar/SKILL.md) for the primitives, the quality levels (`tier`) and the safety rules. To choose which CLI leads, create an `orchestrator.json` in the skill's folder with `{"orchestrator": "codex"}` (values: `claude`, `agy`, `opencode`, `codex`; the default is `claude`). The older Spanish name, `orquestador.json` with the key `orquestador`, still works.

## Status and limits

This is an initial version (`0.1`). It is worth saying clearly what has been verified:

- **Tested**: `navegador-cdp` on Windows 10 with Node 24, Edge and Chrome 156, with and without a visible window: the complete process cycle (fail, fix, save, reuse, repair), including one against a real site, a persistent profile that keeps the session, and up to 20 simultaneous runs in a single browser. So far it has been driven by a single agent. After the translation to English, its create → test → save → run → repair → delete cycle was run again against a local page in a headless browser.
- **Untested**: macOS and Linux (the code allows for them, but they have not been run); `navegador-cdp` with agents other than the one above; signing in to real sites (the person always does it by hand, and some sites, such as Google, may block it in a browser with remote debugging); and the combination of the two skills with real agents from start to finish.
- **`workflow-orquestar`**: `selftest.py` (26 checks with a fake worker) passes. It has not been run against real OpenCode, agy or Codex workers after the translation.
- **`iniciar-memoria`**: the template and the script were tested on Windows 10 (PowerShell 5.1), including use with an external vault and the preparation of Graphify and the RAG. Automatic retrieval was turned on and measured in a real project with Python 3.12 (the mix of search by meaning and by keywords hit in the top 3 results 95% of the time with 20 questions written by someone who knew the notes; with other notes the result may differ). **Untested:** macOS and Linux, other Python versions, agents other than the one above, and the local server staying alive through weeks of real use. The hooks for automatic retrieval (`.claude/settings.local.json`) are written for Claude Code; with another agent you have to wire `rag.py hook` by hand or not use it. Graphify is never installed by the skill.
- Dynamic pages, `iframe`s and browser dialogs (`alert`, `confirm`) have limited support. The details and the known pitfalls are in `referencia.md`.

## Safety and responsible use

- The browser is opened with a **local debugging port**: while the window exists, any process on your machine can control it and see the sessions it has open. Close it when you are done.
- **Passwords are never requested or stored.** When a site asks to sign in, the person does it by hand in the window. A named profile stores cookies on disk, outside the repository.
- Do not pass sensitive data as parameters of a process. Error screenshots can show what was on the page.
- Irreversible steps (send, pay, delete, publish) stop until the person confirms them.
- `iniciar-memoria` does not store passwords or personal data. If you connect a vault with material about people, `.rag/index/` stores the **full text** of the sources you index: it is outside git and must not be shared. The vectors are computed on your machine; the context injected into a message does travel to the model as part of the conversation.
- Automate only sites and accounts that are yours or that you have permission for, and respect each site's terms of use. The author is not responsible for how these tools are used.

## Author and license

Created by [alejandro-xoxo](https://github.com/alejandro-xoxo). Proprietary license ([LICENSE](LICENSE)): all rights reserved. You may view the code to evaluate it; you may not copy, modify, redistribute or sell it without the author's prior written permission. Versions before this license change were published under MIT. See also [`NOTICE.md`](NOTICE.md) for the credits and the third-party tools these skills use but do not include.

Issues and improvement proposals are welcome.
