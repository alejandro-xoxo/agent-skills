// Proceso: __NOMBRE__
// Se prueba con:  node proceso.mjs probar __NOMBRE__ [clave=valor ...]
// Los parámetros llegan en `params`. `pagina` es una pestaña nueva y propia del proceso (se cierra al terminar).
// Escribe los pasos, y al final comprueba el resultado REAL con verificar(...): que no haya errores no basta.
import { proceso } from '../../scripts/motor.mjs';

await proceso('__NOMBRE__', async ({ pagina, params, paso, verificar, irreversible }) => {
  await paso('Abrir la página', async () => {
    await pagina.ir(params.url || 'https://example.com');
  });

  // Más pasos. Cada paso con un título claro, para que el error diga dónde falló. Acciones disponibles:
  //   pagina.esperar('texto=Guardar')   pagina.clic('#boton')   pagina.escribir('input[name=q]', 'hola')
  //   pagina.seleccionar('select#mes', 'Octubre')   pagina.tecla('Enter')   pagina.subir('#archivo', ruta)
  //   pagina.leer('#resultado')   pagina.captura('salida.png')   pagina.evaluar('document.title')
  //
  // Antes de algo que no se puede deshacer (enviar, pagar, borrar, publicar):
  //   irreversible('Enviar el formulario de pago');

  await paso('Comprobar el resultado', async () => {
    const texto = await pagina.leer();
    verificar(texto.length > 0, 'La página tiene contenido');
  });
});
