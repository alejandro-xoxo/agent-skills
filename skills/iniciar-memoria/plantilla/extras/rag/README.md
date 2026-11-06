# Automatic retrieval (local RAG)

Adds to the user's message, before the agent sees it, the most relevant chunks of the vault and of `docs/`, with file and lines. It is a search by meaning (vectors) mixed with exact words, and it runs entirely on this machine.

## What it is and what it is not
- **Yes:** it helps when the sources are large (conversations of thousands of lines, many documents) and `grep` does not find things by meaning. Curated notes weigh more than raw material.
- **No:** it does not replace `AGENTS.md`, `STATE.md` or the notes. And it does not make the AI more accurate by itself: it improves which chunks reach it. Each chunk carries file and lines so it can be verified.

## How it is turned on
1. `new-project.ps1 -WithRag` (or `-RagOnly` on a project that already exists) copies these files to `.rag/`, adds a line to `AGENTS.md` and ignores `.rag/` in git. **It installs nothing.**
2. `powershell -NoProfile -ExecutionPolicy Bypass -File .rag\prepare.ps1` does the heavy part: Python environment, `fastembed`, index, Claude Code hooks and server. The first time it downloads about 0.6 GB (the model, which all projects share in `%USERPROFILE%\.cache\rag-models`) and can take several minutes.
3. Open `/hooks` once or restart the agent session.

## Requirements
Windows with PowerShell and the `py` launcher, and Python 3.10 to 3.13. Tested with Python 3.12. It does not work on Python 3.15 because `onnxruntime` did not publish a version for it.

## What it does in the background
- A local server (only `127.0.0.1`, with a key) keeps the model loaded and answers in tens of milliseconds. It uses about 700 MB of memory while active and shuts itself down after 30 minutes without use. The session-start hook starts it again, and if a message arrives while the server is off, that message goes without context (the hook never waits more than about 3 s) and the next one already has it.
- On Windows the server is launched through WMI and with no console (`pythonw`). Reason: in a real session, a server launched directly from a hook disappeared soon after (it is inferred that it died with the hook). Through WMI, in one test, it survives even if the whole process tree of whoever launched it is closed. That it stays alive between real messages over the long term has not been verified.
- If you change a note, the index updates itself in the background; the change shows up within a few seconds and no search waits.
- It only injects context if the message is about something in the vault (minimum similarity 0.50, adjustable with `RAG_THRESHOLD`). `/` commands, very short messages and automatic system notices inject nothing. If the message does not pass the threshold, nothing is injected: giving no context is better than giving the wrong one.

## Costs and cautions
- Each related message adds between 500 and 900 tokens of context.
- `.rag/index/` stores the full text of the sources, including any personal data they contain. It is outside git; do not copy it to other people.
- The injected context travels to the model as part of the conversation. The vectors are computed here.
- To turn it off: environment variable `RAG_DISABLE=1`. To remove it: delete `.rag/` and the two hooks in `.claude/settings.local.json`.

## Measuring whether it works
Copy `evaluation.example.json` as `evaluation.json`, change the questions to 15 or 20 of your own (with the file where the answer is) and run `rag.py evaluate`. It shows the hit rate of keywords, meaning and the mix, and the recommended threshold. In the first project where it was tried, with 20 questions written by someone who knew the notes, the mix hit in the top 3 95% of the time and the keywords alone 70%; with your own questions the result may differ.

## Untested
macOS and Linux, and Pythons other than 3.12 (`prepare.ps1` looks for 3.12, 3.13, 3.11 and 3.10, in that order). Whether the hooks fire in a real session depends on Claude Code loading them (step 3).