---
name: workflow-orquestar
description: Orquesta un trabajo grande repartiéndolo entre agentes de CLI (OpenCode con modelos gratuitos por defecto, agy de respaldo con Gemini/Claude, y Codex de OpenAI) con soporte para grafos DAG, auto-corrección de tests (self-healing), streaming en vivo con monitor visual, fusión inteligente 3-way y telemetría de tokens y costes. Úsala cuando el usuario pida orquestar, repartir en paralelo, auditar o implementar por partes.
---

# Orquestar con `wf.py` (Arquitectura Multi-Agente)

El orquestador (el agente que lidera el trabajo; se elige en `orquestador.json`) planifica, escribe el script de orquestación, lo ejecuta y valida la entrega final. Los agentes de `opencode` y `agy` son la mano de obra en copias aisladas.

---

## 1. Motores y Trabajadores

- **`opencode`** (primero por defecto, gratis): modelos gratuitos de OpenCode CLI (`npm install -g @opencode/cli`). Sin sesión ni costo; en pruebas es el más rápido (10-25 s). Comprobar con:
  `opencode run --standalone -m opencode/nemotron-3-ultra-free "Responde solo: ok"`
- **`agy`**: Antigravity CLI con modelos Gemini y Claude; cuota alta y soporte de herramientas. Comprobar con:
  `agy -p "Responde solo: ok" --mode plan --model gemini-3.8-flash-low`
- **`codex`** (cuenta de OpenAI, de pago): solo con `worker="codex"`. Usa el modelo que la persona tenga configurado en Codex (`codex exec -s read-only|workspace-write -C <carpeta>`).

### Niveles de calidad (`tier`) y modelos

| `tier` | `opencode` (gratis) | `agy` (Gemini / Claude) | `codex` | Para qué |
|---|---|---|---|---|
| `max` | `opencode/nemotron-3-ultra-free` | `gemini-4-argon-high` | `default` | Arquitectura compleja y seguridad |
| `pro` | `opencode/nemotron-3-ultra-free` | `gemini-3.8-flash-high` | `default` | Cambios que cruzan módulos, refactorización profunda |
| `standard` | `opencode/deepseek-v4.1-flash-free` | `gemini-3.8-flash-medium` | `default` | Desarrollo general y controladores |
| `fast` | `opencode/minimax-m3.1-flash-free` | `gemini-3.8-flash-low` | `default` | Tareas mecánicas, scaffolding, alto volumen |
| `design` | — | `claude-sonnet-5-5-medium` | — | Diseño gráfico y componentes visuales |

El orden por defecto es `opencode` y luego `agy`.

---

## 2. Nuevas Funcionalidades del Orquestador

### A. Monitor Visual en Tiempo Real
Permite ver en una **segunda terminal fija** exactamente qué está haciendo cada agente (lecturas, ediciones, comandos, tests):
```powershell
# En la Terminal 2:
python <carpeta de la skill>/monitor.py
# O también:
python <carpeta de la skill>/wf.py --monitor
```
- **Teclas interactivas:** `[1-9]` para enfocar un agente específico, `[0]` para vista mosaico global de todos los agentes a la vez, `[Q]` para salir.
- El log en disco se escribe en tiempo real en `%TEMP%\wf-runs\<RUN_ID>\agente-N.log`.

### B. Auto-Corrección y Pruebas Locales (`verify_cmd` / Self-Healing)
El agente no se da por terminado hasta que su código pase la suite de verificación indicada:
```python
await agent(
    "Implementa el servicio StudentService en StudentService.java",
    schema={"type": "object", "required": ["resumen"], "properties": {"resumen": {"type": "string"}}},
    workspace="branch",
    edit=True,
    verify_cmd="mvn test -Dtest=StudentServiceTest",  # Corre dentro de la copia aislada
    max_fixes=2                                      # Reintenta hasta 2 veces inyectando el error
)
```
Si el test falla, `wf.py` captura el error y le pide al subagente que corrija los archivos en su copia antes de entregar.

