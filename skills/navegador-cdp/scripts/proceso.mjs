// SPDX-License-Identifier: LicenseRef-Proprietary — Copyright (c) 2026 alejandro-xoxo. All rights reserved.
// Copyright (c) 2026 alejandro-xoxo
// Memoria de procesos repetitivos: crear un borrador, probarlo hasta que salga limpio, guardarlo, listarlo y reutilizarlo.
// Uso: node proceso.mjs <comando> ...   (sin argumentos muestra la ayuda)
// Regla central: "guardar" solo acepta un borrador cuyo ÚLTIMO intento terminó bien, con verificaciones, y con el
// ejecutar.mjs exactamente igual al que se probó. No hay opción para saltarse esto.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { responde } from './motor.mjs';

const RAIZ = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const BORRADORES = path.join(RAIZ, 'borradores');
const PROCESOS = path.join(RAIZ, 'procesos');
const PLANTILLAS = path.join(RAIZ, 'plantillas');
const BOOLEANAS = new Set(['json', 'confirmo', 'si']);
const AYUDA = `Procesos repetitivos del navegador. Uso: node proceso.mjs <comando> ...

Crear (borrador) y guardar
  nuevo <nombre> "<descripcion>"      crea borradores/<nombre>/ con ejecutar.mjs y proceso.md
  probar <nombre> [clave=valor ...] [--confirmo] [--puerto N] [--timeout seg]
                                      ejecuta el borrador y anota el intento (pasos, verificaciones, error, captura)
  guardar <nombre>                    lo pasa a la memoria SOLO si el último intento salió limpio (ver reglas)
Usar lo guardado
  listar [--json]                     procesos guardados (con su estado) y borradores en construcción
  ver <nombre>                        muestra proceso.md
  ejecutar <nombre> [clave=valor ...] [--confirmo] [--puerto N] [--timeout seg]
  reparar <nombre>                    copia un proceso guardado a borradores/ para corregirlo y volver a guardarlo
  borrar <nombre> --si                elimina un proceso guardado
Los parámetros pueden ir como clave=valor, o con --params '{"clave":"valor"}', o con --params-archivo ruta.json.`;

// ---------- utilidades ----------
function parsear(argv) {
  const pos = [], f = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith('--')) {
      const k = a.slice(2);
      if (BOOLEANAS.has(k) || argv[i + 1] === undefined || argv[i + 1].startsWith('--')) f[k] = true; else f[k] = argv[++i];
    } else pos.push(a);
  }
  return { pos, f };
}
const fail = m => { throw new Error(m); };
const hoy = () => new Date().toISOString().slice(0, 10);
const ahora = () => new Date().toISOString();
const hashDe = ruta => crypto.createHash('sha256').update(fs.readFileSync(ruta)).digest('hex').slice(0, 12);
const validarNombre = n => { if (!/^[a-z0-9][a-z0-9-]{1,40}$/.test(n || '')) fail('El nombre debe tener 2 a 41 caracteres: minúsculas, números y guiones (ej. descargar-extracto).'); };
const jsonl = ruta => fs.existsSync(ruta) ? fs.readFileSync(ruta, 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l)) : [];
const anexar = (ruta, obj) => fs.appendFileSync(ruta, JSON.stringify(obj) + '\n');
const seg = ms => (ms / 1000).toFixed(1) + ' s';

function leerFm(ruta) {
  const t = fs.readFileSync(ruta, 'utf8');
  const m = t.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  const fm = {};
  if (m) for (const l of m[1].split(/\r?\n/)) { const k = l.match(/^([a-zA-Z_]+):\s*(.*)$/); if (k) fm[k[1]] = k[2].trim(); }
  return fm;
}
function ponerFm(texto, clave, valor) {
  const m = texto.match(/^(---\r?\n)([\s\S]*?)(\r?\n---)/);
  if (!m) return texto;
  const linea = `${clave}: ${valor}`;
  const re = new RegExp(`^${clave}:.*$`, 'm');
  const cuerpo = re.test(m[2]) ? m[2].replace(re, linea) : m[2] + '\n' + linea;
  return texto.replace(m[0], () => m[1] + cuerpo + m[3]);
}

