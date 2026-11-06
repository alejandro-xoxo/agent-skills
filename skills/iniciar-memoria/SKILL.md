---
name: iniciar-memoria
description: Inicia o carga la memoria de un proyecto y, si el usuario lo pide, la conecta con un vault de Obsidian que él indique. Úsala al empezar a trabajar en un proyecto sin memoria configurada, cuando el usuario diga "inicia la memoria", "carga el contexto del proyecto", "conecta con Obsidian" o "conéctalo a mi vault", o cuando quiera cambiar de vault. Aplica la plantilla de memoria si falta; si ya existe, carga el estado y el índice. También deja preparado, sin instalar nada, el grafo de código (Graphify) cuando el usuario quiera dejar listo el terreno para cuando el proyecto crezca. También puede preparar y activar la recuperación automática del vault (búsqueda semántica local que añade a cada mensaje los trozos relevantes).
---

# Iniciar la memoria y conectar Obsidian

**Plantilla:** la carpeta `plantilla/` que está junto a este `SKILL.md` (script `nuevo-proyecto.ps1`, carpeta `base/`, `README.md`). Si no la encuentras ahí, díselo al usuario y pregunta dónde está; no la recrees de memoria.

**Qué hace esta skill y qué no:** la carga automática en cada sesión la hace `AGENTS.md` (sección "Empieza aquí"). Esta skill sirve para **configurar** un proyecto, para **cargar la memoria a petición** y para **conectar un vault de Obsidian**. Obsidian no necesita estar abierto ni tener plugins: el vault son archivos y se leen y escriben directo.

## Paso 1: ¿en qué estado está el proyecto?
En el directorio de trabajo, mira:
- ¿`AGENTS.md` con un bloque `## Memoria`?
- ¿`docs/ESTADO.md`?
- ¿Hay `CLAUDE.md` o `CLAUDE.local.md`? Si los hay, Claude Code **no lee** `AGENTS.md`.
- ¿Hay git y archivos propios del proyecto?

Clasifica: **A** sin memoria, **B** con memoria, **C** parcial.

## A: sin memoria, aplicar la plantilla
1. Pregunta de una vez lo que falte (no repitas lo que el usuario ya dijo): nombre del proyecto, descripción en una línea, stack (opcional), si quiere `git init`, y si el vault va **dentro del proyecto** (por defecto, `conocimiento/`) o es **uno existente de Obsidian** (entonces pide la ruta y sigue la sección "Conectar con un vault"). Si el proyecto va a tener bastante código, ofrece también dejar **preparado el grafo de código** (Graphify): es opcional y solo deja archivos de guía, no instala nada. Si el vault tendrá fuentes grandes (conversaciones de miles de líneas, muchos documentos), ofrece además la **recuperación automática** (búsqueda semántica local): al crear el proyecto solo deja archivos preparados.
2. Si el proyecto ya tiene `AGENTS.md` propio, no lo sustituyas. Si tiene `CLAUDE.md`, explica que oculta `AGENTS.md` y ofrece: (a) añadir `@AGENTS.md` dentro de `CLAUDE.md`, o (b) migrar su contenido. Haz solo lo que elija.
3. Ejecuta el script (no sobrescribe lo que exista y lo avisa):
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<carpeta de esta skill>\plantilla\nuevo-proyecto.ps1" -Destino "<ruta del proyecto>" -Nombre "<nombre>" -Descripcion "<descripción>" [-Stack "<stack>"] [-ConGit] [-ConGraphify] [-ConRag] [-Vault "<ruta>" [-Carpeta "<nombre>"]]
```
4. Comprueba: `AGENTS.md` sin marcadores `{{...}}`, `docs/ESTADO.md` creado y el vault accesible.
5. Resume qué se creó y qué falta completar: comandos y reglas de oro en `AGENTS.md`, y la nota "Proyecto y objetivo" del vault. Si pidió el grafo de código, di que quedó preparado y que se activa más adelante siguiendo `docs/GRAFO.md`. Si pidió la recuperación automática, di que quedó preparada y que activarla es un paso aparte (sección "Recuperación automática del vault").

## B: con memoria, cargarla
1. Lee `docs/ESTADO.md` y el bloque `## Memoria` de `AGENTS.md`.
2. Comprueba que el vault existe y puedes leerlo (si está fuera del directorio de trabajo, mira "Acceso" más abajo). Lee su índice.
3. Resume al usuario en 5 líneas como máximo: dónde quedó, siguiente paso, bloqueos o dudas y qué está sin verificar.
4. No leas más. El resto se consulta con la skill `memoria` cuando la tarea lo pida. Verifica contra la fuente lo que vayas a usar.
5. Si existe `docs/GRAFO.md` y el proyecto ya tiene bastante código, menciona **una sola vez** que ya puede activarse el grafo de código; no lo actives sin que el usuario lo pida. Si no existe `docs/GRAFO.md` y el proyecto ya tiene bastante código, ofrécelo (sección "Preparar el grafo de código").
6. Si el vault tiene fuentes grandes y no existe `.rag/`, ofrece la recuperación automática. Si existe `.rag/` pero no `.rag/.venv`, está preparada y sin activar: dilo una sola vez y no la actives sin que el usuario lo pida.

