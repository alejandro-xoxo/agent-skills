---
name: navegador-cdp
description: Drives Chrome or Edge without extensions (over CDP, with Node) to do one-off tasks on a website and to create, save and reuse repeatable browser processes. A new process is only saved to the skill's memory when the agent has run it from start to finish with no errors and a verified result. Use it whenever the user asks to open a website and do something on it, to automate a process in the browser, to "create a process", "run the process X", "list my processes" or "what processes do I have", or when no browser extension is available or the user does not want to depend on extensions. Works with any agent that can run shell commands.
---

# Browser without extensions, with process memory

Controls a Chrome or Edge browser through the debugging protocol (CDP), with Node scripts that have no dependencies. It needs no extensions, only a browser and Node 22 or later. The skill has two parts:

1. **One-off tasks**: open a website, read, click, type, upload files, take screenshots (`scripts/nav.mjs`).
2. **Process memory**: a repeatable process is built, tested until it runs clean and only then saved, so it can be reused later with one command (`scripts/proceso.mjs`).

In every command below, `S` is the `scripts/` folder of this skill, wherever it is installed, and commands are run as `node $S/nav.mjs ...` or `node $S/proceso.mjs ...`. If you need the full API or the known pitfalls, read `referencia.md`.

**Command names are Spanish** (the skill was written in Spanish first). This table is the translation; keep using the Spanish names when you run them:

| `nav.mjs` command | Meaning | | `proceso.mjs` command | Meaning |
|---|---|---|---|---|
| `abrir` | open a browser | | `nuevo` | create a draft |
| `estado` | status of opened browsers | | `probar` | test a draft |
| `cerrar` | close the browser | | `guardar` | save a draft into memory |
| `pestanas` / `nueva` / `cerrar-pestana` | list / create / close tabs | | `listar` | list processes |
| `ir` | go to a URL | | `ver` | show a process sheet |
| `leer` | read text | | `ejecutar` | run a saved process |
| `esperar` | wait for an element | | `reparar` | copy a saved process back to a draft to fix it |
| `clic` | click | | `borrar` | delete a saved process |
| `escribir` | type into a field | | | |
| `seleccionar` | pick an option of a `<select>` | | | |
| `tecla` | press a key | | | |
| `subir` | upload files | | | |
| `captura` | screenshot | | | |
| `titulo` / `url` / `html` / `eval` | title / URL / HTML / run JavaScript | | | |

Useful flags: `--puerto` (port), `--perfil` (profile name), `--navegador` (edge or chrome), `--tab` (tab id), `--confirmo` (the user confirmed the irreversible steps), `--borrar-perfil` (delete the profile on close).

