// SPDX-License-Identifier: LicenseRef-Proprietary — Copyright (c) 2026 alejandro-xoxo. All rights reserved.
// Copyright (c) 2026 alejandro-xoxo
// Memory for repeatable processes: create a draft, test it until it runs clean, save it, list it and reuse it.
// Usage: node proceso.mjs <command> ...   (with no arguments it shows the help)
// Command names are Spanish (nuevo = new, probar = test, guardar = save, listar = list, ejecutar = run, reparar = repair, borrar = delete).
// Core rule: "guardar" only accepts a draft whose LAST attempt finished well, with verifications, and with an
// ejecutar.mjs exactly identical to the one that was tested. There is no option to skip this.
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
const AYUDA = `Repeatable browser processes. Usage: node proceso.mjs <command> ...
(Command names are Spanish; the English meaning is in parentheses.)

Create (draft) and save
  nuevo (new) <name> "<description>"   creates borradores/<name>/ (drafts) with ejecutar.mjs and proceso.md
  probar (test) <name> [key=value ...] [--confirmo] [--puerto N] [--timeout sec]
                                      runs the draft and records the attempt (steps, verifications, error, screenshot)
  guardar (save) <name>               moves it into memory ONLY if the last attempt ran clean (see rules)
Use what is saved
  listar (list) [--json]              saved processes (with their status) and drafts under construction
  ver (show) <name>                   prints proceso.md
  ejecutar (run) <name> [key=value ...] [--confirmo] [--puerto N] [--timeout sec]
  reparar (repair) <name>             copies a saved process into borradores/ to fix it and save it again
  borrar (delete) <name> --si         deletes a saved process (--si = yes, confirms)
(--confirmo = the user confirms the irreversible steps.)
Parameters can be given as key=value, or with --params '{"key":"value"}', or with --params-archivo path.json.`;

// ---------- utilities ----------
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
const validarNombre = n => { if (!/^[a-z0-9][a-z0-9-]{1,40}$/.test(n || '')) fail('The name must be 2 to 41 characters: lowercase letters, digits and hyphens (e.g. download-statement).'); };
const jsonl = ruta => fs.existsSync(ruta) ? fs.readFileSync(ruta, 'utf8').split('\n').filter(Boolean).map(l => JSON.parse(l)) : [];
const anexar = (ruta, obj) => fs.appendFileSync(ruta, JSON.stringify(obj) + '\n');
const seg = ms => (ms / 1000).toFixed(1) + ' s';

// Section heading that the tool writes at the end of proceso.md. The Spanish form is also recognized, for files written by earlier versions.
const TITULO_HISTORIAL = 'Build history (automatic)';
const RE_HISTORIAL = /\n## (?:Build history \(automatic\)|Historial de construcción \(automático\))[\s\S]*?(?=\n## |$)/;
// Placeholder that proceso.md must not contain when saving (the Spanish form is also recognized).
const PENDIENTE = ['(complete)', '(completar)'];

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
  else if (f.params) { try { p = JSON.parse(f.params); } catch { fail('--params is not valid JSON. In PowerShell it is easier to use key=value or --params-archivo.'); } }
  for (const e of extras) {
    const m = e.match(/^([\w-]+)=([\s\S]*)$/);
    if (!m) fail(`Unrecognized argument: "${e}". Parameters are given as key=value.`);
    p[m[1]] = m[2];
  }
  return p;
}

// File lock: several parallel runs of the same process update estado.json without overwriting each other.
// If a lock was left orphaned (a process died midway), after 3 s it is discarded and we carry on.
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

// Runs the ejecutar.mjs of a folder and returns the RESULTADO (= RESULT) line that motor.mjs prints.
async function correr(dir, { params, confirmo, puerto, timeoutSeg }) {
  if (!(await responde(puerto))) fail(`No browser with debugging on port ${puerto}. Open one with: node nav.mjs abrir${puerto !== 9222 ? ' --puerto ' + puerto : ''}   (if the site asks you to sign in, sign in yourself in that window).`);
  const t0 = Date.now();
  const r = spawnSync(process.execPath, [path.join(dir, 'ejecutar.mjs')], {
    cwd: dir, encoding: 'utf8', timeout: timeoutSeg * 1000, maxBuffer: 20 * 1024 * 1024,
    env: { ...process.env, PROCESO_PARAMS: JSON.stringify(params), NAV_PUERTO: String(puerto), PROCESO_CONFIRMO: confirmo ? '1' : '0', PROCESO_DIR: dir },
  });
  const lineas = (r.stdout || '').split('\n');
  const idx = lineas.map(l => l.startsWith('RESULTADO ')).lastIndexOf(true);
  let res;
  if (idx >= 0) { try { res = JSON.parse(lineas[idx].slice(10)); } catch { /* handled below */ } }
  const salida = lineas.filter((l, i) => i !== idx && l.trim()).slice(-15);
  if (!res) {
    const causa = r.error?.code === 'ETIMEDOUT' ? `Timed out (${timeoutSeg} s)` : ((r.stderr || '').trim().split('\n').slice(-6).join('\n') || 'The script ended without printing RESULTADO');
    res = { estado: 'error', pasos: [], verificaciones: [], irreversibles: [], error: causa, ms: Date.now() - t0 };
  }
  res.salida = salida;
  return res;
}

