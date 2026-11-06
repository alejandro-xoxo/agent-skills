// Process: __NOMBRE__
// Test it with:  node proceso.mjs probar __NOMBRE__ [key=value ...]
// Parameters arrive in `params`. `pagina` is a new tab that belongs to the process alone (closed when it ends).
// Write the steps, and at the end check the REAL result with verificar(...): the absence of errors is not enough.
import { proceso } from '../../scripts/motor.mjs';

await proceso('__NOMBRE__', async ({ pagina, params, paso, verificar, irreversible }) => {
  await paso('Open the page', async () => {
    await pagina.ir(params.url || 'https://example.com');
  });

  // More steps. Give each step a clear title so the error says where it failed. Available actions
  // (ir = goto, esperar = wait, clic = click, escribir = type, seleccionar = select, tecla = key, subir = upload,
  //  leer = read, captura = screenshot, evaluar = evaluate JavaScript):
  //   pagina.esperar('texto=Save')   pagina.clic('#button')   pagina.escribir('input[name=q]', 'hello')
  //   pagina.seleccionar('select#month', 'October')   pagina.tecla('Enter')   pagina.subir('#file', path)
  //   pagina.leer('#result')   pagina.captura('output.png')   pagina.evaluar('document.title')
  //
  // Before anything that cannot be undone (send, pay, delete, publish):
  //   irreversible('Submit the payment form');

  await paso('Check the result', async () => {
    const texto = await pagina.leer();
    verificar(texto.length > 0, 'The page has content');
  });
});
