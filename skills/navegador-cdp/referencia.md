# Referencia técnica

## Requisitos y alcance probado
- Node 22 o superior (usa `fetch` y `WebSocket` incluidos) y Chrome o Edge instalados.
- **Probado en Windows con Edge y con Chrome 156** (con y sin ventana visible): abrir, ir, leer, esperar, clic (CSS, texto y coordenadas), clic derecho, escribir, seleccionar, Enter, Ctrl+A, subir archivos, captura y cerrar; todo el ciclo de procesos (fallar, corregir, guardar, reutilizar, reparar, compuertas), incluido uno contra un sitio real; un perfil persistente cuya cookie sobrevive a cerrar y reabrir; y Chrome y Edge abiertos a la vez, aislados entre sí.
- **Sin probar**: iniciar sesión en un sitio real (siempre lo hace el usuario a mano; Google puede bloquearlo), macOS y Linux (el código tiene rutas y `pkill` previstos, pero no se han ejecutado) y navegadores que no sean Chromium.
- `cerrar` primero cierra el navegador con normalidad (`Browser.close`, unos 4 s) para que guarde cookies y sesión, y solo fuerza lo que quede vivo. Matarlo de golpe perdía las cookies recientes de un perfil persistente.

## Comandos de `nav.mjs`
`node nav.mjs ayuda` imprime la lista completa. Un **objetivo** es un selector CSS, `texto=Guardar` o `x,y`. Con `texto=`, gana el elemento visible más interno cuyo texto coincide (primero el idéntico, luego los que son botones, enlaces o campos, luego el más corto).

## API de `Pagina` (para escribir `ejecutar.mjs`)
En un proceso, `pagina` ya llega abierta en una pestaña nueva y propia, que se cierra al terminar.

| Método | Qué hace |
|---|---|
| `ir(url)` | Navega y espera a que cargue. En páginas que cargan por partes, añade `esperar(...)` |
| `esperar(objetivo, ms=15000)` | Espera a que exista; falla con un mensaje claro si no |
| `existe(objetivo)` | `true` o `false` sin esperar |
| `clic(objetivo, {derecho, doble})` | Mueve y pulsa con eventos de ratón reales, tras centrar el elemento |
| `escribir(objetivo, texto)` | Reemplaza el contenido del campo; texto vacío lo borra |
| `seleccionar(objetivo, valor)` | Elige una opción de un `<select>` por valor o por texto |
| `tecla('Enter')` | También `Tab`, `Escape`, `Backspace`, `Delete`, flechas, `Ctrl+A`, `Shift+Tab`... |
| `leer(objetivo?)` | Texto del elemento (o valor del campo); sin objetivo, todo el texto de la página |
| `html(objetivo?)` | HTML del elemento o de la página |
| `evaluar(js)` | Ejecuta JavaScript en la página y devuelve el valor (admite promesas) |
| `subir(objetivo, rutas)` | Pulsa el botón o el `<input type=file>` y rellena el selector de archivos |
| `captura(ruta, {completa})` | Guarda un PNG |
| `url()`, `titulo()` | Dirección y título actuales |

Dentro de `proceso(nombre, async ({ pagina, params, paso, verificar, irreversible, carpeta }) => { ... })`:
- `params`: parámetros que llegan por `clave=valor`.
- `paso('título', async () => {...})`: registra el paso; si falla, el resultado dice cuál.
- `verificar(condición, 'qué demuestra')`: obligatorio al menos una; si es falsa, el proceso falla.
- `irreversible('descripción')`: detiene el proceso con código 10 salvo que se ejecute con `--confirmo`.
- `carpeta`: carpeta del proceso, por si necesita guardar archivos de salida.

Códigos de salida del script: `0` bien, `1` error, `3` sin verificaciones, `10` paso irreversible sin confirmar.

## Formato de un proceso guardado
`procesos/<nombre>/proceso.md` empieza con una cabecera de una línea por campo: `nombre`, `descripcion`, `sitio`, `sesion`, `parametros` (nombres separados por comas), `creado`, `guardado`, `hash`. `listar` lee esa cabecera. Al final lleva un bloque automático "Historial de construcción" con los errores que se han encontrado, que se acumulan entre versiones: es la parte más útil de la memoria.

`estado.json` cuenta usos correctos y fallidos y marca `roto` cuando la última ejecución falló. `guardar` lo pone en `false` al aceptar una versión corregida.

## Trampas conocidas
- **PowerShell y comillas.** Pasar JSON o textos con comillas dobles a un programa se rompe fácil. Usa `clave=valor` para los parámetros, o `--params-archivo ruta.json`, y para `eval` prefiere comillas simples dentro del JavaScript.
- **Procesos en segundo plano.** Algunas herramientas de agente matan los procesos lanzados con `Start-Job` al terminar el comando. Si necesitas algo en segundo plano, usa la opción de ejecución en segundo plano de la propia herramienta. Los comandos de esta skill terminan solos y no lo necesitan.
- **Coordenadas.** El tamaño de la ventana cambia el diseño, y con él las coordenadas. Usa selectores o `texto=`.
- **Inicio de sesión de Google.** A veces bloquea el acceso en navegadores con depuración remota ("este navegador no es seguro"). Si pasa, para y avisa al usuario; no intentes rodearlo.
- **Selector de archivos.** Los `<input type=file>` suelen estar ocultos: pulsa el botón que los abre (o el propio input) con `subir`, no uses `escribir`.
- **Texto repetido.** Si un contenedor y su botón tienen el mismo texto, `texto=` ya elige el más interno; si falla, usa un selector CSS.
- **Menús y ventanas emergentes.** Si algo abre una pestaña nueva, mírala con `pestanas` y trabaja con `--tab`. Los diálogos del navegador (`alert`, `confirm`) no están soportados y pueden bloquear la página.
- **`iframe`.** Los selectores no entran en ellos. Para mismo origen, usa `evaluar` con `document.querySelector('iframe').contentDocument`.
- **Sitios dinámicos.** `ir` solo espera a la carga inicial. Antes de leer o pulsar, `esperar` lo que debe aparecer.
- **Capturas de error.** `ultimo-error.png` queda en la carpeta del borrador, o en la del proceso guardado si falló una ejecución. Puede mostrar datos de la página.
- **Varios navegadores a la vez.** Un puerto y un perfil por ventana (`--puerto 9223 --perfil otra-cuenta`). Todos los comandos aceptan `--puerto`, y `NAV_PUERTO` fija el valor por defecto. Hacen falta solo con cuentas distintas: para el mismo usuario es mejor **un solo navegador con una pestaña por tarea**.
- **Varias tareas en un mismo navegador.** Cada ejecución de `proceso.mjs` (`probar` o `ejecutar`) abre su propia pestaña y la cierra al terminar, así que puedes lanzar varias a la vez contra el mismo puerto. Con `nav.mjs` y más de una pestaña abierta hay que indicar `--tab <id>` (la pestaña nueva la crea `nueva <url>`, que imprime su id). Las pestañas comparten cookies y sesión: eso evita iniciar sesión varias veces, pero un sitio que guarde estado por sesión (carrito, "elemento actual") puede mezclar tareas.
- **Qué se probó con varias ejecuciones a la vez** (Chrome, página local con una espera de 1,2 s): 4, 12 y 20 simultáneas, todas correctas; `estado.json` y el historial quedaron con el recuento exacto gracias a un bloqueo por archivo; las pestañas se cerraron solas. En paralelo cada ejecución se alarga (de 1,6 s a unos 7 s con 20), así que hay un tope práctico. Si hay fallos simultáneos del mismo proceso, `ultimo-error.png` corresponde al último que falló.