## C: parcial
Completa lo que falte con el mismo script (no sobrescribe). Di qué añadiste.

## Preparar el grafo de código (opcional)
Úsalo cuando el usuario quiera dejar listo el terreno para cuando el proyecto crezca, o cuando haya bastante código y no exista `docs/GRAFO.md`. **Solo deja preparado: no instala ni ejecuta Graphify.**
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<carpeta de esta skill>\plantilla\nuevo-proyecto.ps1" -Destino "<ruta del proyecto>" -Nombre "<nombre>" -SoloGraphify
```
Copia `.graphifyignore` y `docs/GRAFO.md`, añade una línea al mapa de `AGENTS.md` e ignora `graphify-out/` en `.gitignore`. No crea el vault ni `conocimiento/`, ni toca git. Revisa con el usuario `.graphifyignore`, sobre todo que excluya las fuentes con datos personales. Para activarlo de verdad, sigue `docs/GRAFO.md`, y solo si el usuario lo pide.

## Recuperación automática del vault (opcional)
Úsala cuando el usuario quiera que el agente reciba solo, en cada mensaje, los trozos más relevantes del vault y de `docs/` (con archivo y líneas), o cuando las fuentes crudas sean grandes. Son dos pasos:

1. **Preparar (rápido, no instala nada).** En un proyecto nuevo basta `-ConRag` en el comando de la sección A. En uno que ya existe:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<carpeta de esta skill>\plantilla\nuevo-proyecto.ps1" -Destino "<ruta del proyecto>" -Nombre "<nombre>" -SoloRag
```
Copia `.rag/` (motor, script de activación, guía y ejemplo de evaluación), añade una línea a `AGENTS.md` e ignora `.rag/` en git. No crea el vault ni `conocimiento/`, ni toca git.

