---
name: navegador-cdp
description: Maneja Chrome o Edge sin extensiones (por CDP, con Node) para hacer cosas puntuales en una web y para crear, guardar y reutilizar procesos repetitivos del navegador. Un proceso nuevo solo se guarda en la memoria de la skill cuando el agente lo ejecuta de principio a fin sin errores y con el resultado verificado. Úsala siempre que el usuario pida abrir una web y hacer algo en ella, automatizar un proceso en el navegador, "crear un proceso", "ejecutar el proceso X", "listar mis procesos" o "qué procesos tengo", o cuando no haya una extensión de navegador disponible o el usuario no quiera depender de extensiones. Funciona con cualquier agente que pueda ejecutar comandos de shell.
---

# Navegador sin extensiones, con memoria de procesos

Controla un Chrome o un Edge por el protocolo de depuración (CDP), con scripts de Node sin dependencias. No necesita extensiones, solo un navegador y Node 22 o superior. La skill tiene dos partes:

1. **Tareas puntuales**: abrir una web, leer, hacer clic, escribir, subir archivos, tomar capturas (`scripts/nav.mjs`).
2. **Memoria de procesos**: un proceso repetitivo se construye, se prueba hasta que sale limpio y solo entonces se guarda, para reutilizarlo después con un comando (`scripts/proceso.mjs`).

Para todos los comandos de abajo, `S` es la carpeta `scripts/` de esta skill, allí donde esté instalada y se ejecutan con `node $S/nav.mjs ...` o `node $S/proceso.mjs ...`. Si necesitas la API completa o las trampas conocidas, lee `referencia.md`.

