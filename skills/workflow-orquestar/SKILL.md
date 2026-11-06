---
name: workflow-orquestar
description: Orchestrates a large job by splitting it among CLI agents (OpenCode with free models by default, agy as a fallback with Gemini/Claude, and OpenAI's Codex), with support for DAG graphs, test self-healing, live streaming with a visual monitor, smart 3-way merging and token and cost telemetry. Use it when the user asks to orchestrate, split work in parallel, audit or implement in parts.
---

# Orchestrate with `wf.py` (Multi-Agent Architecture)

(`workflow-orquestar` is Spanish for "orchestrate workflow"; the folder name is kept so existing installs keep working.)

The orchestrator (the agent that leads the work; it is chosen in `orchestrator.json`, e.g. `{"orchestrator": "codex"}`; the older Spanish name `orquestador.json` with the key `orquestador` still works) plans, writes the orchestration script, runs it and validates the final delivery. The `opencode` and `agy` agents are the labor force, working in isolated copies.

---

## 1. Engines and Workers

- **`opencode`** (first by default, free): free models of the OpenCode CLI (`npm install -g @opencode/cli`). No sign-in or cost; in tests it is the fastest (10-25 s). Check with:
  `opencode run --standalone -m opencode/nemotron-3-ultra-free "Reply only: ok"`
- **`agy`**: Antigravity CLI with Gemini and Claude models; high quota and tool support. Check with:
  `agy -p "Reply only: ok" --mode plan --model gemini-3.8-flash-low`
- **`codex`** (OpenAI account, paid): only with `worker="codex"`. It uses the model the person has configured in Codex (`codex exec -s read-only|workspace-write -C <folder>`).

### Quality levels (`tier`) and models

| `tier` | `opencode` (free) | `agy` (Gemini / Claude) | `codex` | What for |
|---|---|---|---|---|
| `max` | `opencode/nemotron-3-ultra-free` | `gemini-4-argon-high` | `default` | Complex architecture and security |
| `pro` | `opencode/nemotron-3-ultra-free` | `gemini-3.8-flash-high` | `default` | Changes that cross modules, deep refactoring |
| `standard` | `opencode/deepseek-v4.1-flash-free` | `gemini-3.8-flash-medium` | `default` | General development and controllers |
| `fast` | `opencode/minimax-m3.1-flash-free` | `gemini-3.8-flash-low` | `default` | Mechanical tasks, scaffolding, high volume |
| `design` | — | `claude-sonnet-5-5-medium` | — | Graphic design and visual components |

The default order is `opencode`, then `agy`.

---

## 2. Orchestrator Features

### A. Real-Time Visual Monitor
Lets you watch, in a **second, fixed terminal**, exactly what each agent is doing (reads, edits, commands, tests):
```powershell
# In Terminal 2:
python <skill folder>/monitor.py
# Or also:
python <skill folder>/wf.py --monitor
```
- **Interactive keys:** `[1-9]` to focus on a specific agent, `[0]` for a global tiled view of all agents at once, `[Q]` to quit.
- The on-disk log is written in real time to `%TEMP%\wf-runs\<RUN_ID>\agent-N.log`.

### B. Self-Healing and Local Tests (`verify_cmd`)
The agent is not considered done until its code passes the verification suite you give it:
```python
await agent(
    "Implement the StudentService service in StudentService.java",
    schema={"type": "object", "required": ["resumen"], "properties": {"resumen": {"type": "string"}}},
    workspace="branch",
    edit=True,
    verify_cmd="mvn test -Dtest=StudentServiceTest",  # Runs inside the isolated copy
    max_fixes=2                                      # Retries up to 2 times, feeding the error back
)
```
If the test fails, `wf.py` captures the error and asks the subagent to fix the files in its copy before handing in the work. (The schema key `resumen` means "summary"; schemas are yours to define.)

### C. Dependency Graphs (`dag` and `task`)
Lets you define non-linear flows in which a task waits for the results of others:
```python
t1 = task("db", prompt="Design the SQL schema...", schema=SchemaDB)
t2 = task("service", prompt="Create the service...", schema=SchemaService, depends_on=[t1])
t3 = task("controller", prompt="Create the controller...", schema=SchemaCtrl, depends_on=[t2])
t4 = task("docs", prompt="Generate the README...", schema=SchemaDoc, depends_on=[t1, t2])

# Resolves the topological order and parallelizes the tasks that are ready
results = await dag([t1, t2, t3, t4])
```

### D. Smart Merging and Collision Detection (`auto_integrate`)
- `check_collisions()`: checks whether two copies modified the same files.
- `auto_integrate()`: if the sets of files are disjoint, applies all the changes directly with `git apply --3way --whitespace=fix`.

### E. Telemetry and Cost Estimation
When the workflow finishes, `wf.py` reports to the console and to `telemetry.json`:
- Total time vs. accumulated agent time (parallel speed-up calculation, e.g. `3.5x`).
- Estimated tokens (input and output).
- Approximate cost in USD.

---

## 3. Available Primitives

| Primitive | Description |
|---|---|
| `agent(prompt, schema, role, tier, worker, workspace, edit, timeout, verify_cmd, max_fixes)` | Defines a runnable agent. |
| `parallel(items, fn)` | Runs tasks in parallel (up to `WF_MAX_PARALLEL`, 4 by default). |
| `pipeline(items, fn)` | Runs tasks in strict sequential order. |
| `task(id, prompt, schema, depends_on, **kwargs)` | Defines a node for directed graphs. |
| `dag(tasks)` | Resolves and runs the task graph concurrently. |
| `check_collisions()` | Returns collisions between worktrees. |
| `auto_integrate()` | Applies the diffs with a 3-way merge if there are no collisions. |
| `phase(name)` | Defines and records a phase in the logs and the visual monitor. |
| `log(...)` | Prints and records information in `log.txt`. |
| `cleanup_worktrees()` | Removes the isolated temporary copies. |

---

## 4. Full Implementation Template

```python
phase("Parallel Implementation")

tasks = [
    {"id": "students", "files": ["StudentService.java"], "test": "mvn test -Dtest=StudentServiceTest"},
    {"id": "teachers", "files": ["TeacherService.java"], "test": "mvn test -Dtest=TeacherServiceTest"},
]

done = await parallel(tasks, lambda t: agent(
    f"Implement {t['id']} editing only: {t['files']}. No commit.",
    schema={"type": "object", "required": ["resumen", "ok"], "properties": {"resumen": {"type": "string"}, "ok": {"type": "boolean"}}},
    role=t["id"],
    tier="standard",
    workspace="branch",
    edit=True,
    verify_cmd=t["test"],
    max_fixes=2
))

phase("Integration")
# Checks for collisions and merges with a 3-way merge
integrated = auto_integrate()
log("Branches integrated successfully:", integrated)
cleanup_worktrees()
```

---

## 5. Safety Rules

1. **Never** pass secrets, credentials or tokens in the prompts.
2. Subagents **do not commit or push**; they work in their isolated copies and the changes are applied with `auto_integrate()`.
3. Every task carries a terse-reply style by default (the "ultracave" text that `wf.py` embeds; turn it off with `WF_CAVEMAN=0`) to save tokens and latency.
4. If an agent fails, `wf.py` automatically moves on to the next worker in the list.