## Why it works this way
- The browser that gets opened is **a separate window** with its own profile. It does not touch the user's normal browser, tabs or sessions. That is why the user **signs in by hand** when a site asks for it; passwords are never requested or stored.
- Without `--perfil`, the profile is temporary and is deleted on close. With `--perfil <name>` the session is kept between uses (useful for processes that would otherwise repeat a login), stored outside this folder in `%LOCALAPPDATA%\navegador-cdp\perfiles\`.
- A saved process is not "what the agent remembers": it is a script (`ejecutar.mjs`) plus its sheet (`proceso.md`), which any agent can read and run.

## User commands
When the user invokes the skill with arguments or asks for the same thing in other words, interpret it like this:

| User says | Do |
|---|---|
| `create <name> <explanation of the process>` | Follow the creation loop below |
| `list` (or "what processes do I have") | `node $S/proceso.mjs listar` and summarize the result |
| `run <name> [key=value ...]` | Follow "Use a saved process" |
| `show <name>` | `node $S/proceso.mjs ver <name>` |
| `repair <name>` | `reparar`, then the loop from step 4 |
| `delete <name>` | Confirm with the user, then run `borrar <name> --si` |
| any other request about a website | One-off task (next section) |

## One-off tasks
1. `node $S/nav.mjs abrir [--url U] [--perfil name]` (add `--headless` if the user does not need to see the window). If the site asks for a login, ask the user to sign in in that window and wait.
2. Work with `ir`, `leer`, `esperar`, `clic`, `escribir`, `seleccionar`, `tecla`, `subir`, `eval`, `captura`. `node $S/nav.mjs ayuda` lists everything. A target is a CSS selector, `texto=Save` (visible element with that text) or `x,y` coordinates.
3. Prefer **reading text and the DOM** (`leer`, `eval`) over looking at screenshots: it is cheaper and does not depend on the agent being able to see images. Use `captura` when you need to see something visual.
4. Wait before reading anything that loads late (`esperar`), and check the result of every action before moving on (for example, `leer` the confirmation message).
5. When done, `cerrar` if the browser was temporary. If there was a session the user wants to keep, leave it open or use a named profile.

If there are several tabs, say which one with `--tab <id>` (`pestanas` lists them). The default port is 9222 and it is changed with `--puerto`, which allows several windows at once, for example one per account.

## Create a process (creation loop)
Core idea: **a process that has not been seen working from start to finish is worthless as memory**, because the next time it would fail and nobody would know why. That is why `guardar` rejects any draft whose last attempt did not run clean, and there is no way around it. Your job is to reach that clean attempt for real, with no tricks.

1. **Understand.** Restate the process as numbered steps and find out only what is missing and blocking: site, parameters, whether it needs a session, what proves it went well. Identify **irreversible steps** (send, pay, delete, publish). If there are any, ask right away how to test them harmlessly (test account, dry-run mode, another recipient), because they get repeated during construction.
2. **Prepare the browser.** `abrir` (with `--perfil <name>` if a session is needed and you want to reuse it). The user signs in by hand. Check with `leer` or `url` that the session works.
3. **Explore by hand** with `nav.mjs` before writing anything: `leer`, `eval` to list fields and buttons, `captura`. Choose stable selectors (id, name, aria-label, visible text), not positions or coordinates, which change with the window size.
4. **Write the draft.** `node $S/proceso.mjs nuevo <name> "<description>"` creates `borradores/<name>/ejecutar.mjs` and `proceso.md`. In `ejecutar.mjs` put one `paso('clear title', ...)` for each user-visible step, `esperar` after navigating or clicking, and at the end **`verificar(condition, 'what it proves')` on the real result** (the confirmation text, the saved value, the downloaded file), not just "there was no error". With no verification at all, the attempt counts as failed.
5. **Test and fix.** `node $S/proceso.mjs probar <name> [key=value ...]`. If it fails, the output shows the failed step, the error, the URL, a summary of the page text and the path of a screenshot (`ultimo-error.png`): look at them, find the **real cause**, fix it and test again. Do not weaken a verification or delete a step to make it "pass": that would save a process that does not do what it says.
6. **If something cannot be solved** (captcha, two-step verification, a missing permission, a microphone, or about 8 attempts without progress), stop. Tell the user what you tried and what is blocking, and do not save anything.
7. **Irreversible steps.** Call `irreversible('what is about to happen')` right before each one. Without confirmation the attempt stops with `necesita_confirmacion` (needs confirmation): ask the user and, only if they authorize, repeat with `--confirmo`. Every confirmed run repeats the real action, so avoid fixing the script after a confirmed run unless it is essential, and ask for permission again if you do.
8. **Complete `proceso.md`.** Remove every "(complete)": what it does, parameters with an example, preconditions, steps, how it is verified, irreversible steps, pitfalls. `guardar` rejects an incomplete sheet. The front matter keys are Spanish because the tool reads them by name: `nombre` (name), `descripcion` (description), `sitio` (site), `sesion` (session), `parametros` (parameters), `creado` (created).
9. **Save.** `node $S/proceso.mjs guardar <name>`. It checks that the last attempt went well, that it has verifications, that `ejecutar.mjs` is exactly the one that was tested and that the sheet is complete. If it rejects, read the reasons and fix them; never copy files into `procesos/` by hand or edit `intentos.jsonl`.
10. **Wrap up.** Tell the user what was saved, how to run it (`ejecutar <name> key=value`) and that it was verified against the site as it was today (if the site changes, it may break). Close the browser if it was temporary.

## Use a saved process
1. `listar` and, if needed, `ver <name>` to learn the parameters, preconditions and irreversible steps.
2. Open the browser with the profile the sheet asks for. If the process has irreversible steps, tell the user what it will do before running it.
3. `node $S/proceso.mjs ejecutar <name> [key=value ...]`.
4. **OK**: report the result. **Error**: the process is marked `BROKEN` in `listar`; tell the user what failed and offer `reparar <name>`, which copies the process into `borradores/` and takes you to step 4 of the loop without touching the saved version until the fix runs clean. **`necesita_confirmacion`**: ask the user, and repeat with `--confirmo` only if they authorize.

## Saving tokens
This skill is already designed to spend little: `leer` and `eval` instead of screenshots, short outputs, and a saved process runs with one command instead of repeating the whole exploration.

If your environment also offers a terse-reply mode (for example "caveman"-style skills, which are not included in this repository), you can use it and keep it on while it is active, and apply it to the briefs you give other agents too (see `briefs/brief-proceso.md`). Do not promise specific savings: they depend on the model and the task. Files that get saved (`proceso.md`, comments in `ejecutar.mjs`) are always written in normal prose.

If the user asks to save tokens and you do not have that mode available, recommend installing it and make clear that this skill works the same without it. Do not download it or invent where to get it.

## Several processes in parallel (workflow-orquestar)
When the user asks to build or run **several** processes at once (for example, the same process on 10 sites, or 3 new processes), splitting them among agents saves time. The `workflow-orquestar` skill exists for that: it splits work among CLI agents (`opencode`, `agy`, `codex`) with a `wf.py` script.

**Before proposing it, check that it is available:** that you have the `workflow-orquestar` skill folder (with its `SKILL.md` and `wf.py`), and that at least one worker CLI exists (`opencode`, `agy` or `codex`; `Get-Command opencode`). If something is missing, **recommend installing it**, say what is missing (according to that skill, `opencode` is installed with `npm install -g @opencode/cli`; the `workflow-orquestar` skill is published in the same repository as this one) and carry on with the processes one at a time; do not install anything on your own.

How to combine them:
1. You are the orchestrator. Write the orchestration script following the `workflow-orquestar` skill, with one agent per process. By default up to 4 run at once.
2. **They all share a single browser and a single session, each agent in its own tab**. Open the browser once (`abrir --perfil <name>` if you want to keep the session), the user signs in by hand **only once**, and the agents work in different tabs. It is faster and uses fewer resources than one browser per agent.
   - `proceso.mjs probar` and `ejecutar` open and close their own tab by themselves, so several can be launched at once against the same port.
   - To explore with `nav.mjs`, each agent creates its own tab with `nueva <url>` and passes `--tab <id>` in all its commands (with several tabs open, `nav.mjs` refuses to act without `--tab`).
   - An agent never touches another agent's tab, nor the initial one, nor closes the browser: `cerrar` belongs to the orchestrator alone, and it would kill everyone's work.
3. **Separate browsers or profiles are only needed** if the agents need **different accounts**, or if the site does not allow two tabs with the same session at once (some sign you out or mix shared state). In that case, one `--puerto` and one `--perfil` per account.
4. Give each agent `briefs/brief-proceso.md` with its values (`NAME`, `PORT`, `TASK`, `PARAMS`, `MODE`, `REPORT` and `SKILL`, the absolute path of this skill's folder) and do not put secrets in the task. Each agent that builds a process needs a different `NAME`.
5. **Irreversible steps are not delegated.** The agent stops with `needs-confirm`; you ask the user and, if they authorize, repeat that run with `--confirmo`.
6. The `guardar` gate protects you even when agents are working: none of them can save a process without a clean, verified attempt. Still, **do not trust what they say in their report**: check with `listar` what was really saved and, if needed, with `ejecutar`.

**How many at once.** Measured with Chrome and a local test page: 4 simultaneous runs took 2.4 s versus 7.3 s one after another; 12 at once, 4.2 s; 20 at once, 9.0 s, although each one gets longer from competing for the browser. It also worked with a visible window. On real sites the times will differ: start with 4 (the orchestrator's default) and do not go beyond 8 per browser without checking.

It is tested that **several simultaneous runs share a browser without stepping on each other** (with a lock for `estado.json`). What has **not been run yet** is the `wf.py` orchestrator distributing real agents with this skill. If something fails, tell the user and continue sequentially.

## Rules
- Never ask for, type or store passwords. If a login appears, stop and ask the user to do it.
- Do not pass sensitive data as parameters or write it in `proceso.md`. The history stores only the parameter **names** and the URL without its query string, but error screenshots (`ultimo-error.png`) can show whatever was on the page.
- Work only on the websites the user named, and only in windows opened with `abrir`. Do not use or close their normal browser.
- A named `--perfil` stores cookies on disk. Tell the user, and offer `cerrar --borrar-perfil` when they no longer need it.
- Do not simulate or fake results: if you could not verify something, say so.

## Files
- `scripts/motor.mjs`: CDP engine and the `proceso()` wrapper. `scripts/nav.mjs`: one-off tasks. `scripts/proceso.mjs`: process memory.
- `borradores/<name>/` (drafts): processes under construction (`ejecutar.mjs`, `proceso.md`, `intentos.jsonl`).
- `procesos/<name>/` (processes): **the memory**: `ejecutar.mjs`, `proceso.md` (sheet with the specification and solved errors), `estado.json` (uses and whether it is broken), `historial.jsonl`, `versiones/` (previous versions).
- `plantillas/` (templates): starting point for a new process.
- `briefs/brief-proceso.md`: a ready-made task for a worker agent (build or run a process in its own tab of the shared browser).
- `referencia.md`: `Pagina` API, process format and known pitfalls.
