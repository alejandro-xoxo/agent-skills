# Recuperación automática (RAG local)

Añade al mensaje del usuario, antes de que el agente lo vea, los trozos más relevantes del vault y de `docs/`, con archivo y líneas. Es una búsqueda por significado (vectores) mezclada con palabras exactas, que corre entera en este equipo.

## Qué es y qué no es
- **Sí:** sirve cuando las fuentes son grandes (conversaciones de miles de líneas, muchos documentos) y `grep` no encuentra por significado. Las notas curadas pesan más que el material crudo.
- **No:** no sustituye a `AGENTS.md`, `ESTADO.md` ni a las notas. Y no hace que la IA acierte más por sí sola: mejora qué trozos le llegan. Cada trozo trae archivo y líneas para verificarlo.

## Cómo se activa
1. `nuevo-proyecto.ps1 -ConRag` (o `-SoloRag` en un proyecto que ya existe) copia estos archivos a `.rag/`, añade una línea a `AGENTS.md` e ignora `.rag/` en git. **No instala nada.**
2. `powershell -NoProfile -ExecutionPolicy Bypass -File .rag\preparar.ps1` hace lo pesado: entorno de Python, `fastembed`, índice, ganchos de Claude Code y servidor. La primera vez descarga unos 0,6 GB (el modelo, que comparten todos los proyectos en `%USERPROFILE%\.cache\rag-modelos`) y puede tardar varios minutos.
3. Abre `/hooks` una vez o reinicia la sesión del agente.

## Requisitos
Windows con PowerShell y el launcher `py`, y Python de la 3.10 a la 3.13. Probado con Python 3.12. En Python 3.15 no sirve porque `onnxruntime` no publicaba versión para él.

## Qué hace en segundo plano
- Un servidor local (solo `127.0.0.1`, con clave) mantiene el modelo cargado y responde en decenas de milisegundos. Ocupa unos 700 MB de memoria mientras está activo y se apaga solo tras 30 minutos sin uso. El gancho de inicio de sesión lo vuelve a arrancar, y si un mensaje llega con el servidor apagado, ese mensaje va sin contexto (el gancho nunca espera más de unos 3 s) y el siguiente ya lo tiene.
- En Windows el servidor se lanza por WMI y sin consola (`pythonw`). Motivo: en una sesión real, un servidor lanzado directamente desde un gancho desaparecía poco después (se deduce que moría con el gancho). Por WMI, en una prueba, sobrevive aunque se cierre todo el árbol de procesos de quien lo lanzó. Que siga vivo entre mensajes reales no se ha comprobado a largo plazo.
- Si cambias una nota, el índice se actualiza solo en segundo plano; el cambio se ve a los pocos segundos y ninguna búsqueda espera.
- Solo inyecta contexto si el mensaje trata de algo del vault (similitud mínima 0,50, ajustable con `RAG_UMBRAL`). Los comandos `/`, los mensajes muy cortos y los avisos automáticos del sistema no inyectan nada. Si el mensaje no pasa el umbral, no se inyecta nada: es mejor no dar contexto que darlo equivocado.

## Costes y cuidados
- Cada mensaje relacionado añade entre 500 y 900 tokens de contexto.
- `.rag/indice/` guarda el texto completo de las fuentes, incluidos los datos personales que haya. Está fuera de git; no lo copies a otras personas.
- El contexto inyectado viaja al modelo como parte de la conversación. Los vectores se calculan aquí.
- Apagarlo: variable de entorno `RAG_DESACTIVAR=1`. Quitarlo: borra `.rag/` y los dos ganchos de `.claude/settings.local.json`.

## Medir si funciona
Copia `evaluacion.ejemplo.json` como `evaluacion.json`, cambia las preguntas por 15 o 20 propias (con el archivo donde está la respuesta) y ejecuta `rag.py evaluar`. Muestra el acierto de palabras, significado y mezcla, y el umbral recomendado. En el primer proyecto donde se probó, con 20 preguntas escritas por quien conocía las notas, la mezcla acertó en los 3 primeros el 95% de las veces y las palabras solas el 70%; con tus propias preguntas el resultado puede ser distinto.

## Sin probar
macOS y Linux, y Python distinto de 3.12 (`preparar.ps1` busca la 3.12, 3.13, 3.11 y 3.10 en ese orden). Que los ganchos se disparen en una sesión real depende de que Claude Code los cargue (paso 3).
