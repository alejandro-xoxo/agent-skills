---
name: cerrar-tarea
description: Rutina de cierre al terminar una tarea importante o antes de acabar la sesión. Reescribe docs/ESTADO.md, anexa 5 líneas a docs/DECISIONS.md y guarda decisiones y lecciones en el vault. Úsala cuando se complete un bloque de trabajo, se tome una decisión técnica o el usuario diga que cierra la sesión.
---

# Cerrar una tarea

> **Requisito:** el proyecto debe tener el bloque `## Memoria` en `AGENTS.md` y el archivo `docs/ESTADO.md`. Si falta alguno, la memoria no está configurada: usa antes la skill `iniciar-memoria` (o díselo al usuario) y no sigas.

Las rutas del vault (`<vault>`, `<decisiones>`, `<lecciones>`, `<índice>`) están en el bloque `## Memoria` de `AGENTS.md`. Haz estos pasos en orden. Si algo no aplica, sáltalo y dilo.

1. **Revisa qué cambió.** Si hay git, mira `git status` y `git diff --stat`. Si no, repasa los archivos que tocaste.
2. **Reescribe `docs/ESTADO.md`.** Sustituye su contenido; no lo acumules. Incluye:
   - Dónde quedó el trabajo.
   - Siguiente paso concreto.
   - Bloqueos y dudas abiertas.
   - Qué quedó **verificado** y qué **sin verificar**. Sé honesto: si no probaste algo, escríbelo.
   Mantén el archivo en 40 líneas o menos y actualiza `actualizado:` con la fecha de hoy.
3. **Anexa a `docs/DECISIONS.md`** una entrada de 5 líneas como máximo si hubo una decisión: qué, por qué, qué cambia y enlace. Si no hubo decisión, no añadas nada.
4. **Decisión grande** (cambia cómo se construye algo): crea una nota ADR en `<decisiones>` con la plantilla `ADR.md` del vault y añádela a su índice.
5. **Lección reutilizable** (un error que costó tiempo, algo que funcionó): una nota en `<lecciones>` con la plantilla `Leccion.md` y una línea en su índice.
6. **Índices.** Si creaste notas, enlázalas desde `<índice>` o desde el índice de su carpeta.
7. **Enlaces.** Comprueba que no dejaste enlaces rotos (mira la skill `auditar-memoria`).
8. **Resume al usuario** en tres líneas qué quedó guardado y dónde.

No guardes secretos ni datos personales. No borres notas sin preguntar.