function imprimir(res, etiqueta) {
  const pasosOk = res.pasos.filter(p => p.ok).length;
  const verOk = res.verificaciones.filter(v => v.ok).length;
  console.log(`${etiqueta} | ${res.estado.toUpperCase()} | steps ${pasosOk}/${res.pasos.length} | verifications ${verOk}/${res.verificaciones.length} | ${seg(res.ms)}`);
  const mal = res.pasos.find(p => !p.ok);
  if (res.estado === 'necesita_confirmacion') console.log(`  stopped before an irreversible step${mal ? ` (in "${mal.titulo}")` : ''}: ${(res.error || '').replace(/^(Irreversible step|Paso irreversible): /, '')}`);
  else if (mal) console.log(`  failed step: "${mal.titulo}" -> ${mal.error}`);
  else if (res.error) console.log(`  ${res.error}`);
  if (res.url) console.log(`  url: ${res.url}`);
  if (res.captura) console.log(`  screenshot: ${res.captura}`);
  if (res.texto) console.log(`  page text: "${res.texto}"`);
  if (res.salida?.length) console.log('  script output:\n    ' + res.salida.join('\n    '));
}

// ---------- commands ----------
function nuevo(nombre, descripcion) {
  validarNombre(nombre);
  if (!descripcion) fail('Missing description. Usage: nuevo <name> "<description>"');
  if (fs.existsSync(path.join(PROCESOS, nombre))) fail(`A saved process "${nombre}" already exists. To fix it use: reparar ${nombre}`);
  const dir = path.join(BORRADORES, nombre);
  if (fs.existsSync(dir)) fail(`The draft "${nombre}" already exists at ${dir}`);
  fs.mkdirSync(dir, { recursive: true });
  const desc = descripcion.replace(/\r?\n/g, ' ');
  const llenar = t => t.replaceAll('__NOMBRE__', () => nombre).replaceAll('__DESCRIPCION__', () => desc).replaceAll('__FECHA__', () => hoy());
  fs.writeFileSync(path.join(dir, 'ejecutar.mjs'), llenar(fs.readFileSync(path.join(PLANTILLAS, 'ejecutar.plantilla.mjs'), 'utf8')));
  fs.writeFileSync(path.join(dir, 'proceso.md'), llenar(fs.readFileSync(path.join(PLANTILLAS, 'proceso.plantilla.md'), 'utf8')));
  console.log(`Draft created at ${dir}\n  1. Write the steps in ejecutar.mjs and fill in proceso.md (remove every "(complete)").\n  2. node proceso.mjs probar ${nombre}   (repeat until it prints OK)\n  3. node proceso.mjs guardar ${nombre}`);
}

async function probar(nombre, extras, f) {
  validarNombre(nombre);
  const dir = path.join(BORRADORES, nombre);
  if (!fs.existsSync(dir)) fail(`The draft "${nombre}" does not exist. Create it with: nuevo ${nombre} "<description>"`);
  const params = leerParams(f, extras);
  const res = await correr(dir, { params, confirmo: !!f.confirmo, puerto: Number(f.puerto || process.env.NAV_PUERTO || 9222), timeoutSeg: Number(f.timeout || 300) });
  const archivo = path.join(dir, 'intentos.jsonl');
  const n = jsonl(archivo).length + 1;
  // The history only stores the parameter NAMES and the URL without its query string: the values may be sensitive data.
  anexar(archivo, { n, fecha: ahora(), hash: hashDe(path.join(dir, 'ejecutar.mjs')), estado: res.estado, ok: res.estado === 'ok', pasos: res.pasos, verificaciones: res.verificaciones.length, irreversibles: res.irreversibles, error: res.error, url: res.url?.split('?')[0], ms: res.ms, parametros: Object.keys(params) });
  imprimir(res, `attempt ${n}`);
  if (res.estado === 'ok') console.log(`  Ready to save: node proceso.mjs guardar ${nombre}`);
  if (res.estado === 'necesita_confirmacion') console.log('  Ask the user whether they authorize that step. If they say yes, repeat with --confirmo.');
  process.exitCode = res.estado === 'ok' ? 0 : 1;
}

