---
name: git-work
description: >-
  Flujo profesional y universal (Windows, Linux, macOS) de ingeniería de software
  en Git bajo metodología GitFlow: ramas de trabajo (`feat/*`, `fix/*`, `refactor/*`)
  que nacen y se integran en `develop` (prohibido hacer productos "one-shot" o
  tocar `main` directo), paso controlado de `develop` a `main` por versión SemVer,
  commits atómicos cortos bajo Conventional Commits sin marcas de agua de IA y
  caja de herramientas quirúrgica para conflictos de merge/rebase, worktrees y
  recuperación. Úsala siempre que gestiones repositorios, crees features nuevas,
  hagas commits, fusiones ramas o resuelvas conflictos.
---

# Git-Work: Ingeniería de Software con GitFlow y Control Profesional de Versiones

Esta skill es **100% multiplataforma (Linux, macOS y Windows)** y obliga al agente a comportarse como un **Staff Software Engineer** aplicando **GitFlow estricto**. Erradica el antipatrón de "producto one-shot en una sola rama" y garantiza que `main` jamás reciba código sin antes haberse construido modularmente y validado en `develop`.

---

## 1. Arquitectura de Ramas: GitFlow Estricto (Cero "One-Shot")

**PROHIBIDO** programar directamente sobre `main` o `develop`, y **PROHIBIDO** construir un proyecto entero en un solo commit monolítico.

### Jerarquía de ramas en GitFlow
```text
main (producción limpia, solo recibe merges desde develop/release o hotfix + tags vX.Y.Z)
 └── develop (rama de integración continua de desarrollo)
      ├── chore/project-scaffold
      ├── feat/domain-models
      ├── feat/<modulo>-service
      ├── feat/<modulo>-api
      └── fix/<modulo>-bug
```

1. **`main` (o `master`) — Santuario de Producción**:
   - Solo contiene versiones estables y probadas listas para producción.
   - **Jamás** se hace commit directo en `main` (salvo el `init` inicial del repo con `.gitignore` y `README.md`).
   - Solo recibe código mediante merge desde `develop` (o una rama `release/*`) cuando se cierra una versión completa.
2. **`develop` — Troncal de Integración**:
   - Nace de `main` al iniciar el proyecto (`git checkout -b develop main`).
   - Es el punto de partida y de llegada de todas las ramas de trabajo diario.
   - Tampoco se programa directo en `develop`: todo bloque funcional se hace en su propia rama hija y entra a `develop` con `git merge --no-ff`.
3. **Ramas de Trabajo (nacen de `develop` → vuelven a `develop`)**:
   - Antes de programar cualquier requerimiento mediano o grande, divídelo por capas de Ingeniería de Software (*Slice → Test → Commit → Merge a `develop`*):
     - `chore/project-scaffold`: configuración base, dependencias, linters, estructura.
     - `feat/domain-models` (o `feat/db-schema`): entidades, migraciones, modelos base.
     - `feat/<modulo>-service`: lógica de negocio aislada con sus tests unitarios.
     - `feat/<modulo>-api` / `feat/<modulo>-ui`: controladores, endpoints o interfaz.
     - `fix/<alcance>-<bug>`: correcciones de bugs detectados en `develop`.
     - `refactor/<alcance>`: mejoras estructurales sin cambio de comportamiento.
4. **Ramas de Emergencia (`hotfix/*`)**:
   - Única excepción que nace de `main` para apagar un incendio en producción y, al cerrarse, se fusiona tanto en `main` como en `develop`.

### Ciclo de vida paso a paso (Comandos Git universales)

```bash
# PASO 0: Asegurar que existe la rama develop partiendo de main
git checkout main
git checkout -b develop

# PASO 1: Crear rama de feature/capa SIEMPRE desde develop actualizado
git checkout develop
git pull --rebase origin develop
git checkout -b feat/auth-jwt

# PASO 2: Desarrollar en commits atómicos (Slice -> Test -> Commit)
git status -s
git add <archivos-de-esta-capa>
git commit -m "feat(auth): add jwt token validation middleware"

# PASO 3: Correr pruebas y fusionar de vuelta a DEVELOP (con --no-ff)
git checkout develop
git merge --no-ff feat/auth-jwt -m "Merge branch 'feat/auth-jwt' into develop"
git branch -d feat/auth-jwt

# PASO 4: Repetir Pasos 1-3 para las siguientes ramas (feat/auth-endpoints, etc.)

# PASO 5: Pase a Producción (De DEVELOP -> MAIN) solo al cerrar versión estable
git checkout main
git merge --no-ff develop -m "chore(release): release v0.2.0"
git tag -a v0.2.0 -m "Release v0.2.0"
git checkout develop
```

