---
name: auditar-memoria
description: Revisión periódica de la memoria del proyecto. Encuentra enlaces rotos, notas huérfanas, duplicadas, contradictorias o desactualizadas, y un AGENTS.md demasiado largo. Úsala cuando el usuario pida limpiar o revisar la memoria, o cuando AGENTS.md pase de 100 líneas.
---

# Auditar la memoria

> **Requisito:** el proyecto debe tener el bloque `## Memoria` en `AGENTS.md`. Si no lo tiene, la memoria no está configurada: usa antes la skill `iniciar-memoria` (o díselo al usuario) y no sigas.

La memoria sin mantenimiento se llena de datos viejos y contradicciones, y eso es peor que no tener memoria. Propón cambios; **no borres nada sin preguntar**. La ruta del vault (`<vault>`) está en el bloque `## Memoria` de `AGENTS.md`.

## 1. Tamaño de lo que se carga siempre
```bash
wc -l AGENTS.md docs/ESTADO.md
```
- `AGENTS.md` por encima de 100 líneas: mueve lo que solo sirve para una parte a una nota del vault o a una regla por ruta en `.claude/rules/`.
- `docs/ESTADO.md` por encima de 40 líneas: se está acumulando; recórtalo.

## 2. Enlaces rotos y notas huérfanas
Sustituye `<vault>` por la ruta real.
```bash
T=$(mktemp -d)
cd "<vault>"
find . -name '*.md' -print0 | xargs -0 -n1 basename | sed 's/\.md$//' | sort -u > "$T/nombres.txt"
grep -rhoP '\[\[\K[^\]|#]+' --include='*.md' --exclude-dir='05 Fuentes' --exclude-dir=Plantillas --exclude-dir=.obsidian . | sed 's/[[:space:]]*$//' | sort -u > "$T/enlaces.txt"
echo "--- enlaces rotos:"; comm -23 "$T/enlaces.txt" "$T/nombres.txt"
echo "--- notas sin enlaces entrantes:"
while IFS= read -r n; do grep -rqF "[[$n" --include='*.md' --exclude-dir=Plantillas . || echo "$n"; done < "$T/nombres.txt"
```
Ajusta `--exclude-dir` al nombre real de la carpeta de fuentes. Ignora como huérfanas las plantillas y el propio índice. Si el vault es compartido con otros proyectos, limita la búsqueda a la subcarpeta de este proyecto.

## 3. Contenido viejo, duplicado o contradictorio
- Busca por palabra clave las ideas que aparecen en varias notas y fusiona.
- Para cada nota con `status: propuesta` de hace mucho, pregunta si sigue vigente.
- Contrasta 3 o 4 datos concretos (rutas, comandos, cifras) con la fuente real. Si ya no coinciden, corrige la nota y anótalo en `docs/DECISIONS.md`.
- Si dos notas se contradicen, dilo al usuario; no elijas en silencio.

## 4. Informe
Entrega una lista corta: qué encontraste, qué propones cambiar y qué necesitas que confirme el usuario. Aplica solo lo que confirme.
