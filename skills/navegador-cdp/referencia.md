# Technical reference

(`referencia` is Spanish for "reference". Method, command and file names in this skill are Spanish; each is glossed where it first appears. The glossary table is in `SKILL.md`.)

## Requirements and tested scope
- Node 22 or later (uses the built-in `fetch` and `WebSocket`) and Chrome or Edge installed.
- **Tested on Windows with Edge and with Chrome 156** (with and without a visible window): open, go, read, wait, click (CSS, text and coordinates), right click, type, select, Enter, Ctrl+A, file upload, screenshot and close; the whole process cycle (fail, fix, save, reuse, repair, gates), including one against a real site; a persistent profile whose cookie survives closing and reopening; and Chrome and Edge open at the same time, isolated from each other.
- **Not tested**: signing in to a real site (the user always does it by hand; Google may block it), macOS and Linux (the code has paths and `pkill` in place, but they have not been run) and non-Chromium browsers.
- `cerrar` (close) first closes the browser normally (`Browser.close`, about 4 s) so it saves cookies and session, and only forces whatever is left alive. Killing it abruptly used to lose the recent cookies of a persistent profile.

## `nav.mjs` commands
`node nav.mjs ayuda` (help) prints the full list. A **target** is a CSS selector, `texto=Save` or `x,y`. With `texto=`, the innermost visible element whose text matches wins (first the identical one, then those that are buttons, links or fields, then the shortest).

## `Pagina` API (for writing `ejecutar.mjs`)
In a process, `pagina` already arrives open in a new tab of its own, which is closed when it ends. `Pagina` means "Page".

| Method | What it does |
|---|---|
| `ir(url)` (go) | Navigates and waits for it to load. On pages that load in pieces, add `esperar(...)` |
| `esperar(objetivo, ms=15000)` (wait) | Waits for it to exist; fails with a clear message if not |
| `existe(objetivo)` (exists) | `true` or `false` without waiting |
| `clic(objetivo, {derecho, doble})` (click; right, double) | Moves and presses with real mouse events, after centering the element |
| `escribir(objetivo, texto)` (type) | Replaces the content of the field; empty text clears it |
| `seleccionar(objetivo, valor)` (select) | Picks an option of a `<select>` by value or by text |
| `tecla('Enter')` (key) | Also `Tab`, `Escape`, `Backspace`, `Delete`, arrows, `Ctrl+A`, `Shift+Tab`... |
| `leer(objetivo?)` (read) | Text of the element (or the field's value); with no target, all the text of the page |
| `html(objetivo?)` | HTML of the element or the page |
| `evaluar(js)` (evaluate) | Runs JavaScript in the page and returns the value (promises are supported) |
| `subir(objetivo, rutas)` (upload) | Clicks the button or the `<input type=file>` and fills in the file chooser |
| `captura(ruta, {completa})` (screenshot; full page) | Saves a PNG |
| `url()`, `titulo()` (title) | Current address and title |

Inside `proceso(name, async ({ pagina, params, paso, verificar, irreversible, carpeta }) => { ... })`:
- `params`: parameters that arrive as `key=value`.
- `paso('title', async () => {...})` (step): records the step; if it fails, the result says which one.
- `verificar(condition, 'what it proves')` (verify): at least one is mandatory; if it is false, the process fails.
- `irreversible('description')`: stops the process with code 10 unless it is run with `--confirmo`.
- `carpeta` (folder): the process folder, in case it needs to save output files.

Script exit codes: `0` ok, `1` error, `3` no verifications, `10` irreversible step not confirmed. The script also prints one line starting with `RESULTADO` (= RESULT) followed by JSON; `proceso.mjs` reads it. Its `estado` (status) field is one of `ok`, `error`, `sin_verificaciones` or `necesita_confirmacion`.

## Format of a saved process
`procesos/<name>/proceso.md` starts with a header with one line per field: `nombre` (name), `descripcion` (description), `sitio` (site), `sesion` (session), `parametros` (parameters, names separated by commas), `creado` (created), `guardado` (saved), `hash`. `listar` (list) reads that header. At the end there is an automatic "Build history (automatic)" block with the errors found so far, which accumulate across versions: it is the most useful part of the memory. Files written by an earlier Spanish-language version, with the heading "Historial de construcción (automático)", are recognized too.

`estado.json` counts successful and failed uses and sets `roto` (broken) when the last run failed. `guardar` (save) sets it back to `false` when it accepts a fixed version.

## Known pitfalls
- **PowerShell and quotes.** Passing JSON or text with double quotes to a program breaks easily. Use `key=value` for the parameters, or `--params-archivo path.json`, and for `eval` prefer single quotes inside the JavaScript.
- **Background processes.** Some agent tools kill processes started with `Start-Job` when the command ends. If you need something in the background, use the tool's own background-execution option. The commands of this skill finish by themselves and do not need it.
- **Coordinates.** The window size changes the layout, and the coordinates with it. Use selectors or `texto=`.
- **Google sign-in.** It sometimes blocks access in browsers with remote debugging ("this browser is not secure"). If that happens, stop and tell the user; do not try to work around it.
- **File chooser.** `<input type=file>` elements are often hidden: click the button that opens them (or the input itself) with `subir`, do not use `escribir`.
- **Repeated text.** If a container and its button have the same text, `texto=` already picks the innermost; if that fails, use a CSS selector.
- **Menus and pop-ups.** If something opens a new tab, look at it with `pestanas` (tabs) and work with `--tab`. Browser dialogs (`alert`, `confirm`) are not supported and can block the page.
- **`iframe`.** Selectors do not go into them. For the same origin, use `evaluar` with `document.querySelector('iframe').contentDocument`.
- **Dynamic sites.** `ir` only waits for the initial load. Before reading or clicking, `esperar` what must appear.
- **Error screenshots.** `ultimo-error.png` (last-error) stays in the draft's folder, or in the saved process's folder if a run failed. It can show data from the page.
- **Several browsers at once.** One port and one profile per window (`--puerto 9223 --perfil other-account`). Every command accepts `--puerto`, and `NAV_PUERTO` sets the default. They are only needed with different accounts: for the same user it is better to have **a single browser with one tab per task**.
- **Several tasks in one browser.** Each run of `proceso.mjs` (`probar` or `ejecutar`) opens its own tab and closes it when it ends, so you can launch several at once against the same port. With `nav.mjs` and more than one tab open you must pass `--tab <id>` (the new tab is created by `nueva <url>`, which prints its id). Tabs share cookies and session: that avoids signing in several times, but a site that keeps per-session state (shopping cart, "current item") may mix tasks up.
- **What was tested with several simultaneous runs** (Chrome, local page with a 1.2 s wait): 4, 12 and 20 at once, all correct; `estado.json` and the history ended with the exact count thanks to a file lock; the tabs closed by themselves. In parallel each run gets longer (from 1.6 s to about 7 s with 20), so there is a practical ceiling. If the same process fails several times at once, `ultimo-error.png` belongs to the last one that failed.
