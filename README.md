# agent-skills

Skills para agentes de IA que pueden ejecutar comandos de shell. **No dependen de un agente concreto**: son carpetas con instrucciones (`SKILL.md`) y scripts normales que cualquier agente puede leer y ejecutar. Con ellas, un agente puede manejar el navegador sin extensiones, repartir un trabajo grande entre varios agentes de línea de comandos y dejar la memoria de un proyecto organizada (estado, decisiones, lecciones y un vault de Obsidian).

*English summary: three agent-agnostic skills, each a folder with instructions (`SKILL.md`) and plain scripts. `navegador-cdp` drives Chrome or Edge over the DevTools Protocol with no extension, and keeps a memory of repeatable browser processes that are only saved after a clean, verified run. `workflow-orquestar` splits a big job across CLI agents (OpenCode, agy, Codex). `iniciar-memoria` sets up project memory (a short `AGENTS.md`, status and decision logs, an Obsidian vault) from a bundled template, and can optionally prepare a code graph and a local semantic-retrieval hook (the retrieval hook is wired for Claude Code and Windows only). The skill texts are written in Spanish.*

## Skills

| Skill | Para qué sirve |
|---|---|
| [`navegador-cdp`](skills/navegador-cdp) | Maneja Chrome o Edge **sin extensiones**, con scripts de Node sin dependencias. Sirve para tareas puntuales en una web (abrir, leer, hacer clic, escribir, subir archivos, capturas) y para **crear, guardar y reutilizar procesos repetitivos**: un proceso nuevo solo se guarda en la memoria cuando se ejecutó de principio a fin sin errores y con el resultado verificado. |
| [`workflow-orquestar`](skills/workflow-orquestar) | Orquesta un trabajo grande repartiéndolo entre agentes de CLI (OpenCode, agy y Codex), con grafos de dependencias, auto-corrección con tests, monitor visual en vivo, fusión de cambios y telemetría de tokens y costes. El agente que lidera se elige en `orquestador.json`. |
| [`iniciar-memoria`](skills/iniciar-memoria) | Deja la **memoria de un proyecto** lista a partir de una plantilla incluida (`plantilla/`): un `AGENTS.md` corto que se carga siempre, `docs/ESTADO.md` (dónde quedó el trabajo), `docs/DECISIONS.md`, tres skills de memoria (`memoria`, `cerrar-tarea`, `auditar-memoria`) y un vault de Obsidian. Puede **conectar un vault que ya tengas** sin tocarlo. Opcionalmente prepara el terreno para un grafo de código (Graphify, sin instalarlo) y para una **recuperación automática** del vault: búsqueda semántica local que añade a cada mensaje los trozos más relevantes. Nada pesado se instala sin tu visto bueno. |

Las dos primeras se complementan: con `workflow-orquestar`, varios agentes pueden construir o ejecutar varios procesos de `navegador-cdp` a la vez, cada uno en su propia pestaña de un mismo navegador.

## Requisitos

- **`navegador-cdp`**: Node.js 22 o superior y Chrome o Edge instalados.
- **`iniciar-memoria`**: Windows con PowerShell 5.1 o superior (el script de la plantilla, `nuevo-proyecto.ps1`, es de PowerShell). Para la recuperación automática opcional, además, el launcher `py` con Python 3.10 a 3.13 (probado con 3.12) y unos 0,6 GB de descarga la primera vez. Obsidian es opcional.
- **`workflow-orquestar`**: Python 3, git, y al menos un CLI trabajador instalado (`opencode`, `agy` o `codex`). Incluye `selftest.py`, que prueba el orquestador con un trabajador falso, sin gastar cuota ni llamar a ningún modelo.

## Instalación

Una skill es una carpeta con un `SKILL.md` (las instrucciones para el agente) y los scripts que ese texto indica ejecutar. No hay nada que compilar ni instalar con un gestor de paquetes.

