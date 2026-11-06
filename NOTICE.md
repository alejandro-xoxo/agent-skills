# Créditos y avisos

## Autoría

Las skills `navegador-cdp`, `workflow-orquestar` e `iniciar-memoria` (con su carpeta `plantilla/`) de este repositorio son obra de **alejandro-xoxo** (https://github.com/alejandro-xoxo) y se publican bajo una licencia propietaria, con todos los derechos reservados (ver `LICENSE`). Copyright (c) 2026 alejandro-xoxo. Las versiones anteriores a este cambio se publicaron bajo la licencia MIT.

## Herramientas de terceros que se usan pero no se incluyen

Estas skills funcionan junto a programas que **no forman parte de este repositorio** y que se rigen por sus propias licencias y condiciones de uso. Instálalos desde sus fuentes oficiales:

- **Node.js**, y los navegadores **Google Chrome** y **Microsoft Edge**, con su protocolo de depuración (Chrome DevTools Protocol), que usa `navegador-cdp`.
- **Python 3** y **git**, que usa `workflow-orquestar`.
- **PowerShell** (Windows), **Obsidian** (opcional; el vault son archivos de texto y no hace falta tenerlo instalado) y, solo si activas las funciones opcionales de `iniciar-memoria`, **Graphify** (Apache-2.0, solo se prepara el terreno: no se instala ni se redistribuye) y las bibliotecas de Python que instala `plantilla/extras/rag/preparar.ps1` en un entorno local del proyecto, sin incluirlas en este repositorio: `fastembed` (Apache-2.0), `numpy` (BSD-3-Clause y otras licencias permisivas), `onnxruntime` (MIT), `tokenizers` (Apache-2.0) y `huggingface_hub` (Apache-2.0).
- El modelo de embeddings `jinaai/jina-embeddings-v2-base-es` (Apache-2.0, según su ficha en Hugging Face), que se descarga la primera vez que se activa la recuperación automática y **no** se incluye aquí. Su licencia y condiciones son las de sus autores.
- Los CLI de agentes que `workflow-orquestar` puede lanzar como trabajadores: **OpenCode CLI** (`opencode`), **Antigravity CLI** (`agy`) y **Codex CLI** (`codex`). Su uso puede requerir una cuenta, tener cuota y costes, y sus propios términos.

## Skills relacionadas que no se incluyen

El texto de las skills menciona como **opcionales** modos de respuesta breve que ofrecen otras skills. No se incluyen ni se redistribuyen aquí; su autoría y su licencia son las de sus propios autores. El orquestador `wf.py` incorpora su propio texto de estilo breve y no necesita instalarlas.

## Contenido de terceros que no se incluye

`iniciar-memoria` se inspira en prácticas habituales de memoria para agentes (un `AGENTS.md` corto, un vault de Obsidian, skills con carga progresiva) y cita la documentación de Claude Code sobre memoria como referencia (<https://code.claude.com/docs/en/memory>). No se copia texto de esa documentación ni de ninguna guía de terceros. El vault de ejemplo que genera la plantilla está vacío: no contiene datos de ningún proyecto ni de ninguna persona.

## Marcas

Chrome, Edge, OpenCode, Antigravity, Codex, Claude Code, Obsidian, Graphify, Hugging Face y los demás nombres de productos mencionados pertenecen a sus respectivos titulares y se nombran solo para indicar compatibilidad.