function leerParams(f, extras) {
  let p = {};
  if (f['params-archivo']) p = JSON.parse(fs.readFileSync(f['params-archivo'], 'utf8'));
  else if (f.params) { try { p = JSON.parse(f.params); } catch { fail('--params no es JSON válido. En PowerShell es más fácil usar clave=valor o --params-archivo.'); } }
  for (const e of extras) {
    const m = e.match(/^([\w-]+)=([\s\S]*)$/);
    if (!m) fail(`Argumento no reconocido: "${e}". Los parámetros van como clave=valor.`);
    p[m[1]] = m[2];
  }
  return p;
}

// Bloqueo con archivo: varias ejecuciones en paralelo del mismo proceso actualizan estado.json sin pisarse.
// Si un bloqueo quedó huérfano (un proceso murió a mitad), a los 3 s se descarta y se sigue.
async function conBloqueo(ruta, fn) {
  const lock = ruta + '.lock';
  const fin = Date.now() + 3000;
  let fd = null;
  while (fd === null) {
    try { fd = fs.openSync(lock, 'wx'); }
    catch {
      if (Date.now() > fin) fs.rmSync(lock, { force: true });
      else await new Promise(r => setTimeout(r, 25 + Math.random() * 25));
    }
  }
  try { return fn(); } finally { fs.closeSync(fd); fs.rmSync(lock, { force: true }); }
}

// Ejecuta ejecutar.mjs de una carpeta y devuelve el RESULTADO que imprime motor.mjs.
async function correr(dir, { params, confirmo, puerto, timeoutSeg }) {
  if (!(await responde(puerto))) fail(`No hay navegador con depuración en el puerto ${puerto}. Ábrelo con: node nav.mjs abrir${puerto !== 9222 ? ' --puerto ' + puerto : ''}   (si el sitio pide sesión, inicia sesión tú en esa ventana).`);
  const t0 = Date.now();
  const r = spawnSync(process.execPath, [path.join(dir, 'ejecutar.mjs')], {
    cwd: dir, encoding: 'utf8', timeout: timeoutSeg * 1000, maxBuffer: 20 * 1024 * 1024,
    env: { ...process.env, PROCESO_PARAMS: JSON.stringify(params), NAV_PUERTO: String(puerto), PROCESO_CONFIRMO: confirmo ? '1' : '0', PROCESO_DIR: dir },
  });
  const lineas = (r.stdout || '').split('\n');
  const idx = lineas.map(l => l.startsWith('RESULTADO ')).lastIndexOf(true);
  let res;
  if (idx >= 0) { try { res = JSON.parse(lineas[idx].slice(10)); } catch { /* se trata abajo */ } }
  const salida = lineas.filter((l, i) => i !== idx && l.trim()).slice(-15);
  if (!res) {
    const causa = r.error?.code === 'ETIMEDOUT' ? `Se agotó el tiempo (${timeoutSeg} s)` : ((r.stderr || '').trim().split('\n').slice(-6).join('\n') || 'El script terminó sin imprimir RESULTADO');
    res = { estado: 'error', pasos: [], verificaciones: [], irreversibles: [], error: causa, ms: Date.now() - t0 };
  }
  res.salida = salida;
  return res;
}

