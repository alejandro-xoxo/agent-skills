# {{NOMBRE}}

{{DESCRIPCION}}

> Este archivo se carga en cada sesión: mantenlo en 100 líneas o menos. Lo largo vive en el vault.

## Memoria
- Vault de Obsidian: `{{VAULT}}`
- Dentro del vault (rutas relativas): índice `00 Inicio.md` · inbox `00 Inbox/` · lecciones `03 Lecciones/` · decisiones `04 Decisiones/` · fuentes `05 Fuentes/`
- Fuera del vault: estado vivo `docs/ESTADO.md` · registro corto `docs/DECISIONS.md`
- Si conectas otro vault con otra estructura, cambia aquí las rutas (lo hace la skill global `iniciar-memoria`). Todas las skills leen este bloque.

## Empieza aquí
1. Lee `docs/ESTADO.md`: dónde quedó el trabajo y cuál es el siguiente paso.
2. Si necesitas contexto, abre el índice del vault y sigue solo los `[[enlaces]]` que la tarea requiera. No leas carpetas enteras.
3. La carpeta de fuentes es material crudo: no la leas completa; busca con grep.
4. Antes de actuar sobre un dato guardado (ruta, función, cifra, estado), compruébalo en la fuente. La memoria puede estar vieja.

## Stack y comandos
- Stack: {{STACK}}
- Instalar: (completar)
- Ejecutar: (completar)
- Probar: (completar)

## Reglas de oro
- (Completar con 3 a 7 reglas propias del proyecto.)
- No inventes datos: toda cifra lleva su fuente y su fecha.
- Sin credenciales ni datos personales en el repositorio ni en las notas.
- Si dos fuentes se contradicen, dilo; no elijas en silencio.

## Cómo guardar memoria
| Qué | Dónde | Cómo |
|---|---|---|
| Dónde quedó el trabajo | `docs/ESTADO.md` | Se reescribe, no se acumula |
| Decisión (resumen) | `docs/DECISIONS.md` | Se anexa: 5 líneas como máximo |
| Decisión con razones | decisiones del vault | Nota ADR numerada |
| Lección reutilizable | lecciones del vault | Una idea por nota |
| Idea suelta | inbox del vault | Revisar y mover cada semana |

Al escribir: una idea por nota, con fecha, fuente y el porqué; enlaza con `[[wikilinks]]`; busca si ya existe y actualiza antes de duplicar; borra lo que dejó de ser cierto.

Al cerrar una tarea importante usa la skill `cerrar-tarea`.

## Skills
Procedimientos en `.claude/skills/<nombre>/SKILL.md`. Si tu agente no tiene skills, lee el archivo directamente.
- `memoria`: consultar y escribir en el vault.
- `cerrar-tarea`: rutina de cierre de una tarea.
- `auditar-memoria`: limpieza periódica de la memoria.

## Mapa del repositorio
- `docs/`: estado y decisiones.
- `conocimiento/`: vault local por defecto; no existe si el vault es externo.
- (Añadir aquí las carpetas de código cuando existan.)