```bash
git clone https://github.com/alejandro-xoxo/agent-skills.git
```

Después, según tu agente:

- **Si tu agente carga skills desde una carpeta** (por ejemplo, desde `~/.claude/skills/`), copia allí las carpetas de `skills/` que quieras:

  ```powershell
  # Windows (PowerShell)
  Copy-Item -Recurse agent-skills\skills\navegador-cdp $HOME\.claude\skills\
  ```
  ```bash
  # macOS / Linux
  cp -r agent-skills/skills/navegador-cdp ~/.claude/skills/
  ```

- **Si tu agente no carga skills**, deja la carpeta donde quieras y dile que lea el `SKILL.md`: por ejemplo, añade una línea a su archivo de instrucciones (como `AGENTS.md`):

  ```
  Para manejar el navegador, lee y sigue skills/navegador-cdp/SKILL.md
  ```

Copia la carpeta de `iniciar-memoria` **completa**, con su subcarpeta `plantilla/` dentro: la skill busca la plantilla junto a su `SKILL.md`. Si separas las dos, la skill te preguntará dónde está.

Puede que tengas que reiniciar la sesión del agente para que reconozca las skills nuevas.

## Uso rápido de `navegador-cdp`

Los scripts se pueden usar directamente, con cualquier agente (o a mano):

```bash
node skills/navegador-cdp/scripts/nav.mjs abrir --url https://example.com   # abre un navegador aparte
node skills/navegador-cdp/scripts/nav.mjs leer                              # lee el texto de la página
node skills/navegador-cdp/scripts/nav.mjs cerrar
node skills/navegador-cdp/scripts/nav.mjs ayuda                             # lista todos los comandos

node skills/navegador-cdp/scripts/proceso.mjs listar                        # procesos guardados
```

Un agente que lea `SKILL.md` sabe construir y reutilizar procesos. En los agentes que exponen las skills como comandos, se pide así (el nombre del comando puede variar según el agente):

```
/navegador-cdp crear descargar-extracto Entra en mi banco, descarga el extracto del mes y comprueba que el archivo existe
/navegador-cdp listar
/navegador-cdp ejecutar descargar-extracto mes=octubre
```

La idea central: **un proceso que no se ha visto funcionar de principio a fin no vale como memoria**. `guardar` rechaza cualquier borrador cuyo último intento no haya salido limpio, que no tenga al menos una verificación del resultado real, o cuyo script haya cambiado después de probarlo. El detalle está en [`SKILL.md`](skills/navegador-cdp/SKILL.md) y [`referencia.md`](skills/navegador-cdp/referencia.md).

## Uso rápido de `iniciar-memoria`

Con un agente que cargue la skill, basta con pedírselo ("inicia la memoria de este proyecto", "conéctalo a mi vault de Obsidian"). También puedes usar el script directamente, sin agente:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File skills\iniciar-memoria\plantilla\nuevo-proyecto.ps1 `
  -Destino "C:\ruta\a\mi-proyecto" -Nombre "Mi proyecto" -Descripcion "Qué hace" -ConGit
```

Crea `AGENTS.md`, `docs/` y un vault en `conocimiento/` **sin sobrescribir** lo que ya exista (`-Forzar` lo permite). Con `-Vault "<ruta>"` usa un vault de Obsidian que ya tengas en lugar de crear uno. `-ConGraphify` y `-ConRag` solo copian archivos y añaden líneas a `AGENTS.md` y `.gitignore`; activar el RAG es un paso aparte (`.rag\preparar.ps1`). Los detalles, los niveles de memoria y qué está comprobado están en [`plantilla/README.md`](skills/iniciar-memoria/plantilla/README.md).

## Uso rápido de `workflow-orquestar`