function imprimir(res, etiqueta) {
  const pasosOk = res.pasos.filter(p => p.ok).length;
  const verOk = res.verificaciones.filter(v => v.ok).length;
  console.log(`${etiqueta} | ${res.estado.toUpperCase()} | pasos ${pasosOk}/${res.pasos.length} | verificaciones ${verOk}/${res.verificaciones.length} | ${seg(res.ms)}`);
  const mal = res.pasos.find(p => !p.ok);
  if (res.estado === 'necesita_confirmacion') console.log(`  detenido antes de un paso irreversible${mal ? ` (en "${mal.titulo}")` : ''}: ${(res.error || '').replace('Paso irreversible: ', '')}`);
  else if (mal) console.log(`  paso fallido: "${mal.titulo}" -> ${mal.error}`);
  else if (res.error) console.log(`  ${res.error}`);
  if (res.url) console.log(`  url: ${res.url}`);
  if (res.captura) console.log(`  captura: ${res.captura}`);
  if (res.texto) console.log(`  texto de la página: "${res.texto}"`);
  if (res.salida?.length) console.log('  salida del script:\n    ' + res.salida.join('\n    '));
}

// ---------- comandos ----------
function nuevo(nombre, descripcion) {
  validarNombre(nombre);
  if (!descripcion) fail('Falta la descripción. Uso: nuevo <nombre> "<descripcion>"');
  if (fs.existsSync(path.join(PROCESOS, nombre))) fail(`Ya existe un proceso guardado "${nombre}". Para corregirlo usa: reparar ${nombre}`);
  const dir = path.join(BORRADORES, nombre);
  if (fs.existsSync(dir)) fail(`Ya existe el borrador "${nombre}" en ${dir}`);
  fs.mkdirSync(dir, { recursive: true });
  const desc = descripcion.replace(/\r?\n/g, ' ');
  const llenar = t => t.replaceAll('__NOMBRE__', () => nombre).replaceAll('__DESCRIPCION__', () => desc).replaceAll('__FECHA__', () => hoy());
  fs.writeFileSync(path.join(dir, 'ejecutar.mjs'), llenar(fs.readFileSync(path.join(PLANTILLAS, 'ejecutar.plantilla.mjs'), 'utf8')));
  fs.writeFileSync(path.join(dir, 'proceso.md'), llenar(fs.readFileSync(path.join(PLANTILLAS, 'proceso.plantilla.md'), 'utf8')));
  console.log(`Borrador creado en ${dir}\n  1. Escribe los pasos en ejecutar.mjs y rellena proceso.md (quita todos los "(completar)").\n  2. node proceso.mjs probar ${nombre}   (repite hasta que salga OK)\n  3. node proceso.mjs guardar ${nombre}`);
}

async function probar(nombre, extras, f) {
  validarNombre(nombre);
  const dir = path.join(BORRADORES, nombre);
  if (!fs.existsSync(dir)) fail(`No existe el borrador "${nombre}". Créalo con: nuevo ${nombre} "<descripcion>"`);
  const params = leerParams(f, extras);
  const res = await correr(dir, { params, confirmo: !!f.confirmo, puerto: Number(f.puerto || process.env.NAV_PUERTO || 9222), timeoutSeg: Number(f.timeout || 300) });
  const archivo = path.join(dir, 'intentos.jsonl');
  const n = jsonl(archivo).length + 1;
  // En el historial solo se guardan los NOMBRES de los parámetros y la URL sin consulta: los valores pueden ser datos sensibles.
  anexar(archivo, { n, fecha: ahora(), hash: hashDe(path.join(dir, 'ejecutar.mjs')), estado: res.estado, ok: res.estado === 'ok', pasos: res.pasos, verificaciones: res.verificaciones.length, irreversibles: res.irreversibles, error: res.error, url: res.url?.split('?')[0], ms: res.ms, parametros: Object.keys(params) });
  imprimir(res, `intento ${n}`);
  if (res.estado === 'ok') console.log(`  Listo para guardar: node proceso.mjs guardar ${nombre}`);
  if (res.estado === 'necesita_confirmacion') console.log('  Pregunta al usuario si autoriza ese paso. Si dice que sí, repite con --confirmo.');
  process.exitCode = res.estado === 'ok' ? 0 : 1;
}