function comprobarGuardable(nombre) {
  const dir = path.join(BORRADORES, nombre);
  if (!fs.existsSync(dir)) return { ok: false, motivos: [`The draft "${nombre}" does not exist.`] };
  const intentos = jsonl(path.join(dir, 'intentos.jsonl'));
  const ult = intentos[intentos.length - 1];
  const h = hashDe(path.join(dir, 'ejecutar.mjs'));
  const motivos = [];
  if (!ult) motivos.push(`There is no attempt yet. Run: node proceso.mjs probar ${nombre}`);
  else {
    if (ult.hash !== h) motivos.push('ejecutar.mjs changed after the last attempt. Test it again: what gets saved must be exactly what was tested.');
    if (ult.estado !== 'ok') motivos.push(`The last attempt ended in "${ult.estado}"${ult.error ? ': ' + ult.error.replace(/\.+$/, '') : ''}.`);
    else if (!(ult.verificaciones >= 1)) motivos.push('The last attempt has no verifications.');
  }
  const md = fs.readFileSync(path.join(dir, 'proceso.md'), 'utf8');
  if (PENDIENTE.some(p => md.includes(p))) motivos.push('proceso.md still has "(complete)": describe the parameters, the steps and how the result is verified.');
  return { ok: motivos.length === 0, motivos, intentos, hash: h };
}

function guardar(nombre) {
  validarNombre(nombre);
  const g = comprobarGuardable(nombre);
  if (!g.ok) { console.error(`"${nombre}" was NOT saved:\n` + g.motivos.map(m => '  - ' + m).join('\n')); process.exitCode = 1; return; }
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
  // Errors accumulate across versions: they are the most useful part of the memory (what failed and was solved).
  const errores = [...new Set(jsonl(path.join(destino, 'historial.jsonl'))
    .filter(h => h.estado === 'error' || h.estado === 'sin_verificaciones').map(h => h.error).filter(Boolean))];
  let md = fs.readFileSync(path.join(origen, 'proceso.md'), 'utf8').replace(RE_HISTORIAL, '');
  md = ponerFm(md, 'guardado', hoy());
  md = ponerFm(md, 'hash', g.hash);
  md = md.trimEnd() + `\n\n## ${TITULO_HISTORIAL}\n- Latest version saved on ${hoy()} after ${g.intentos.length} attempt(s), ${fallidos.length} failed.\n` +
    (errores.length ? '- Errors found in this process (while building and while using it):\n' + errores.map(e => `  - ${e}`).join('\n') + '\n' : '- No errors so far.\n') +
    `- Last attempt (successful): ${ult.pasos.length} steps, ${ult.verificaciones} verifications, ${seg(ult.ms)}.\n`;
  fs.writeFileSync(path.join(destino, 'proceso.md'), md);
  const rutaEstado = path.join(destino, 'estado.json');
  const estado = fs.existsSync(rutaEstado) ? JSON.parse(fs.readFileSync(rutaEstado, 'utf8')) : { ejecuciones_ok: 0, ejecuciones_fallidas: 0, ultima: null };
  estado.roto = false; // the new version has just passed the gate
  fs.writeFileSync(rutaEstado, JSON.stringify(estado, null, 1));
  fs.rmSync(origen, { recursive: true, force: true });
  console.log(`Saved "${nombre}" ${existia ? '(new version; the previous one is in versiones/) ' : ''}at ${destino}\n  hash ${g.hash} · ${g.intentos.length} attempt(s) · ${fallidos.length} failed\n  Reuse it with: node proceso.mjs ejecutar ${nombre}`);
}