---

## 2. Disciplina de Commits (Atómicos, Cortos y Sin Marcas de Agua)

### A. Prohibición absoluta de marcas de agua y firmas de IA
**NUNCA** incluyas en ningún mensaje de commit, cuerpo, footer, tag o PR:
- `Co-Authored-By: Claude...`, `Co-Authored-By: Gemini...`, `Co-Authored-By: Cursor...`
- `Generated with Claude Code`, `Assisted by AI`, emojis robóticos (`🤖`, `✨`) ni enlaces a herramientas de IA.
- Banderas `--trailer` o plantillas que inyecten co-autores automáticos.

### B. Regla 50/72 y Conventional Commits
Todo commit debe seguir el estándar **Conventional Commits** en una sola línea concisa (y cuerpo opcional solo cuando el *porqué* arquitectónico no sea obvio):

```text
<tipo>(<alcance>): <descripción en imperativo, minúscula, sin punto final>
```

- **Longitud máxima del asunto**: **50 caracteres** ideal (límite estricto: **72 caracteres**). Si necesitas más espacio, tu commit hace demasiadas cosas o estás explicando el *cómo* en vez del *qué*.
- **Tipos permitidos**:
  - `feat`: nueva funcionalidad para el usuario (sube versión `MINOR`).
  - `fix`: corrección de un bug (sube versión `PATCH`).
  - `refactor`: cambio de código que no corrige bugs ni añade features.
  - `perf`: mejora de rendimiento medible.
  - `test`: añadir o corregir pruebas.
  - `docs`: cambios exclusivos en documentación.
  - `build` / `ci` / `chore`: herramientas, dependencias, configuración.
  - `style`: formato, espacios, punto y coma (sin cambio semántico).

**Ejemplos malos (PROHIBIDOS):**
- `feat: implement authentication system, database models, login page and fix cors bug in server` *(demasiado largo y mezcla 4 cosas)*
- `update files` / `wip` / `fix bug` *(sin contexto ni sentido)*
- `feat(api): add endpoint.\n\n🤖 Generated with Claude\nCo-Authored-By: ...` *(con marca de agua y punto final)*

**Ejemplos buenos:**
- `feat(auth): issue refresh token on login`
- `fix(parser): handle empty decimal in signal price`
- `refactor(db): extract connection pool factory`
- `chore(deps): lock fastembed to 0.3.x`

### C. Atomicidad y Staging Quirúrgico
- **Un commit = un cambio lógico que compila y pasa tests por sí solo.**
- **Nunca uses `git add .` ni `git add -A` a ciegas.** Revisa siempre `git status -s` y `git diff --stat` antes de preparar archivos.
- Si tocaste dos cosas distintas en el mismo archivo, divídelas o haz staging selectivo.
- Tamaño ideal por commit: **20 a 200 líneas**. Si supera ~300 líneas de lógica, divídelo en commits por capa (ej. primero modelo/interfaz, luego implementación, luego tests).

---

## 3. Higiene del Repositorio y Versionado Semántico (SemVer)

1. **Antes de cada primer commit en un repo**:
   - Verifica que `.gitignore` cubra `.env*`, credenciales, `.venv/`, `node_modules/`, `dist/`, `build/`, cachés (`__pycache__/`, `.pytest_cache/`, `.rag/indice/`), binarios locales y datos personales.
   - Ejecuta `git diff --cached` para comprobar que no entren secretos, claves API ni archivos temporales.
2. **Auditoría universal antes de cerrar o hacer push**:
   - Ejecuta el script multiplataforma en Python ([`scripts/git_doctor.py`](./scripts/git_doctor.py)), que funciona idéntico en **Linux, macOS y Windows**:
     ```bash
     python3 "<ruta-a-la-skill>/scripts/git_doctor.py" --fix-config
     # (o `python` en Windows)
     ```
   - Comprueba que existe `develop`, que no estás editando directo sobre `main` ni `develop`, que los commits cumplen formato/longitud/cero marcas de agua y que las fusiones hacia `develop` y `main` están libres de conflictos.