function comprobarGuardable(nombre) {
  const dir = path.join(BORRADORES, nombre);
  if (!fs.existsSync(dir)) return { ok: false, motivos: [`No existe el borrador "${nombre}".`] };
  const intentos = jsonl(path.join(dir, 'intentos.jsonl'));
  const ult = intentos[intentos.length - 1];
  const h = hashDe(path.join(dir, 'ejecutar.mjs'));
  const motivos = [];
  if (!ult) motivos.push(`Todavía no hay ningún intento. Ejecuta: node proceso.mjs probar ${nombre}`);
  else {
    if (ult.hash !== h) motivos.push('ejecutar.mjs cambió después del último intento. Vuelve a probarlo: lo que se guarda debe ser exactamente lo que se probó.');
    if (ult.estado !== 'ok') motivos.push(`El último intento terminó en "${ult.estado}"${ult.error ? ': ' + ult.error.replace(/\.+$/, '') : ''}.`);
    else if (!(ult.verificaciones >= 1)) motivos.push('El último intento no tiene verificaciones.');
  }
  if (fs.readFileSync(path.join(dir, 'proceso.md'), 'utf8').includes('(completar)')) motivos.push('proceso.md todavía tiene "(completar)": describe parámetros, pasos y cómo se verifica el resultado.');
  return { ok: motivos.length === 0, motivos, intentos, hash: h };
}

