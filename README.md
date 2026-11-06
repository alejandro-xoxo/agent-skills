# agent-skills

Skills para agentes de IA que pueden ejecutar comandos de shell. **No dependen de un agente concreto**: son carpetas con instrucciones (`SKILL.md`) y scripts normales que cualquier agente puede leer y ejecutar. Con ellas, un agente puede manejar el navegador sin extensiones y repartir un trabajo grande entre varios agentes de línea de comandos.

*English summary: two agent-agnostic skills, each a folder with instructions (`SKILL.md`) and plain scripts. `navegador-cdp` drives Chrome or Edge over the DevTools Protocol with no extension, and keeps a memory of repeatable browser processes that are only saved after a clean, verified run. `workflow-orquestar` splits a big job across CLI agents (OpenCode, agy, Codex). The skill texts are written in Spanish.*

## Skills

| Skill | Para qué sirve |
|---|---|
| [`navegador-cdp`](skills/navegador-cdp) | Maneja Chrome o Edge **sin extensiones**, con scripts de Node sin dependencias. Sirve para tareas puntuales en una web (abrir, leer, hacer clic, escribir, subir archivos, capturas) y para **crear, guardar y reutilizar procesos repetitivos**: un proceso nuevo solo se guarda en la memoria cuando se ejecutó de principio a fin sin errores y con el resultado verificado. |
| [`workflow-orquestar`](skills/workflow-orquestar) | Orquesta un trabajo grande repartiéndolo entre agentes de CLI (OpenCode, agy y Codex), con grafos de dependencias, auto-corrección con tests, monitor visual en vivo, fusión de cambios y telemetría de tokens y costes. El agente que lidera se elige en `orquestador.json`. |

Las dos se complementan: con `workflow-orquestar`, varios agentes pueden construir o ejecutar varios procesos de `navegador-cdp` a la vez, cada uno en su propia pestaña de un mismo navegador.

## Requisitos

- **`navegador-cdp`**: Node.js 22 o superior y Chrome o Edge instalados.
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

## Uso rápido de `workflow-orquestar`

El agente que lidera escribe un script corto con las primitivas del orquestador (`agent`, `parallel`, `dag`, `auto_integrate`...) y lo lanza con `python wf.py script.py`. Mira [`SKILL.md`](skills/workflow-orquestar/SKILL.md) para las primitivas, los niveles de calidad (`tier`) y las reglas de seguridad. Para elegir qué CLI lidera, crea un `orquestador.json` en la carpeta de la skill con `{"orquestador": "codex"}` (valores: `claude`, `agy`, `opencode`, `codex`; por defecto `claude`).

## Estado y límites

Es una versión inicial (`0.1`). Conviene decir con claridad qué está comprobado:

- **Probado**: `navegador-cdp` en Windows 10 con Node 24, Edge y Chrome 156, con y sin ventana visible: el ciclo completo de procesos (fallar, corregir, guardar, reutilizar, reparar), incluido uno contra un sitio real, un perfil persistente que conserva la sesión, y hasta 20 ejecuciones a la vez en un mismo navegador. Hasta ahora lo ha manejado un solo agente.
- **Sin probar**: macOS y Linux (el código los contempla, pero no se han ejecutado); `navegador-cdp` con otros agentes distintos del anterior; iniciar sesión en sitios reales (siempre lo hace la persona a mano, y algunos sitios, como Google, pueden bloquearlo en un navegador con depuración remota); y la combinación de las dos skills con agentes reales de principio a fin.
- Las páginas dinámicas, los `iframe` y los diálogos del navegador (`alert`, `confirm`) tienen soporte limitado. Los detalles y las trampas conocidas están en `referencia.md`.

## Seguridad y uso responsable

- El navegador se abre con un **puerto de depuración local**: mientras la ventana existe, cualquier proceso de tu equipo puede controlarla y ver las sesiones que tenga abiertas. Ciérrala al terminar.
- **Nunca se piden ni se guardan contraseñas.** Cuando un sitio pide iniciar sesión, la persona lo hace a mano en la ventana. Un perfil con nombre guarda cookies en disco, fuera del repositorio.
- No pases datos sensibles como parámetros de un proceso. Las capturas de error pueden mostrar lo que había en la página.
- Los pasos irreversibles (enviar, pagar, borrar, publicar) se detienen hasta que la persona los confirme.
- Automatiza solo sitios y cuentas que sean tuyos o para los que tengas permiso, y respeta los términos de uso de cada sitio. El autor no se hace responsable del uso que se haga de estas herramientas.

## Autor y licencia

Creado por [alejandro-xoxo](https://github.com/alejandro-xoxo). Licencia [MIT](LICENSE): puedes usar, copiar, modificar y distribuir este código, conservando el aviso de copyright. Mira también [`NOTICE.md`](NOTICE.md) para los créditos y las herramientas de terceros que estas skills usan pero no incluyen.

Los issues y las propuestas de mejora son bienvenidos.