3. **Manejo de Versiones en el paso `develop` → `main` (SemVer `vMAJOR.MINOR.PATCH`)**:
   - Cuando todas las ramas `feat/*` y `fix/*` de una iteración ya se integraron en `develop` y pasaron las pruebas, se fusiona `develop` en `main` y se etiqueta:
     ```bash
     git checkout main
     git merge --no-ff develop -m "chore(release): release v0.2.0"
     git tag -a v0.2.0 -m "Release v0.2.0: soporte multi-cuenta y parser v2"
     git checkout develop
     ```
   - `PATCH` (`0.1.0` → `0.1.1`): solo commits `fix`, `perf`, `refactor`.
   - `MINOR` (`0.1.1` → `0.2.0`): al menos un `feat` compatible hacia atrás.
   - `MAJOR` (`0.2.0` → `1.0.0`): cambios incompatibles (`feat!:` o `BREAKING CHANGE:`).

---

## 4. Caja de Herramientas: Conflictos, Merges, Rebases y Rescate

Para casos avanzados, consulta la referencia completa en [`references/conflict-toolbox.md`](./references/conflict-toolbox.md). Resumen operativo:

### A. Preparación del entorno Git (universal)
Configura Git para ver el ancestro común en los conflictos (`zdiff3`) y recordar resoluciones previas (`rerere`):
```bash
git config merge.conflictstyle zdiff3
git config rerere.enabled true
git config rerere.autoupdate true
```

### B. Pre-chequeo de conflictos en seco (Dry-Run antes de fusionar)
Antes de integrar tu rama `feat/*` en `develop` (o `develop` en `main`), simula el cruce en memoria sin tocar tu directorio de trabajo:
```bash
# Antes de pasar tu feature a develop:
git merge-tree --write-tree develop feat/mi-rama

# Antes de pasar develop a main:
git merge-tree --write-tree main develop
```
- Si devuelve código `0` y un hash de árbol: **fusión 100% limpia garantizada**.
- Si devuelve código `1`: lista exactamente qué archivos tendrán conflicto antes de tocar nada.

### C. Protocolo Quirúrgico cuando estalla un Conflicto
Nunca resuelvas un conflicto borrando un bloque al azar ni aceptando `--ours` / `--theirs` sin leer la historia de ambos lados:

1. **Identifica los archivos en conflicto (comando Git puro, sin depender de `grep`)**:
   ```bash
   git diff --name-only --diff-filter=U
   ```
2. **Investiga la intención de ambos lados** antes de editar:
   ```bash
   git log --oneline --left-right --merge -p -- <archivo>
   ```
3. **Lee las 3 secciones del marcador `zdiff3`**:
   - `<<<<<<< HEAD` (o `ours`): lo que hay en la rama destino actual (`develop` o `main`).
   - `||||||| base`: cómo estaba el código originalmente antes de que ambas ramas lo tocaran.
   - `=======` ... `>>>>>>> rama`: lo que intenta introducir la rama entrante.
4. **Integra ambas intenciones** (o elige una si es un reemplazo explícito), verifica que no quede ningún marcador `<<<<<<<`, `|||||||` ni `>>>>>>>`:
   ```bash
   git diff --check
   ```
5. **Ejecuta los tests correspondientes al módulo afectado**, haz `git add <archivo>` y continúa (`git merge --continue` o `git rebase --continue`).
6. **Si algo sale mal a mitad del proceso**, aborta limpiamente (`git merge --abort` o `git rebase --abort`) y vuelve a analizar.

### D. Trabajo en paralelo sin pisarse (`git worktree`)
Cuando necesites ejecutar subagentes en distintas ramas `feat/*` sobre `develop` o atender un `hotfix/*` en `main` sin hacer `stash`:
```bash
git worktree add ../<repo>-feat-api -b feat/api-endpoints develop
# ... trabajar, probar, commitear y fusionar en develop ...
git worktree remove ../<repo>-feat-api
```

### E. Limpieza de historial antes de entregar a `develop` (`--fixup` y `--autosquash`)
Si durante el desarrollo de una rama `feat/*` detectas un olvido que pertenece a un commit anterior de esa misma rama:
```bash
git commit --fixup <hash-del-commit-original>
git rebase -i --autosquash develop
```
Y si limpiaste una marca de agua o un mensaje demasiado largo en el último commit local:
```bash
git commit --amend -m "feat(modulo): mensaje corto y limpio"
```
*(Si la rama ya fue subida a remoto propio, usa siempre `git push --force-with-lease`, jamás `git push --force` a secas).*
