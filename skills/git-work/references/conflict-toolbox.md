# Caja de Herramientas Avanzada (GitFlow): Conflictos, Rebases, Worktrees y Rescate

Guía operativa para resolver situaciones complejas en Git bajo **GitFlow** (`feat/*` → `develop` → `main`) sin perder código ni ensuciar el historial.

---

## 1. Diagnóstico Previo de Conflictos (Sin tocar el Working Tree)

Antes de lanzar un `git merge` o `git rebase` hacia `develop` o desde `develop` hacia `main`:

```bash
# 1. Encontrar el punto exacto donde tu feature divergió de develop
git merge-base develop feat/nueva-capa

# 2. Ver cuántos commits tiene cada lado desde la divergencia
git rev-list --left-right --count develop...feat/nueva-capa

# 3. Simular el merge en memoria hacia develop (Git 2.38+)
git merge-tree --write-tree develop feat/nueva-capa

# 4. Simular el pase de develop a main antes de un release
git merge-tree --write-tree main develop
```

Si `git merge-tree` reporta conflictos, puedes ver exactamente qué commits los provocan con:
```bash
git log --oneline --left-right develop...feat/nueva-capa -- <archivo-conflictivo>
```

---

## 2. Resolución Quirúrgica de Conflictos (`zdiff3`)

Activa siempre el estilo `zdiff3` para ver el bloque base original:
```bash
git config merge.conflictstyle zdiff3
```

Cuando abras un archivo en conflicto verás:
```text
<<<<<<< HEAD
calculo_impuesto(base, tasa=0.19, redondear=True)
||||||| 8f3a1b2 (ancestro común en develop)
calculo_impuesto(base)
=======
calculo_impuesto(base, moneda="COP")
>>>>>>> feat/multi-moneda
```

### Razonamiento de Ingeniería con `zdiff3`:
1. En el **ancestro común** (`|||||||`), la llamada solo recibía `base`.
2. En `HEAD` (`develop`), otra feature ya integrada añadió `tasa=0.19, redondear=True`.
3. En `feat/multi-moneda`, se añadió `moneda="COP"`.
4. **Solución correcta**: Combinar ambos cambios (`calculo_impuesto(base, tasa=0.19, redondear=True, moneda="COP")`) y verificar la firma de la función `calculo_impuesto`. Sin `zdiff3`, podrías haber pensado por error que una rama quería borrar los argumentos de la otra.

### Comandos útiles durante un conflicto:
| Situación | Comando |
|---|---|
| Ver lista de archivos con conflicto | `git diff --name-only --diff-filter=U` |
| Verificar si quedaron marcadores `<<<` o espacios rotos | `git diff --check` |
| Aceptar versión de nuestra rama actual para **un solo archivo** (ej. un lockfile que regenerarás) | `git checkout --ours <archivo> && git add <archivo>` |
| Aceptar versión de la rama entrante para **un solo archivo** | `git checkout --theirs <archivo> && git add <archivo>` |
| Rehacer los marcadores de conflicto en un archivo si te equivocaste al editarlo | `git checkout --merge --conflict=zdiff3 <archivo>` |
| Ver el log de los commits que chocaron sobre ese archivo | `git log --merge -p -- <archivo>` |

> **Nota sobre `ours` y `theirs` en `rebase` vs `merge`**:
> - En `git merge`: `--ours` es la rama donde estás parado (`develop`); `--theirs` es la rama que estás trayendo (`feat/...`).
> - En `git rebase develop`: ¡Se invierten! Porque Git primero se para en `develop` (`--ours`) y va reaplicando tus commits de la feature uno por uno (`--theirs`).

---

## 3. Estrategia GitFlow: ¿Cuándo hacer `merge --no-ff`, `rebase` o `squash`?

| Escenario en GitFlow | Estrategia recomendada | Comando |
|---|---|---|
| Poner al día tu rama `feat/*` con lo último que entró a `develop` | **Rebase contra `develop`** (mantiene tu feature limpia sobre la punta de `develop`) | `git fetch origin && git rebase origin/develop` |
| Integrar una rama `feat/*` o `fix/*` terminada hacia `develop` | **Merge `--no-ff` en `develop`** (preserva los commits atómicos y deja trazabilidad de la feature) | `git checkout develop && git merge --no-ff feat/x` |
| Pasar versión lista y probada de `develop` hacia `main` | **Merge `--no-ff` en `main` + Tag SemVer** | `git checkout main && git merge --no-ff develop -m "chore(release): vX.Y.Z" && git tag -a vX.Y.Z -m "Release vX.Y.Z"` |
| Hotfix urgente en producción (`hotfix/*` desde `main`) | **Merge `--no-ff` tanto en `main` como en `develop`** | `git checkout main && git merge --no-ff hotfix/x` y luego `git checkout develop && git merge --no-ff hotfix/x` |

---

## 4. Limpieza de Marcas de Agua o Commits Largos en el Historial

Si un agente o desarrollador dejó commits con `Co-Authored-By`, marcas de agua o asuntos de más de 72 caracteres en la rama actual (aún no fusionada en `develop`):

### Caso 1: Es solo el último commit (`HEAD`)
```bash
git commit --amend -m "feat(modulo): resumen limpio en imperativo"
```

### Caso 2: Son varios commits en la rama actual (`feat/...`)
Reescribe o limpia automáticamente los trailers de IA en todos los commits de tu rama respecto a `develop` (multiplataforma con Python):
```bash
git filter-branch -f --msg-filter "python3 -c \"import sys,re; print(re.sub(r'(?im)^(Co-Authored-By:.*|Generated with.*|🤖.*)\n?', '', sys.stdin.read()).strip())\"" develop..HEAD
```

---

## 5. Rescate de Emergencia en GitFlow (`reflog`, `bisect`, desvíos de rama)

### A. Empezaste a programar sobre `main` o `develop` por descuido (sin commit aún)
Pasa todos tus cambios en curso a una nueva rama de feature sin perder nada:
```bash
git switch -c feat/nombre-correcto
```

### B. Hiciste commits directamente en `main` o `develop` por error (sin haber hecho push)
Si hiciste, por ejemplo, 2 commits directos en `develop` que debían ir en `feat/nueva-capa` (o hiciste commits en `main` que debían ir en `develop`):
```bash
# 1. Crear la rama destino donde sí deben quedar esos commits
git branch feat/nueva-capa

# 2. Retroceder la rama protegida (main o develop) al estado limpio anterior
git reset --hard HEAD~2

# 3. Saltar a la rama correcta (que conserva intactos los 2 commits)
git checkout feat/nueva-capa
```

### C. Recuperar un commit o rama borrada por accidente (`git reflog`)
```bash
git reflog -n 20
git branch rescate-trabajo <hash-del-reflog>
```

### D. Encontrar qué commit de `develop` introdujo un bug (`git bisect`)
```bash
git bisect start
git bisect bad develop              # En develop falla
git bisect good main                # En main (último release) funcionaba
git bisect run pytest tests/test_x.py
git bisect reset
```