### C. Grafos de Dependencias (`dag` y `task`)
Permite definir flujos no lineales donde una tarea espera los resultados de otras:
```python
t1 = task("db", prompt="Diseña el esquema SQL...", schema=SchemaDB)
t2 = task("servicio", prompt="Crea el servicio...", schema=SchemaService, depends_on=[t1])
t3 = task("controlador", prompt="Crea el controlador...", schema=SchemaCtrl, depends_on=[t2])
t4 = task("documentacion", prompt="Genera el README...", schema=SchemaDoc, depends_on=[t1, t2])

# Resuelve el orden topológico y paraleliza las tareas listas
resultados = await dag([t1, t2, t3, t4])
```

### D. Fusión Inteligente y Detección de Colisiones (`auto_integrate`)
- `check_collisions()`: Comprueba si dos copias modificaron los mismos archivos.
- `auto_integrate()`: Si los conjuntos de archivos son disjuntos, aplica todos los cambios directamente con `git apply --3way --whitespace=fix`.

### E. Telemetría y Estimación de Costes
Al finalizar el workflow, `wf.py` reporta en consola y en `telemetry.json`:
- Tiempo total vs. tiempo acumulado de agentes (cálculo de aceleración paralela, ej: `3.5x`).
- Tokens estimados (input y output).
- Costo económico aproximado en USD.

---

## 3. Primitivas Disponibles

| Primitiva | Descripción |
|---|---|
| `agent(prompt, schema, role, tier, worker, workspace, edit, timeout, verify_cmd, max_fixes)` | Define un agente ejecutable. |
| `parallel(items, fn)` | Ejecuta tareas en paralelo (hasta `WF_MAX_PARALLEL`, por defecto 4). |
| `pipeline(items, fn)` | Ejecuta tareas en orden secuencial estricto. |
| `task(id, prompt, schema, depends_on, **kwargs)` | Define un nodo para grafos dirigidos. |
| `dag(tasks)` | Resuelve y ejecuta el grafo de tareas concurrentemente. |
| `check_collisions()` | Retorna colisiones entre worktrees. |
| `auto_integrate()` | Aplica los diffs con 3-way merge si no hay colisiones. |
| `phase(name)` | Define y registra una fase en logs y en el monitor visual. |
| `log(...)` | Imprime y registra información en `log.txt`. |
| `cleanup_worktrees()` | Elimina las copias temporales aisladas. |

---

## 4. Plantilla de Implementación Completa

```python
phase("Implementación Paralela")

tareas = [
    {"id": "estudiantes", "archivos": ["StudentService.java"], "test": "mvn test -Dtest=StudentServiceTest"},
    {"id": "profesores", "archivos": ["TeacherService.java"], "test": "mvn test -Dtest=TeacherServiceTest"},
]

hechas = await parallel(tareas, lambda t: agent(
    f"Implementa {t['id']} editando solo: {t['archivos']}. Sin commit.",
    schema={"type": "object", "required": ["resumen", "ok"], "properties": {"resumen": {"type": "string"}, "ok": {"type": "boolean"}}},
    role=t["id"],
    tier="standard",
    workspace="branch",
    edit=True,
    verify_cmd=t["test"],
    max_fixes=2
))

phase("Integración")
# Verifica colisiones y fusiona con 3-way merge
integradas = auto_integrate()
log("Ramas integradas exitosamente:", integradas)
cleanup_worktrees()
```

---

## 5. Reglas de Seguridad

1. **Nunca** pasar secretos, credenciales ni tokens en los prompts.
2. Los subagentes **no hacen commit ni push**; trabajan en sus copias aisladas y los cambios se aplican con `auto_integrate()`.
3. Todo encargo lleva por defecto un estilo de respuesta breve (el texto «ultracave» que incorpora `wf.py`; se apaga con `WF_CAVEMAN=0`) para ahorrar tokens y latencia.
4. Si un agente falla, `wf.py` pasa al siguiente trabajador de la lista automáticamente.