function listar(f) {
  const guardados = fs.existsSync(PROCESOS) ? fs.readdirSync(PROCESOS).filter(n => fs.existsSync(path.join(PROCESOS, n, 'proceso.md'))) : [];
  const borradores = fs.existsSync(BORRADORES) ? fs.readdirSync(BORRADORES).filter(n => fs.existsSync(path.join(BORRADORES, n, 'proceso.md'))) : [];
  const datos = guardados.map(n => {
    const fm = leerFm(path.join(PROCESOS, n, 'proceso.md'));
    const est = JSON.parse(fs.readFileSync(path.join(PROCESOS, n, 'estado.json'), 'utf8'));
    return { nombre: n, descripcion: fm.descripcion, parametros: fm.parametros || 'none', sitio: fm.sitio, sesion: fm.sesion, guardado: fm.guardado, ...est };
  });
  const enConstruccion = borradores.map(n => {
    const it = jsonl(path.join(BORRADORES, n, 'intentos.jsonl'));
    return { nombre: n, intentos: it.length, ultimo: it.length ? it[it.length - 1].estado : 'untested', descripcion: leerFm(path.join(BORRADORES, n, 'proceso.md')).descripcion };
  });
  if (f.json) { console.log(JSON.stringify({ guardados: datos, en_construccion: enConstruccion }, null, 1)); return; }
  console.log(`SAVED PROCESSES (${datos.length})`);
  if (!datos.length) console.log('  (none yet; create one with: nuevo <name> "<description>")');
  for (const d of datos) {
    const marca = d.roto ? 'BROKEN' : d.ejecuciones_ok + d.ejecuciones_fallidas === 0 ? 'unused' : 'ok';
    console.log(`- ${d.nombre}  [${marca}]  ${d.ejecuciones_ok} ok / ${d.ejecuciones_fallidas} failed · last: ${d.ultima ? d.ultima.fecha.slice(0, 10) + ' ' + d.ultima.estado : 'never'}`);
    console.log(`    ${d.descripcion}`);
    console.log(`    parameters: ${d.parametros} · site: ${d.sitio || '-'} · session: ${d.sesion || '-'}`);
  }
  if (enConstruccion.length) {
    console.log(`\nUNDER CONSTRUCTION (${enConstruccion.length})`);
    for (const b of enConstruccion) console.log(`- ${b.nombre}  ${b.intentos} attempt(s) · last: ${b.ultimo}  — ${b.descripcion}`);
  }
}

function ver(nombre) {
  validarNombre(nombre);
  const ruta = [path.join(PROCESOS, nombre, 'proceso.md'), path.join(BORRADORES, nombre, 'proceso.md')].find(fs.existsSync);
  if (!ruta) fail(`"${nombre}" exists neither as a saved process nor as a draft.`);
  console.log(`(${ruta})\n`); console.log(fs.readFileSync(ruta, 'utf8'));
}

async function ejecutar(nombre, extras, f) {
  validarNombre(nombre);
  const dir = path.join(PROCESOS, nombre);
  if (!fs.existsSync(dir)) fail(`There is no saved process "${nombre}". See the existing ones with: listar`);
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
  if (res.estado === 'necesita_confirmacion') console.log('  Ask the user whether they authorize that step. If they say yes, repeat with --confirmo.');
  if (res.estado !== 'ok' && res.estado !== 'necesita_confirmacion') console.log(`  The process failed. To fix it: node proceso.mjs reparar ${nombre}`);
  process.exitCode = res.estado === 'ok' ? 0 : 1;
}

function reparar(nombre) {
  validarNombre(nombre);
  const origen = path.join(PROCESOS, nombre);
  if (!fs.existsSync(origen)) fail(`There is no saved process "${nombre}".`);
  const dir = path.join(BORRADORES, nombre);
  if (fs.existsSync(dir)) fail(`A draft "${nombre}" already exists. Finish it or delete it first.`);
  fs.mkdirSync(dir, { recursive: true });
  fs.copyFileSync(path.join(origen, 'ejecutar.mjs'), path.join(dir, 'ejecutar.mjs'));
  fs.copyFileSync(path.join(origen, 'proceso.md'), path.join(dir, 'proceso.md'));
  console.log(`Copied to ${dir}. The saved one stays untouched until "guardar" accepts the fix.\n  Fix ejecutar.mjs, repeat: probar ${nombre} (until OK) and then: guardar ${nombre}`);
}

function borrar(nombre, f) {
  validarNombre(nombre);
  const dir = path.join(PROCESOS, nombre);
  if (!fs.existsSync(dir)) fail(`There is no saved process "${nombre}".`);
  if (!f.si) fail(`This deletes the saved process "${nombre}" together with its history. Confirm by repeating the command with --si.`);
  fs.rmSync(dir, { recursive: true, force: true });
  console.log(`Deleted "${nombre}".`);
}

// ---------- entry point ----------
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
  else { console.error(`Unknown command: ${cmd}\n`); console.error(AYUDA); process.exitCode = 1; }
} catch (e) {
  console.error('ERROR:', e.message);
  process.exitCode = 1;
}
const codigo = process.exitCode || 0;
process.stderr.write('', () => process.stdout.write('', () => process.exit(codigo)));
