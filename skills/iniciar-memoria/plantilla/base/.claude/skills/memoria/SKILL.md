---
name: memoria
description: Consulta y escribe la memoria del proyecto (el vault de Obsidian y la carpeta docs/). Úsala cuando necesites contexto previo, decisiones pasadas, lecciones o convenciones del proyecto, o cuando haya algo nuevo que valga la pena recordar para próximas sesiones.
---

# Memoria del proyecto

> **Requisito:** el proyecto debe tener el bloque `## Memoria` en `AGENTS.md`. Si no lo tiene, la memoria no está configurada: usa antes la skill `iniciar-memoria` (o díselo al usuario) y no sigas.

**Rutas:** lee el bloque `## Memoria` de `AGENTS.md`. Ahí están la ruta del vault y las carpetas (índice, inbox, lecciones, decisiones, fuentes). Abajo se llaman `<vault>`, `<índice>`, `<inbox>`, `<lecciones>`, `<decisiones>` y `<fuentes>`. Si el vault está fuera del directorio de trabajo y no puedes leerlo, pide acceso al usuario antes de seguir.

La memoria está en capas. Entra por la más barata y baja solo si hace falta.

## Para consultar (en este orden)
1. `docs/ESTADO.md`: dónde quedó el trabajo.
2. `<índice>`: sigue solo los `[[enlaces]]` que la tarea necesite.
3. Para buscar algo concreto: `grep -ril "palabra" "<vault>" --include=*.md` y abre solo las notas que salgan.
4. `<fuentes>` es material crudo. Nunca lo leas completo; busca con grep y lee el fragmento.
5. Antes de usar un dato guardado (ruta, función, cifra, estado), compruébalo en la fuente. Si ya no es cierto, corrige la nota.

## Para escribir
Primero busca si ya existe una nota sobre eso (`grep`). Si existe, actualízala; no dupliques.

| Qué es | Dónde | Formato |
|---|---|---|
| Idea suelta o duda | `<inbox>` | Una línea o un párrafo con fecha |
| Cómo funciona el dominio o el proceso | el vault, en su carpeta de dominio | Una idea por nota |
| Lección aprendida | `<lecciones>` | Plantilla `Leccion.md` del vault, si existe |
| Decisión con razones | `<decisiones>` | Plantilla `ADR.md` del vault, numerada `ADR-NNNN Título.md` |
| Material crudo | `<fuentes>` | Copia sin editar + una línea en su índice |

Reglas de escritura:
- Frontmatter con `tags` y `created`. En decisiones, también `status` (propuesta, aceptada, reemplazada).
- Una idea por nota. Título claro. Nombres de archivo sin `: ? " < > | / \`.
- Guarda el **porqué** y la **fuente** con su fecha, no solo el hecho.
- Enlaza con `[[wikilinks]]` y añade la nota nueva al índice que corresponda.
- Escribe en el idioma del proyecto y sin nombres de personas ni datos personales salvo que sea imprescindible.
- Nunca borres ni sobrescribas notas existentes sin preguntar.

## Qué NO guardar
- Lo que ya está en el código o en git.
- Secretos, claves o contraseñas.
- Datos personales.
- Estados efímeros de una sola sesión (van a `docs/ESTADO.md`).

## Decisiones
Si la decisión cambia cómo se construye algo, crea una nota ADR y añade 5 líneas a `docs/DECISIONS.md` con el enlace.