function guardar(nombre) {
  validarNombre(nombre);
  const g = comprobarGuardable(nombre);
  if (!g.ok) { console.error(`NO se guardó "${nombre}":\n` + g.motivos.map(m => '  - ' + m).join('\n')); process.exitCode = 1; return; }
  const origen = path.join(BORRADORES, nombre);
  const destino = path.join(PROCESOS, nombre);
  const existia = fs.existsSync(destino);
  fs.mkdirSync(destino, { recursive: true });
  if (existia && fs.existsSync(path.join(destino, 'ejecutar.mjs'))) {
    fs.mkdirSync(path.join(destino, 'versiones'), { recursive: true });
    fs.copyFileSync(path.join(destino, 'ejecutar.mjs'), path.join(destino, 'versiones', `ejecutar-${hashDe(path.join(destino, 'ejecutar.mjs'))}.mjs`));
  }
  fs.copyFileSync(path.join(origen, 'ejecutar.mjs'), path.join(destino, 'ejecutar.mjs'));

  const ult = g.intentos[g.intentos.length - 1];
  const fallidos = g.intentos.filter(i => !i.ok);
  for (const i of g.intentos) anexar(path.join(destino, 'historial.jsonl'), { ...i, origen: 'construccion' });
  // Los errores se acumulan entre versiones: son la parte más útil de la memoria (qué falló y se resolvió).
  const errores = [...new Set(jsonl(path.join(destino, 'historial.jsonl'))
    .filter(h => h.estado === 'error' || h.estado === 'sin_verificaciones').map(h => h.error).filter(Boolean))];
  let md = fs.readFileSync(path.join(origen, 'proceso.md'), 'utf8').replace(/\n## Historial de construcción \(automático\)[\s\S]*?(?=\n## |$)/, '');
  md = ponerFm(md, 'guardado', hoy());
  md = ponerFm(md, 'hash', g.hash);
  md = md.trimEnd() + `\n\n## Historial de construcción (automático)\n- Última versión guardada el ${hoy()} tras ${g.intentos.length} intento(s), ${fallidos.length} fallido(s).\n` +
    (errores.length ? '- Errores que se han encontrado en este proceso (construcción y uso):\n' + errores.map(e => `  - ${e}`).join('\n') + '\n' : '- No ha habido errores hasta ahora.\n') +
    `- Último intento (correcto): ${ult.pasos.length} pasos, ${ult.verificaciones} verificaciones, ${seg(ult.ms)}.\n`;
  fs.writeFileSync(path.join(destino, 'proceso.md'), md);
  const rutaEstado = path.join(destino, 'estado.json');
  const estado = fs.existsSync(rutaEstado) ? JSON.parse(fs.readFileSync(rutaEstado, 'utf8')) : { ejecuciones_ok: 0, ejecuciones_fallidas: 0, ultima: null };
  estado.roto = false; // la versión nueva acaba de pasar la compuerta
  fs.writeFileSync(rutaEstado, JSON.stringify(estado, null, 1));
  fs.rmSync(origen, { recursive: true, force: true });
  console.log(`Guardado "${nombre}" ${existia ? '(versión nueva; la anterior quedó en versiones/) ' : ''}en ${destino}\n  hash ${g.hash} · ${g.intentos.length} intento(s) · ${fallidos.length} fallido(s)\n  Reutilízalo con: node proceso.mjs ejecutar ${nombre}`);
}

function listar(f) {
  const guardados = fs.existsSync(PROCESOS) ? fs.readdirSync(PROCESOS).filter(n => fs.existsSync(path.join(PROCESOS, n, 'proceso.md'))) : [];
  const borradores = fs.existsSync(BORRADORES) ? fs.readdirSync(BORRADORES).filter(n => fs.existsSync(path.join(BORRADORES, n, 'proceso.md'))) : [];
  const datos = guardados.map(n => {
    const fm = leerFm(path.join(PROCESOS, n, 'proceso.md'));
    const est = JSON.parse(fs.readFileSync(path.join(PROCESOS, n, 'estado.json'), 'utf8'));
    return { nombre: n, descripcion: fm.descripcion, parametros: fm.parametros || 'ninguno', sitio: fm.sitio, sesion: fm.sesion, guardado: fm.guardado, ...est };
  });
  const enConstruccion = borradores.map(n => {
    const it = jsonl(path.join(BORRADORES, n, 'intentos.jsonl'));
    return { nombre: n, intentos: it.length, ultimo: it.length ? it[it.length - 1].estado : 'sin probar', descripcion: leerFm(path.join(BORRADORES, n, 'proceso.md')).descripcion };
  });
  if (f.json) { console.log(JSON.stringify({ guardados: datos, en_construccion: enConstruccion }, null, 1)); return; }
  console.log(`PROCESOS GUARDADOS (${datos.length})`);
  if (!datos.length) console.log('  (ninguno todavía; crea uno con: nuevo <nombre> "<descripcion>")');
  for (const d of datos) {
    const marca = d.roto ? 'ROTO' : d.ejecuciones_ok + d.ejecuciones_fallidas === 0 ? 'sin usar' : 'ok';
    console.log(`- ${d.nombre}  [${marca}]  ${d.ejecuciones_ok} ok / ${d.ejecuciones_fallidas} fallos · última: ${d.ultima ? d.ultima.fecha.slice(0, 10) + ' ' + d.ultima.estado : 'nunca'}`);
    console.log(`    ${d.descripcion}`);
    console.log(`    parámetros: ${d.parametros} · sitio: ${d.sitio || '-'} · sesión: ${d.sesion || '-'}`);
  }
  if (enConstruccion.length) {
    console.log(`\nEN CONSTRUCCIÓN (${enConstruccion.length})`);
    for (const b of enConstruccion) console.log(`- ${b.nombre}  ${b.intentos} intento(s) · último: ${b.ultimo}  — ${b.descripcion}`);
  }
}

function ver(nombre) {
  validarNombre(nombre);
  const ruta = [path.join(PROCESOS, nombre, 'proceso.md'), path.join(BORRADORES, nombre, 'proceso.md')].find(fs.existsSync);
  if (!ruta) fail(`No existe "${nombre}" ni guardado ni como borrador.`);
  console.log(`(${ruta})\n`); console.log(fs.readFileSync(ruta, 'utf8'));
}

async function ejecutar(nombre, extras, f) {
  validarNombre(nombre);
  const dir = path.join(PROCESOS, nombre);
  if (!fs.existsSync(dir)) fail(`No hay un proceso guardado "${nombre}". Mira los que hay con: listar`);
  const params = leerParams(f, extras);
  const res = await correr(dir, { params, confirmo: !!f.confirmo, puerto: Number(f.puerto || process.env.NAV_PUERTO || 9222), timeoutSeg: Number(f.timeout || 300) });
  const ruta = path.join(dir, 'estado.json');
  await conBloqueo(ruta, () => {
    const est = JSON.parse(fs.readFileSync(ruta, 'utf8'));
    if (res.estado === 'ok') { est.ejecuciones_ok++; est.roto = false; }
    else if (res.estado !== 'necesita_confirmacion') { est.ejecuciones_fallidas++; est.roto = true; }
    est.ultima = { fecha: ahora(), estado: res.estado, ms: res.ms, error: res.error || undefined };
    fs.writeFileSync(ruta, JSON.stringify(est, null, 1));
  });
  anexar(path.join(dir, 'historial.jsonl'), { fecha: ahora(), origen: 'uso', estado: res.estado, ms: res.ms, error: res.error, parametros: Object.keys(params) });
  imprimir(res, nombre);
  if (res.estado === 'necesita_confirmacion') console.log('  Pregunta al usuario si autoriza ese paso. Si dice que sí, repite con --confirmo.');
  if (res.estado !== 'ok' && res.estado !== 'necesita_confirmacion') console.log(`  El proceso falló. Para corregirlo: node proceso.mjs reparar ${nombre}`);
  process.exitCode = res.estado === 'ok' ? 0 : 1;
}

function reparar(nombre) {
  validarNombre(nombre);
  const origen = path.join(PROCESOS, nombre);
  if (!fs.existsSync(origen)) fail(`No hay un proceso guardado "${nombre}".`);
  const dir = path.join(BORRADORES, nombre);
  if (fs.existsSync(dir)) fail(`Ya hay un borrador "${nombre}". Termínalo o bórralo antes.`);
  fs.mkdirSync(dir, { recursive: true });
  fs.copyFileSync(path.join(origen, 'ejecutar.mjs'), path.join(dir, 'ejecutar.mjs'));
  fs.copyFileSync(path.join(origen, 'proceso.md'), path.join(dir, 'proceso.md'));
  console.log(`Copiado a ${dir}. El guardado sigue intacto hasta que "guardar" acepte la corrección.\n  Corrige ejecutar.mjs, repite: probar ${nombre} (hasta OK) y luego: guardar ${nombre}`);
}

function borrar(nombre, f) {
  validarNombre(nombre);
  const dir = path.join(PROCESOS, nombre);
  if (!fs.existsSync(dir)) fail(`No hay un proceso guardado "${nombre}".`);
  if (!f.si) fail(`Esto elimina el proceso guardado "${nombre}" con su historial. Confírmalo repitiendo el comando con --si.`);
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(`Eliminado "${nombre}".`);
}

// ---------- entrada ----------
try {
  const { pos, f } = parsear(process.argv.slice(2));
  const [cmd, nombre, ...resto] = pos;
  if (!cmd || cmd === 'ayuda') console.log(AYUDA);
  else if (cmd === 'nuevo') nuevo(nombre, resto.join(' '));
  else if (cmd === 'probar') await probar(nombre, resto, f);
  else if (cmd === 'guardar') guardar(nombre);
  else if (cmd === 'listar') listar(f);
  else if (cmd === 'ver') ver(nombre);
  else if (cmd === 'ejecutar') await ejecutar(nombre, resto, f);
  else if (cmd === 'reparar') reparar(nombre);
  else if (cmd === 'borrar') borrar(nombre, f);
  else { console.error(`Comando desconocido: ${cmd}\n`); console.error(AYUDA); process.exitCode = 1; }
} catch (e) {
  console.error('ERROR:', e.message);
  process.exitCode = 1;
}
const codigo = process.exitCode || 0;
process.stderr.write('', () => process.stdout.write('', () => process.exit(codigo)));
