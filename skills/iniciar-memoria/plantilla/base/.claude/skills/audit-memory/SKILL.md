---
name: audit-memory
description: Periodic review of the project's memory. Finds broken links, orphan, duplicate, contradictory or outdated notes, and an AGENTS.md that has grown too long. Use it when the user asks to clean up or review the memory, or when AGENTS.md goes past 100 lines.
---

# Audit the memory

> **Requirement:** the project must have the `## Memory` block in `AGENTS.md`. If it does not, the memory is not set up: use the `iniciar-memoria` skill first (or tell the user) and do not go on.

Memory without maintenance fills up with old facts and contradictions, which is worse than having no memory. Propose changes; **do not delete anything without asking**. The vault path (`<vault>`) is in the `## Memory` block of `AGENTS.md`.

## 1. Size of what is always loaded
```bash
wc -l AGENTS.md docs/STATE.md
```
- `AGENTS.md` over 100 lines: move what only serves one part into a vault note or into a per-path rule in `.claude/rules/`.
- `docs/STATE.md` over 40 lines: it is piling up; trim it.

## 2. Broken links and orphan notes
Replace `<vault>` with the real path.
```bash
T=$(mktemp -d)
cd "<vault>"
find . -name '*.md' -print0 | xargs -0 -n1 basename | sed 's/\.md$//' | sort -u > "$T/names.txt"
grep -rhoP '\[\[\K[^\]|#]+' --include='*.md' --exclude-dir='05 Sources' --exclude-dir=Templates --exclude-dir=.obsidian . | sed 's/[[:space:]]*$//' | sort -u > "$T/links.txt"
echo "--- broken links:"; comm -23 "$T/links.txt" "$T/names.txt"
echo "--- notes with no incoming links:"
while IFS= read -r n; do grep -rqF "[[$n" --include='*.md' --exclude-dir=Templates . || echo "$n"; done < "$T/names.txt"
```
Adjust `--exclude-dir` to the real name of the sources folder. Ignore the templates and the index itself as orphans. If the vault is shared with other projects, limit the search to this project's subfolder.

## 3. Old, duplicate or contradictory content
- Search by keyword for ideas that appear in several notes and merge them.
- For each note with `status: proposed` that has been that way for a long time, ask whether it is still valid.
- Check 3 or 4 concrete facts (paths, commands, figures) against the real source. If they no longer match, fix the note and record it in `docs/DECISIONS.md`.
- If two notes contradict each other, tell the user; do not pick one silently.

## 4. Report
Hand over a short list: what you found, what you propose to change and what you need the user to confirm. Apply only what they confirm.