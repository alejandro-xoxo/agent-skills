# Plantilla de memoria para proyectos con agentes

Una estructura igual para todos tus proyectos, para que el agente retome el contexto sin releer todo. Aplica prácticas habituales (un `AGENTS.md` corto que se carga siempre, un vault de Obsidian con enlaces, skills con carga progresiva) y se apoya en la documentación de Claude Code sobre memoria (<https://code.claude.com/docs/en/memory>).

**Idea central:** cada sesión empieza sin recuerdos. La memoria consiste en decidir qué se carga siempre (poco), qué se carga si hace falta y qué solo se consulta.

## Qué incluye

Esta carpeta (plantilla/) va dentro de la skill iniciar-memoria, junto a su SKILL.md.

```
plantilla/
├─ README.md
├─ nuevo-proyecto.ps1            crea o completa la estructura en un proyecto
├─ extras/mcp.memory.example.json  nivel 2, opcional (grafo de memoria por MCP)
├─ extras/graphify/              nivel 3, opcional: guía y .graphifyignore del grafo de código (no instala nada)
├─ extras/rag/                   nivel 4, opcional: recuperación automática del vault (RAG local); al crear el proyecto no instala nada
└─ base/                         lo que se copia al proyecto
   ├─ AGENTS.md                  reglas y mapa; se carga siempre (≤100 líneas)
   ├─ docs/ESTADO.md             dónde quedó el trabajo (se reescribe)
   ├─ docs/DECISIONS.md          registro corto de decisiones (se anexa)
   ├─ .claude/skills/
   │   ├─ memoria/               cómo consultar y escribir la memoria
   │   ├─ cerrar-tarea/          rutina de cierre
   │   └─ auditar-memoria/       limpieza periódica
   ├─ .gitignore
   └─ conocimiento/              vault de Obsidian (memoria de largo plazo)
      ├─ 00 Inicio · 00 Inbox · 01 Contexto · 02 Dominio y proceso
      ├─ 03 Lecciones · 04 Decisiones · 05 Fuentes
      └─ Plantillas (ADR, Lección)
```

## Las capas

| Capa | Dónde | Se carga |
|---|---|---|
| Reglas y mapa | `AGENTS.md` | Siempre |
| Estado vivo | `docs/ESTADO.md` | Al empezar (lo pide `AGENTS.md`) |
| Procedimientos | `.claude/skills/*` | Nombre y descripción siempre; el cuerpo, bajo demanda |
| Largo plazo | `conocimiento/` | Solo lo que la tarea necesite, entrando por `00 Inicio` |
| Material crudo | `conocimiento/05 Fuentes/` | Nunca completo; con grep |
| Consulta por grafo (opcional) | MCP `memory` | Cuando se pregunta |
| Grafo de código (opcional) | Graphify, preparado en `docs/GRAFO.md` | Cuando el proyecto tenga bastante código |
| Recuperación automática (opcional) | RAG local en `.rag/` | En cada mensaje, si trata del vault |

Equivalencia con una organización habitual de segundo cerebro en cuatro carpetas: `00-inbox` → `00 Inbox`; `01-proyectos` → el vault ya es de un proyecto; `02-buenas-practicas` → `03 Lecciones` (y un vault global tuyo, ver más abajo); `03-decisiones` → `04 Decisiones`.

## Cómo usarla

Proyecto nuevo o existente (no sobrescribe lo que ya exista):

```powershell
powershell -ExecutionPolicy Bypass -File "<carpeta de la plantilla>\nuevo-proyecto.ps1" `
  -Destino "<carpeta del proyecto>" `
  -Nombre "Mi Proyecto" -Descripcion "Qué es, en una línea" -Stack "Python y FastAPI" -ConGit
```

Opciones: `-ConGit` hace `git init` sin commit; `-ConMcpMemoria` crea un `.mcp.json` con el servidor de memoria; `-ConGraphify` deja preparado el grafo de código (ver "Nivel 3 opcional"); `-SoloGraphify` hace solo eso en un proyecto que ya existe, sin tocar nada más; `-ConRag` y `-SoloRag` dejan preparada la recuperación automática (ver "Nivel 4 opcional"); `-Forzar` sobrescribe. Para usar un vault de Obsidian que ya tienes, ver la sección siguiente.

## Conectar un vault de Obsidian propio
Por defecto el vault es `conocimiento/` dentro del proyecto. Para usar otro, la **única fuente de verdad** es el bloque `## Memoria` de `AGENTS.md`: ahí van la ruta del vault y las carpetas (índice, inbox, lecciones, decisiones, fuentes). Las tres skills leen ese bloque, así que cambiarlo basta.

| Situación | Cómo |
|---|---|
| Vault nuevo o vacío | `-Vault "D:\Obsidian\MiVault"` (añade `-CrearVault` si la carpeta aún no existe) |
| Vault compartido entre proyectos | `-Vault "D:\Obsidian\Cerebro" -Carpeta "Mi Proyecto"`: la estructura va en una subcarpeta y no se anida otro `.obsidian` |
| Solo crear la estructura en el vault, sin tocar el proyecto | añade `-SoloVault` |
| Vault que ya tiene notas con otra estructura | No se crean carpetas: se edita a mano el bloque `## Memoria` con las carpetas reales |

El script nunca sobrescribe notas existentes. En un vault compartido, las notas de la plantilla (Inbox, Glosario, Decisiones…) se llaman igual en cada proyecto y Obsidian puede resolver un enlace a la nota de otro; usa nombres propios.

### Skill global `iniciar-memoria`
Hace todo lo anterior conversando. Es el `SKILL.md` de la carpeta superior (`iniciar-memoria/`). Para instalarla, copia esa carpeta completa, con `plantilla/` dentro, a la carpeta de skills de tu agente (por ejemplo `~/.claude/skills/`) y reinicia la sesión. Al empezar un proyecto detecta si falta la memoria y aplica la plantilla; si ya existe, carga el estado y el índice; y si le dices "conéctalo a mi vault" y la ruta, valida el vault, consigue acceso a esa carpeta, elige el modo y actualiza el bloque `## Memoria`. Encuentra la plantilla por su ruta relativa (`plantilla/` junto al `SKILL.md`): si separas las dos carpetas, la skill te preguntará dónde está.

La **carga automática en cada sesión** no depende de la skill sino de `AGENTS.md` ("Empieza aquí"). Una skill se activa cuando el agente cree que encaja con su descripción, no en cada arranque.

## Por qué no usa RAG ni grafo por defecto
Es una decisión de tamaño y de confianza, no una carencia.

- **RAG (búsqueda por vectores).** Parte las notas en trozos y trae los parecidos a la pregunta. Con decenas de notas es peor que lo que ya hay: los trozos pierden el contexto (el porqué de una decisión queda separado de su fecha y su fuente), necesita un índice que se desactualiza cada vez que cambia una nota, y no se puede auditar por qué trajo un trozo y no otro. Aquí el agente entra por un índice, sigue `[[enlaces]]` y busca con grep: es predecible y verificable.
- **Grafo.** El propio vault ya es un grafo: cada `[[wikilink]]` es una relación y Obsidian lo dibuja. Un grafo aparte (entidades, relaciones, observaciones) duplica lo que dicen las notas y se desordena sin un esquema estricto; dos fuentes de verdad acaban contradiciéndose.
- **Criterio de partida:** empezar por lo más simple y no montar infraestructura pesada el primer día; el RAG clásico rara vez es la opción más sencilla o eficiente para un proyecto pequeño.

**Sí hay un grafo, pero opcional:** `-ConMcpMemoria` añade el servidor de memoria como acelerador de consulta. Las notas mandan.

**Cuándo sí valdría la pena añadirlos:**
- Un grafo de código (por ejemplo `codebase-memory-mcp`, que no he verificado) cuando el repositorio sea grande y el agente gaste mucho leyendo archivos para saber quién llama a qué.
- RAG o búsqueda semántica sobre las **fuentes crudas** cuando sean muchas o enormes (cientos de documentos, conversaciones de miles de líneas), manteniendo las notas curadas como capa principal. Está disponible como opción (`-ConRag`, ver "Nivel 4 opcional").
- Un grafo temporal (Zep o Graphiti) en agentes autónomos de producción, por ejemplo en n8n, donde los datos cambian solos y hay que invalidar los viejos.
- Señal práctica para dar el paso: cuando el grep devuelve demasiados resultados irrelevantes o el índice ya no cabe en una pantalla.

## Primeros 10 minutos en un proyecto
1. Completa en `AGENTS.md` los comandos y de 3 a 7 reglas de oro propias.
2. Rellena `conocimiento/01 Contexto/Proyecto y objetivo.md`.
3. Abre la carpeta `conocimiento` como bóveda en Obsidian.
4. Anota en `05 Fuentes/Fuentes.md` el material crudo que ya exista.
5. Trabaja; al terminar una tarea importante pide la skill `cerrar-tarea`.

## AGENTS.md y Claude Code
Según la documentación de Claude Code, lee `AGENTS.md` directamente (versión 2.1.277 o posterior) **solo si no hay ningún `CLAUDE.md` ni `CLAUDE.local.md` en la carpeta del proyecto ni en las superiores**. Si existe alguno de los dos, lee esos y deja `AGENTS.md` de lado. Por eso la plantilla **no incluye `CLAUDE.md`**.

- Tu `~/.claude/CLAUDE.md` personal y las reglas en `.claude/rules/` no cuentan: siguen cargándose junto a `AGENTS.md`.
- Si en algún entorno no lo lee (versión vieja, o `/plugin` desactivó el soporte), crea un `CLAUDE.md` con una sola línea: `@AGENTS.md`.
- La documentación recomienda menos de 200 líneas; la plantilla se queda en 100 para dejar margen.

## Skills
`.claude/skills/<nombre>/SKILL.md` es el formato de Claude Code: del encabezado `name` y `description` se ve siempre, y el cuerpo se carga cuando la tarea coincide. Otros agentes no tienen por qué cargarlas solos; por eso `AGENTS.md` las nombra y son Markdown normal que cualquier agente puede leer.

## Nivel 2 opcional: grafo de memoria
`-ConMcpMemoria` genera un `.mcp.json` con `@modelcontextprotocol/server-memory` (entidades, relaciones y observaciones en un `.jsonl` local en `.memory/`). Claude Code pedirá aprobación la primera vez. Úsalo como acelerador de consulta, no como fuente de verdad: las notas de `conocimiento/` mandan.

Otra opción que se menciona en la comunidad es `codebase-memory-mcp`, para mapear código. No lo incluí: no lo he verificado y solo aporta en proyectos con mucho código.

## Nivel 3 opcional: grafo de código (Graphify)
La idea es **dejar el terreno listo** para cuando el proyecto crezca, sin pagar su coste antes de tiempo. `-ConGraphify` (o `-SoloGraphify` en un proyecto que ya existe) deja:

- `.graphifyignore`: qué no debe leer Graphify. Excluye por defecto las fuentes con datos personales, el vault, la memoria del agente, las dependencias y las credenciales.
- `docs/GRAFO.md`: qué es, cuándo activarlo, cómo hacerlo paso a paso, qué no hacer y cómo quitarlo.
- Una línea en el mapa de `AGENTS.md` que apunta a esa guía, y `graphify-out/` en el `.gitignore`.

**No instala ni ejecuta nada.** Activarlo es una decisión posterior, cuando el repositorio tenga bastante código y el agente gaste mucho leyendo archivos.

Cuidados que recoge `docs/GRAFO.md`, porque chocan con esta plantilla:
- `graphify claude install` escribe en `CLAUDE.md`, y con ese archivo Claude Code deja de leer `AGENTS.md` (ver la sección siguiente). No lo uses.
- Sus ganchos en modo estricto pueden denegar lecturas de archivos, incluidas las del vault.
- Los documentos, PDFs e imágenes que indexa se envían al modelo del asistente; el código se procesa en local. Por eso el `.graphifyignore` excluye las fuentes crudas.
- Las cifras de ahorro de tokens son del autor de la herramienta y conviene medirlas en tu proyecto.

La herramienta es de terceros ([Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify), Apache-2.0): aquí no se incluye su código.

## Nivel 4 opcional: recuperación automática del vault (RAG local)
Para cuando las fuentes crudas son grandes (por ejemplo, una conversación de miles de líneas) y `grep` no basta: un gancho de Claude Code añade a cada mensaje los trozos más relevantes del vault y de `docs/`, con archivo y líneas, usando una búsqueda por significado mezclada con palabras exactas. Todo corre en el equipo, y las notas curadas pesan más que el material crudo.

Se activa en dos pasos, para que crear un proyecto nunca instale ni descargue nada sin que lo decidas:
1. `-ConRag` (o `-SoloRag` en un proyecto que ya existe) copia `.rag/` (el motor `rag.py`, el script `preparar.ps1`, una guía y un ejemplo de evaluación), añade una línea a `AGENTS.md` e ignora `.rag/` en git.
2. `.rag\preparar.ps1` hace lo pesado: entorno de Python (3.10 a 3.13), `fastembed`, índice, ganchos en `.claude/settings.local.json` (mezcla con lo que haya, con copia de seguridad) y servidor local. La primera vez descarga unos 0,6 GB de modelo, que se comparte entre proyectos.

Lo que hay que saber:
- Es opcional y tiene costes: unos 700 MB de memoria mientras el servidor está activo, entre 500 y 900 tokens más por cada mensaje relacionado, y `.rag/indice/` guarda el texto completo de las fuentes (no debe compartirse).
- Solo inyecta si el mensaje trata del vault (umbral de similitud 0,50). Es preferible no dar contexto que darlo equivocado.
- Mejora qué trozos le llegan al agente, no garantiza que acierte: cada trozo trae archivo y líneas para verificarlo.
- Se mide con `rag.py evaluar` y preguntas propias (`evaluacion.ejemplo.json`). En el proyecto donde se probó, con 20 preguntas escritas por quien conocía las notas, la mezcla acertó en los 3 primeros el 95% de las veces y las palabras solas el 70%.
- Windows y Python de la 3.10 a la 3.13 (probado con 3.12). El detalle está en `.rag/LEEME.md`.

## Tu capa global (no la toca el script)
- `~/.claude/CLAUDE.md` y `~/.claude/rules/` para preferencias que valen en todos los proyectos.
- Un vault tuyo de buenas prácticas entre proyectos (un "segundo cerebro"). Cada `AGENTS.md` puede apuntar a él con una línea.

## Mantenimiento
- La memoria vieja o contradictoria es peor que ninguna: usa la skill `auditar-memoria` de vez en cuando o cuando `AGENTS.md` pase de 100 líneas.
- Antes de actuar sobre un dato guardado, compruébalo en la fuente.
- El auto-memory de Claude Code (notas que escribe solo) convive con esto: lo personal y por repositorio va allí; lo compartido y versionado, aquí.

## Qué se probó y qué no
**Probado:**
- El script en carpetas temporales: proyecto normal (19 archivos, marcadores rellenos, `{{date}}` de Obsidian intacto, sin enlaces rotos, sin `CLAUDE.md`), segunda ejecución sin sobrescribir, vault externo vacío, vault compartido con `-Carpeta` (la nota ajena y el `.obsidian` existente quedan intactos, sin `.obsidian` anidado), `-SoloVault` (no crea el proyecto) y los errores esperados (vault inexistente sin `-CrearVault`, `-SoloVault` sin `-Vault`).
- El servidor de memoria arrancando con la configuración generada, con sus 9 herramientas y escribiendo su archivo.
- `-ConGraphify` y `-SoloGraphify` (en carpetas temporales): proyecto nuevo con la opción, repetición sin duplicar nada, sin la opción (no aparece nada de Graphify), proyecto existente con un `AGENTS.md` propio en CRLF (se conservan los saltos de línea y se añade una sección), carpeta sin `AGENTS.md`, `.gitignore` ni git (solo crea los dos archivos de guía), y los errores esperados (destino inexistente y combinaciones no permitidas), sin crear `conocimiento/`, `.claude/` ni `CLAUDE.md`.
- `-ConRag` y `-SoloRag` (en carpetas temporales): proyecto nuevo con la opción (solo crea archivos: sin entorno, sin modelo y sin `CLAUDE.md`), repetición sin duplicar, sin la opción, proyecto existente con `AGENTS.md` propio en CRLF, combinación con `-SoloGraphify`, errores esperados, y el registro de ganchos sobre una configuración existente (conserva permisos, modelo y otros ganchos, hace copia de seguridad, no duplica y no toca un JSON inválido ni de forma inesperada). Además, `preparar.ps1` de principio a fin en un proyecto nuevo: 61 s con el modelo ya en la caché compartida, sin volver a descargarlo.

**No probado:**
- La skill `iniciar-memoria` de punta a punta en una conversación real.
- Cargar un proyecto generado en una sesión nueva de Claude Code (aprobación del `.mcp.json`, disparo de las skills).
- Abrir en Obsidian el vault generado.
- Conectar un vault que ya tiene su propia estructura (el modo "Existente" depende del criterio del agente, no del script).
- El uso con agentes que no sean Claude Code.
- Graphify en sí: no se instaló ni se ejecutó. `docs/GRAFO.md` se basa en su README (y en un archivo de referencia de su instalación para Claude), así que sus comandos hay que confirmarlos con `graphify --help` al activarlo.
- La recuperación automática: `preparar.ps1` con una descarga del modelo desde cero (la caché compartida ya existía) y con Pythons distintos de 3.12; que el servidor siga vivo entre mensajes reales a largo plazo; macOS y Linux.