El agente que lidera escribe un script corto con las primitivas del orquestador (`agent`, `parallel`, `dag`, `auto_integrate`...) y lo lanza con `python wf.py script.py`. Mira [`SKILL.md`](skills/workflow-orquestar/SKILL.md) para las primitivas, los niveles de calidad (`tier`) y las reglas de seguridad. Para elegir qué CLI lidera, crea un `orquestador.json` en la carpeta de la skill con `{"orquestador": "codex"}` (valores: `claude`, `agy`, `opencode`, `codex`; por defecto `claude`).

## Estado y límites

Es una versión inicial (`0.1`). Conviene decir con claridad qué está comprobado:

- **Probado**: `navegador-cdp` en Windows 10 con Node 24, Edge y Chrome 156, con y sin ventana visible: el ciclo completo de procesos (fallar, corregir, guardar, reutilizar, reparar), incluido uno contra un sitio real, un perfil persistente que conserva la sesión, y hasta 20 ejecuciones a la vez en un mismo navegador. Hasta ahora lo ha manejado un solo agente.
- **Sin probar**: macOS y Linux (el código los contempla, pero no se han ejecutado); `navegador-cdp` con otros agentes distintos del anterior; iniciar sesión en sitios reales (siempre lo hace la persona a mano, y algunos sitios, como Google, pueden bloquearlo en un navegador con depuración remota); y la combinación de las dos skills con agentes reales de principio a fin.
- **`iniciar-memoria`**: la plantilla y el script se probaron en Windows 10 (PowerShell 5.1), incluido el uso con un vault externo y la preparación de Graphify y del RAG. La recuperación automática se activó y midió en un proyecto real con Python 3.12 (la mezcla de búsqueda por significado y por palabras acertó en los 3 primeros resultados el 95% de las veces con 20 preguntas escritas por quien conocía las notas; con otras notas el resultado puede ser distinto). **Sin probar:** macOS y Linux, otras versiones de Python, otros agentes distintos del anterior, y que el servidor local siga vivo durante semanas de uso real. Los ganchos de la recuperación automática (`.claude/settings.local.json`) están escritos para Claude Code; en otro agente hay que enganchar `rag.py hook` a mano o no usarla. Graphify no se instala nunca desde la skill.
- Las páginas dinámicas, los `iframe` y los diálogos del navegador (`alert`, `confirm`) tienen soporte limitado. Los detalles y las trampas conocidas están en `referencia.md`.

## Seguridad y uso responsable

- El navegador se abre con un **puerto de depuración local**: mientras la ventana existe, cualquier proceso de tu equipo puede controlarla y ver las sesiones que tenga abiertas. Ciérrala al terminar.
- **Nunca se piden ni se guardan contraseñas.** Cuando un sitio pide iniciar sesión, la persona lo hace a mano en la ventana. Un perfil con nombre guarda cookies en disco, fuera del repositorio.
- No pases datos sensibles como parámetros de un proceso. Las capturas de error pueden mostrar lo que había en la página.
- Los pasos irreversibles (enviar, pagar, borrar, publicar) se detienen hasta que la persona los confirme.
- `iniciar-memoria` no guarda contraseñas ni datos personales. Si conectas un vault con material de personas, `.rag/indice/` guarda el **texto completo** de las fuentes que indexes: está fuera de git y no debe compartirse. Los vectores se calculan en tu equipo; el contexto que se inyecta en un mensaje sí viaja al modelo como parte de la conversación.
- Automatiza solo sitios y cuentas que sean tuyos o para los que tengas permiso, y respeta los términos de uso de cada sitio. El autor no se hace responsable del uso que se haga de estas herramientas.

## Autor y licencia

Creado por [alejandro-xoxo](https://github.com/alejandro-xoxo). Licencia [MIT](LICENSE): puedes usar, copiar, modificar y distribuir este código, conservando el aviso de copyright. Mira también [`NOTICE.md`](NOTICE.md) para los créditos y las herramientas de terceros que estas skills usan pero no incluyen.

Los issues y las propuestas de mejora son bienvenidos.
