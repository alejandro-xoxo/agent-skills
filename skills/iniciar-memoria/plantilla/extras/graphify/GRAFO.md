# Grafo de código con Graphify: cómo activarlo cuando {{NOMBRE}} crezca

**Estado: preparado, no instalado.** Este proyecto solo trae la configuración y esta guía. Nada de Graphify está instalado ni se ha ejecutado.

## Qué es y qué no es
[Graphify](https://github.com/Graphify-Labs/graphify) (licencia Apache-2.0) convierte un proyecto en un grafo de conocimiento que el agente consulta en vez de leer o buscar con `grep` en muchos archivos: quién llama a qué, qué conecta con qué, cuáles son los conceptos centrales.

- **Sí** sirve para orientarse en un repositorio de código grande y gastar menos tokens leyendo archivos.
- **No** sustituye a esta memoria. No guarda decisiones, lecciones ni el estado del trabajo: eso sigue en `docs/ESTADO.md`, `docs/DECISIONS.md` y el vault. El grafo dice *qué hay conectado*; la memoria dice *por qué y en qué punto estamos*.

## Cuándo activarlo
No antes de que haga falta. Señales de que ya toca:
- El repositorio tiene bastantes módulos y el agente gasta mucho leyendo archivos para saber quién usa qué.
- `grep` devuelve demasiados resultados irrelevantes.
- Se hacen preguntas del tipo "¿qué se rompe si cambio esta función?" y cuesta responderlas.

Con un repositorio pequeño no aporta: el agente ya lo recorre entero.

## Cómo activarlo (cuando toque)
Los comandos salen del README de Graphify y **no se han probado aquí**. Confírmalos con `graphify --help` y en https://docs.graphify.com.

1. **Requisitos:** Python 3.10 o superior, y `uv` o `pipx`.
2. **Instalar:** `uv tool install graphifyy` (con doble "y"). Comprueba en el repositorio oficial que ese es el paquete correcto antes de instalar.
3. **Revisar `.graphifyignore`** (ya está en la raíz del proyecto). Excluye las fuentes con datos personales.
4. **Primer grafo solo de código, sin modelo ni red:** `graphify extract . --code-only`. El código se analiza en local con tree-sitter.
5. **Consultar:** `graphify query "<pregunta>"`, `graphify path "A" "B"`, `graphify explain "X"`.
6. **Mantenerlo:** `graphify update .` tras cambiar código (solo analiza lo que cambió).
7. **Que el agente lo use:** añade a `AGENTS.md` una línea: "Para preguntas sobre el código, consulta `graphify query` antes de buscar con grep". Es más simple y controlable que el modo "siempre activo".

## Qué no hacer en este proyecto
- **No ejecutes `graphify claude install`.** Escribe una sección en `CLAUDE.md`, y con ese archivo presente Claude Code deja de leer `AGENTS.md`, que es donde está la memoria. Si ya lo hiciste, añade `@AGENTS.md` a `CLAUDE.md` o quita la sección con `graphify claude uninstall`.
- **No actives el modo estricto de los ganchos (`--strict`).** Puede denegar lecturas y búsquedas de archivos, incluidas las del vault.
- **No indexes fuentes con datos personales.** Código y audio se procesan en local, pero documentos, PDFs e imágenes se envían al modelo del asistente. Para evitarlo, mantén `.graphifyignore` al día o usa `--code-only`.
- **No te fíes de las cifras de ahorro** ("80% menos tokens") hasta medirlas en este proyecto: son del autor de la herramienta.
- Si te ofrecen *Graphify Cloud*, es un servicio de pago aparte; no hace falta para nada de lo anterior.

## Qué deja en tu equipo
El grafo se guarda en `graphify-out/` (`graph.json`, `GRAPH_REPORT.md`, `graph.html`), que `.gitignore` ya ignora porque se regenera. Según su README, registra tus preguntas en `~/.cache/graphify-queries.log`, y no envía telemetría.

## Quitarlo
`graphify uninstall` (añade `--purge` para borrar también `graphify-out/`). Luego quita la línea que añadiste a `AGENTS.md`.
