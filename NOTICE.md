# Credits and notices

## Authorship

The `navegador-cdp`, `workflow-orquestar` and `iniciar-memoria` skills (with its `plantilla/` folder) of this repository are the work of **alejandro-xoxo** (https://github.com/alejandro-xoxo) and are published under a proprietary license, with all rights reserved (see `LICENSE`). Copyright (c) 2026 alejandro-xoxo. Versions before this change were published under the MIT license.

## Third-party tools that are used but not included

These skills work alongside programs that are **not part of this repository** and are governed by their own licenses and terms of use. Install them from their official sources:

- **Node.js**, and the **Google Chrome** and **Microsoft Edge** browsers, with their debugging protocol (Chrome DevTools Protocol), which `navegador-cdp` uses.
- **Python 3** and **git**, which `workflow-orquestar` uses.
- **PowerShell** (Windows), **Obsidian** (optional; the vault is plain text files and it does not need to be installed) and, only if you turn on the optional features of `iniciar-memoria`, **Graphify** (Apache-2.0; only the ground is prepared: it is neither installed nor redistributed) and the Python libraries that `plantilla/extras/rag/prepare.ps1` installs into a local environment of the project, without including them in this repository: `fastembed` (Apache-2.0), `numpy` (BSD-3-Clause and other permissive licenses), `onnxruntime` (MIT), `tokenizers` (Apache-2.0) and `huggingface_hub` (Apache-2.0).
- The embedding model `jinaai/jina-embeddings-v2-base-es` (Apache-2.0, according to its Hugging Face page), which is downloaded the first time automatic retrieval is turned on and is **not** included here. Its license and terms are those of its authors.
- The agent CLIs that `workflow-orquestar` can launch as workers: **OpenCode CLI** (`opencode`), **Antigravity CLI** (`agy`) and **Codex CLI** (`codex`). Using them may require an account, have quotas and costs, and their own terms.

## Related skills that are not included

The text of the skills mentions, as **optional**, terse-reply modes offered by other skills. They are neither included nor redistributed here; their authorship and license are those of their own authors. The `wf.py` orchestrator embeds its own terse-style text and does not need them installed.

## Third-party content that is not included

`iniciar-memoria` is inspired by common agent-memory practices (a short `AGENTS.md`, an Obsidian vault, skills with progressive loading) and cites Claude Code's documentation about memory as a reference (<https://code.claude.com/docs/en/memory>). No text is copied from that documentation or from any third-party guide. The example vault the template generates is empty: it contains no data from any project or any person.

## Trademarks

Chrome, Edge, OpenCode, Antigravity, Codex, Claude Code, Obsidian, Graphify, Hugging Face and the other product names mentioned belong to their respective owners and are named only to indicate compatibility.