## Por qué funciona así
- El navegador que se abre es **una ventana aparte** con su propio perfil. No toca el navegador normal del usuario, sus pestañas ni sus sesiones. Por eso el usuario **inicia sesión a mano** cuando un sitio lo pide; nunca se piden ni se guardan contraseñas.
- Sin `--perfil`, el perfil es temporal y se borra al cerrar. Con `--perfil <nombre>` la sesión se conserva entre usos (útil para procesos que repiten un inicio de sesión), guardada fuera de esta carpeta en `%LOCALAPPDATA%\navegador-cdp\perfiles\`.
- Un proceso guardado no es "lo que el agente recuerda": es un script (`ejecutar.mjs`) más su ficha (`proceso.md`), que cualquier agente puede leer y ejecutar.

## Comandos del usuario
Cuando el usuario invoque la skill con argumentos o lo pida con otras palabras, interprétalo así:

| Dice | Haz |
|---|---|
| `crear <nombre> <explicación del proceso>` | Sigue el bucle de creación de abajo |
| `listar` (o "qué procesos tengo") | `node $S/proceso.mjs listar` y resume el resultado |
| `ejecutar <nombre> [clave=valor ...]` | Sigue "Usar un proceso guardado" |
| `ver <nombre>` | `node $S/proceso.mjs ver <nombre>` |
| `reparar <nombre>` | `reparar` y luego el bucle desde el paso 4 |
| `borrar <nombre>` | Confirma con el usuario y ejecuta `borrar <nombre> --si` |
| cualquier otra petición sobre una web | Tarea puntual (siguiente sección) |

## Tareas puntuales
1. `node $S/nav.mjs abrir [--url U] [--perfil nombre]` (añade `--headless` si no hace falta que el usuario vea la ventana). Si el sitio pide sesión, pide al usuario que inicie sesión en esa ventana y espera.
2. Trabaja con `ir`, `leer`, `esperar`, `clic`, `escribir`, `seleccionar`, `tecla`, `subir`, `eval`, `captura`. `node $S/nav.mjs ayuda` lista todo. Un objetivo es un selector CSS, `texto=Guardar` (elemento visible con ese texto) o coordenadas `x,y`.
3. Prefiere **leer texto y el DOM** (`leer`, `eval`) a mirar capturas: es más barato y no depende de que el agente vea imágenes. Usa `captura` cuando haga falta ver algo visual.
4. Espera antes de leer lo que carga tarde (`esperar`), y comprueba el resultado de cada acción antes de seguir (por ejemplo, `leer` el mensaje de confirmación).
5. Al terminar, `cerrar` si el navegador era temporal. Si había una sesión que el usuario quiere conservar, déjala abierta o usa un perfil con nombre.

Si hay varias pestañas, indica cuál con `--tab <id>` (las lista `pestanas`). El puerto por defecto es 9222 y se cambia con `--puerto`, lo que permite tener varias ventanas a la vez, por ejemplo una por cuenta.

## Crear un proceso (bucle de creación)
Idea central: **un proceso que no se ha visto funcionar de principio a fin no vale como memoria**, porque la siguiente vez fallaría y nadie sabría por qué. Por eso `guardar` rechaza cualquier borrador cuyo último intento no haya salido limpio, y no hay forma de saltarse eso. Tu trabajo es llegar a ese intento limpio de verdad, sin trucos.

1. **Entender.** Reformula el proceso en pasos numerados y averigua solo lo que falte y bloquee: sitio, parámetros, si necesita sesión, qué demuestra que salió bien. Identifica **pasos irreversibles** (enviar, pagar, borrar, publicar). Si los hay, pregunta ya cómo probarlos sin daño (cuenta de prueba, modo de ensayo, otro destinatario), porque durante la construcción se repiten.
2. **Preparar el navegador.** `abrir` (con `--perfil <nombre>` si hace falta sesión y quieres reutilizarla). El usuario inicia sesión a mano. Comprueba con `leer` o `url` que la sesión funciona.
3. **Explorar a mano** con `nav.mjs` antes de escribir nada: `leer`, `eval` para listar campos y botones, `captura`. Elige selectores estables (id, name, aria-label, texto visible), no posiciones ni coordenadas, que cambian con el tamaño de la ventana.
4. **Escribir el borrador.** `node $S/proceso.mjs nuevo <nombre> "<descripción>"` crea `borradores/<nombre>/ejecutar.mjs` y `proceso.md`. En `ejecutar.mjs` pon un `paso('título claro', ...)` por cada paso visible para el usuario, `esperar` después de navegar o pulsar, y al final **`verificar(condición, 'qué demuestra')` sobre el resultado real** (el texto de confirmación, el valor guardado, el archivo bajado), no solo "no hubo error". Sin ninguna verificación el intento cuenta como fallido.
5. **Probar y corregir.** `node $S/proceso.mjs probar <nombre> [clave=valor ...]`. Si falla, la salida trae el paso fallido, el error, la URL, un resumen del texto de la página y la ruta de una captura (`ultimo-error.png`): míralos, encuentra la **causa real**, corrige y vuelve a probar. No debilites una verificación ni borres un paso para que "pase": eso guardaría un proceso que no hace lo que dice.
6. **Si algo no se puede resolver** (captcha, verificación en dos pasos, un permiso que falta, un micrófono, o unos 8 intentos sin avanzar), detente. Cuéntale al usuario qué probaste y qué bloquea, y no guardes nada.
7. **Pasos irreversibles.** Llama a `irreversible('qué va a pasar')` justo antes de cada uno. Sin confirmación el intento se detiene con `necesita_confirmacion`: pregunta al usuario y, solo si autoriza, repite con `--confirmo`. Cada ejecución confirmada repite la acción real, así que evita corregir el script después de una confirmada si no es imprescindible, y pide permiso otra vez si lo haces.
8. **Completar `proceso.md`.** Quita todos los "(completar)": qué hace, parámetros con ejemplo, precondiciones, pasos, cómo se verifica, pasos irreversibles, trampas. `guardar` rechaza la ficha incompleta.
9. **Guardar.** `node $S/proceso.mjs guardar <nombre>`. Comprueba que el último intento salió bien, que tiene verificaciones, que `ejecutar.mjs` es exactamente el que se probó y que la ficha está completa. Si rechaza, lee los motivos y corrígelos; nunca copies archivos a `procesos/` a mano ni edites `intentos.jsonl`.
10. **Cerrar.** Dile al usuario qué se guardó, cómo ejecutarlo (`ejecutar <nombre> clave=valor`) y que se verificó contra el sitio tal como estaba hoy (si el sitio cambia, puede romperse). Cierra el navegador si era temporal.

## Usar un proceso guardado
1. `listar` y, si hace falta, `ver <nombre>` para conocer parámetros, precondiciones y pasos irreversibles.
2. Abre el navegador con el perfil que pide la ficha. Si el proceso tiene pasos irreversibles, dile al usuario qué hará antes de ejecutarlo.
3. `node $S/proceso.mjs ejecutar <nombre> [clave=valor ...]`.
4. **OK**: cuenta el resultado. **Error**: el proceso queda marcado `ROTO` en `listar`; cuéntale al usuario qué falló y ofrece `reparar <nombre>`, que copia el proceso a `borradores/` y te lleva al paso 4 del bucle sin tocar la versión guardada hasta que la corrección salga limpia. **`necesita_confirmacion`**: pregunta al usuario y repite con `--confirmo` solo si autoriza.

## Ahorro de tokens
Esta skill ya está pensada para gastar poco: `leer` y `eval` en vez de capturas, salidas cortas, y un proceso guardado se ejecuta con un comando en lugar de repetir toda la exploración.

Si tu entorno ofrece además un modo de respuestas breves (por ejemplo, skills de estilo "caveman", que no se incluyen en este repositorio), puedes usarlo y mantenerlo mientras esté activo, y aplicarlo también a los encargos a agentes (ver `briefs/brief-proceso.md`). No prometas ahorros concretos: dependen del modelo y de la tarea. Los archivos que se guardan (`proceso.md`, comentarios en `ejecutar.mjs`) van siempre en prosa normal.

Si el usuario pide ahorrar tokens y no tienes ese modo disponible, recomiéndale instalarlo y aclara que esta skill funciona igual sin él. No lo descargues ni inventes de dónde sacarlo.

## Varios procesos en paralelo (workflow-orquestar)
Cuando el usuario pida construir o ejecutar **varios** procesos a la vez (por ejemplo, el mismo proceso en 10 sitios, o 3 procesos nuevos), repartirlos entre agentes ahorra tiempo. Para eso existe la skill `workflow-orquestar`, que reparte el trabajo entre agentes de CLI (`opencode`, `agy`, `codex`) con un script `wf.py`.

**Antes de proponerlo, comprueba que está disponible:** que tengas la carpeta de la skill `workflow-orquestar` (con su `SKILL.md` y `wf.py`), y que haya al menos un CLI trabajador (`opencode`, `agy` o `codex`; `Get-Command opencode`). Si falta algo, **recomienda instalarlo**, di qué falta (según esa skill, `opencode` se instala con `npm install -g @opencode/cli`; la skill `workflow-orquestar` se publica en el mismo repositorio que esta) y sigue con los procesos de uno en uno; no instales nada tú por tu cuenta.

Cómo combinarlas:
1. El orquestador eres tú. Escribe el script de orquestación siguiendo la skill `workflow-orquestar`, con un agente por proceso. Por defecto corren hasta 4 a la vez.
2. **Todos comparten un solo navegador y una sola sesión, cada agente en su propia pestaña**. Abre el navegador una vez (`abrir --perfil <nombre>` si quieres conservar la sesión), el usuario inicia sesión a mano **una sola vez** y los agentes trabajan en pestañas distintas. Es más rápido y gasta menos recursos que un navegador por agente.
   - `proceso.mjs probar` y `ejecutar` abren y cierran su propia pestaña solos, así que se pueden lanzar varios a la vez contra el mismo puerto.
   - Para explorar con `nav.mjs`, cada agente crea la suya con `nueva <url>` y pasa `--tab <id>` en todos sus comandos (con varias pestañas abiertas, `nav.mjs` se niega a actuar sin `--tab`).
   - Un agente nunca toca la pestaña de otro, ni la inicial, ni cierra el navegador: `cerrar` es solo del orquestador, y mataría el trabajo de todos.
3. **Navegadores o perfiles separados solo hacen falta** si los agentes necesitan **cuentas distintas**, o si el sitio no admite dos pestañas con la misma sesión a la vez (algunos cierran la sesión o mezclan el estado compartido). Entonces, un `--puerto` y un `--perfil` por cuenta.
4. Dale a cada agente `briefs/brief-proceso.md` con sus valores (`NAME`, `PORT`, `TASK`, `PARAMS`, `MODE`, `REPORT` y `SKILL`, la ruta absoluta de la carpeta de esta skill) y no pongas secretos en el encargo. Cada agente que construye un proceso necesita un `NAME` distinto.
5. **Los pasos irreversibles no se delegan.** El agente se detiene con `needs-confirm`; tú le preguntas al usuario y, si autoriza, repites esa ejecución con `--confirmo`.
6. La compuerta de `guardar` protege aunque trabajen agentes: ninguno puede guardar un proceso sin un intento limpio y verificado. Aun así, **no te fíes de lo que digan en su informe**: comprueba con `listar` qué se guardó de verdad y, si hace falta, con `ejecutar`.

**Cuántos a la vez.** Medido con Chrome y una página local de prueba: 4 ejecuciones simultáneas tardaron 2,4 s frente a 7,3 s seguidas; 12 a la vez, 4,2 s; 20 a la vez, 9,0 s, aunque cada una se alarga por competir por el navegador. Funcionó también con ventana visible. En sitios reales los tiempos serán otros: empieza con 4 (el valor por defecto del orquestador) y no pases de 8 por navegador sin comprobar.

Está probado que **varias ejecuciones simultáneas comparten un navegador sin pisarse** (con un bloqueo para `estado.json`). Lo que **no se ha ejecutado todavía** es el orquestador `wf.py` repartiendo agentes reales con esta skill. Si algo falla, díselo al usuario y continúa de forma secuencial.

## Reglas
- Nunca pidas, escribas ni guardes contraseñas. Si aparece un login, para y pide al usuario que lo haga.
- No pases datos sensibles como parámetros ni los escribas en `proceso.md`. El historial guarda solo los **nombres** de los parámetros y la URL sin consulta, pero las capturas de error (`ultimo-error.png`) pueden mostrar lo que había en la página.
- Trabaja solo en las webs que nombró el usuario, y solo en ventanas abiertas con `abrir`. No uses ni cierres su navegador normal.
- Un `--perfil` con nombre guarda cookies en disco. Dilo al usuario y ofrece `cerrar --borrar-perfil` cuando ya no lo necesite.
- No simules ni falsees resultados: si no pudiste verificar algo, dilo.

## Archivos
- `scripts/motor.mjs`: motor CDP y envoltorio `proceso()`. `scripts/nav.mjs`: tareas puntuales. `scripts/proceso.mjs`: memoria de procesos.
- `borradores/<nombre>/`: procesos en construcción (`ejecutar.mjs`, `proceso.md`, `intentos.jsonl`).
- `procesos/<nombre>/`: **la memoria**: `ejecutar.mjs`, `proceso.md` (ficha con especificación y errores resueltos), `estado.json` (usos y si está roto), `historial.jsonl`, `versiones/` (versiones anteriores).
- `plantillas/`: punto de partida de un proceso nuevo.
- `briefs/brief-proceso.md`: encargo listo para un agente trabajador (construir o ejecutar un proceso en su propio navegador).
- `referencia.md`: API de `Pagina`, formato de un proceso y trampas conocidas.
