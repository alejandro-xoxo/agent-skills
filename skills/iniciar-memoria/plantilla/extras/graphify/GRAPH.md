# Code graph with Graphify: how to turn it on when {{NAME}} grows

**Status: prepared, not installed.** This project only brings the configuration and this guide. Nothing of Graphify is installed or has been run.

## What it is and what it is not
[Graphify](https://github.com/Graphify-Labs/graphify) (Apache-2.0 license) turns a project into a knowledge graph that the agent queries instead of reading or `grep`-searching many files: who calls what, what connects to what, which are the central concepts.

- It **does** help to find your way around a large code repository and to spend fewer tokens reading files.
- It does **not** replace this memory. It does not store decisions, lessons or the state of the work: that stays in `docs/STATE.md`, `docs/DECISIONS.md` and the vault. The graph says *what is connected*; the memory says *why, and where we are*.

## When to turn it on
Not before it is needed. Signs that it is time:
- The repository has quite a few modules and the agent spends a lot reading files to find out who uses what.
- `grep` returns too many irrelevant results.
- You ask questions like "what breaks if I change this function?" and they are hard to answer.

With a small repository it adds nothing: the agent already walks through all of it.

## How to turn it on (when the time comes)
The commands come from Graphify's README and **have not been tested here**. Confirm them with `graphify --help` and at https://docs.graphify.com.

1. **Requirements:** Python 3.10 or later, and `uv` or `pipx`.
2. **Install:** `uv tool install graphifyy` (with a double "y"). Check in the official repository that this is the right package before installing.
3. **Review `.graphifyignore`** (it is already at the project root). It excludes sources with personal data.
4. **First graph, code only, no model and no network:** `graphify extract . --code-only`. The code is analyzed locally with tree-sitter.
5. **Query:** `graphify query "<question>"`, `graphify path "A" "B"`, `graphify explain "X"`.
6. **Keep it up to date:** `graphify update .` after changing code (it only analyzes what changed).
7. **Have the agent use it:** add a line to `AGENTS.md`: "For questions about the code, query `graphify query` before searching with grep". It is simpler and more controllable than the "always on" mode.

## What not to do in this project
- **Do not run `graphify claude install`.** It writes a section into `CLAUDE.md`, and with that file present Claude Code stops reading `AGENTS.md`, which is where the memory is. If you already did, add `@AGENTS.md` to `CLAUDE.md` or remove the section with `graphify claude uninstall`.
- **Do not turn on the strict hook mode (`--strict`).** It can deny file reads and searches, including those of the vault.
- **Do not index sources with personal data.** Code and audio are processed locally, but documents, PDFs and images are sent to the assistant's model. To avoid that, keep `.graphifyignore` up to date or use `--code-only`.
- **Do not trust the savings figures** ("80% fewer tokens") until you measure them in this project: they come from the tool's author.
- If you are offered *Graphify Cloud*, it is a separate paid service; it is not needed for anything above.

## What it leaves on your machine
The graph is stored in `graphify-out/` (`graph.json`, `GRAPH_REPORT.md`, `graph.html`), which `.gitignore` already ignores because it is regenerated. According to its README, it logs your queries in `~/.cache/graphify-queries.log`, and sends no telemetry.

## Removing it
`graphify uninstall` (add `--purge` to also delete `graphify-out/`). Then remove the line you added to `AGENTS.md`.