2. **Activar (pesado: solo con el visto bueno del usuario).** Antes de ejecutarlo, explícale qué hará: crea un entorno de Python dentro de `.rag/`, instala `fastembed`, descarga el modelo la primera vez (unos 0,6 GB, que comparten todos los proyectos), tarda varios minutos, deja un servidor local en segundo plano y escribe dos ganchos en `.claude/settings.local.json` (con copia de seguridad si ya existía). Si acepta:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "<ruta del proyecto>\.rag\preparar.ps1"
```
Necesita Windows, el launcher `py` y Python de la 3.10 a la 3.13. Si falla por el Python, dilo tal cual y no improvises alternativas.

Al terminar, dile que abra `/hooks` una vez o reinicie la sesión para que se carguen los ganchos, y cuéntale lo que cuesta: unos 500 a 900 tokens más por cada mensaje relacionado con el vault; `.rag/indice/` guarda el texto completo de las fuentes (no debe compartirse); se apaga con la variable `RAG_DESACTIVAR=1`. `.rag/LEEME.md` explica cómo medir su calidad con preguntas propias.

## Conectar con un vault de Obsidian
Cuando el usuario diga "conéctalo a mi vault", dé una ruta o quiera otro vault:

1. **Ruta.** Pídela si no la dio. En la app de escritorio puedes abrir un selector de carpeta con la herramienta `request_directory` (sin ruta). No adivines rutas.
2. **Valida.** ¿Existe? Es un vault de Obsidian si contiene `.obsidian/`. Si existe sin `.obsidian`, pregunta si es un vault nuevo (Obsidian lo creará al abrirlo).
3. **Acceso.** Si está fuera del directorio de trabajo, consigue acceso: `request_directory` con la ruta (app de escritorio) o, en terminal, pide al usuario que ejecute `/add-dir <ruta>`. Sin acceso, para.
4. **Mira qué hay** (carpetas del primer nivel y cuántas notas `.md`) y elige el modo. Si hay duda, haz **una sola** pregunta.

| El vault... | Modo | Qué haces |
|---|---|---|
| Está vacío o es nuevo | Dedicado | Crea la estructura con `nuevo-proyecto.ps1 -SoloVault -Vault "<ruta>" -Destino "<proyecto>" -Nombre "<nombre>"` |
| Es un "segundo cerebro" con notas de otros temas | Compartido | Igual, añadiendo `-Carpeta "<nombre del proyecto>"`. Avisa: los nombres de nota repetidos (Inbox, Glosario…) pueden confundir los enlaces entre proyectos |
| Ya tiene las notas de este proyecto con otra estructura | Existente | **No crees carpetas.** Lista las carpetas e identifica índice, inbox, lecciones, decisiones y fuentes por su nombre (Inicio/Index/MOC, Inbox/Bandeja, Lecciones, Decisiones/ADR, Fuentes/Sources). Confirma el mapa con el usuario si algo es ambiguo. Lo que no exista, déjalo sin ruta y dilo |

5. **Actualiza el bloque `## Memoria` de `AGENTS.md`.** Edita solo ese bloque: la línea `Vault de Obsidian:` con la ruta (barras `/`) y la línea de rutas relativas con el mapa real. En modo Compartido la ruta incluye la subcarpeta.
6. **Registra.** Añade 5 líneas a `docs/DECISIONS.md` (qué vault, modo y por qué) y menciónalo en `docs/ESTADO.md`.
7. **Comprueba.** Lee el índice desde la ruta nueva. Si creaste estructura, corre la comprobación de enlaces de la skill `auditar-memoria`.
8. **Dile al usuario** cómo abrirlo: en Obsidian, **Abrir carpeta como bóveda** y elegir la carpeta del **vault** (no la del proyecto). No hace falta que Obsidian esté abierto para que tú leas y escribas.

### Cambiar o quitar el vault
Cambia solo la línea del vault y el mapa en `AGENTS.md`. No muevas ni borres notas del vault anterior. Anótalo en `docs/DECISIONS.md`.

## Reglas
- Nunca sobrescribas ni borres notas del usuario. Si el script dice "ya existe, se omite", está bien.
- No crees `CLAUDE.md` ni `CLAUDE.local.md`.
- No hagas `git commit`. `git init` solo si el usuario lo pidió.
- No instales plugins de Obsidian ni servidores MCP salvo que lo pida; no hacen falta.
- No instales ni ejecutes Graphify: esta skill solo deja el terreno preparado. Nunca ejecutes `graphify claude install` (escribe `CLAUDE.md`).
- No actives la recuperación automática (`.rag\preparar.ps1`) sin el visto bueno del usuario: descarga cientos de MB y deja un proceso en segundo plano. No edites a mano los ganchos de `.claude/settings.local.json`: los registra ese script, que mezcla sin pisar lo que ya haya.
- No pongas datos personales ni secretos en las notas.
- Si algo no cuadra (ruta inexistente, vault sin acceso), para y dilo.
