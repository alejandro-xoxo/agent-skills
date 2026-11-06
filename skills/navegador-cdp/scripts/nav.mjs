// SPDX-License-Identifier: LicenseRef-Proprietary — Copyright (c) 2026 alejandro-xoxo. All rights reserved.
// Copyright (c) 2026 alejandro-xoxo
// One-off browser control from the command line. Each command prints little and fails with a clear message.
// Usage: node nav.mjs <command> [arguments] [--puerto 9222] [--tab <id>]
// Note: command names and flags are in Spanish (abrir = open, leer = read, clic = click, ...); the help text translates them.
import { lanzar, cerrarNavegador, abiertos, responde, pestanas, Pagina } from './motor.mjs';

const BOOLEANAS = new Set(['headless', 'borrar-perfil', 'completa', 'derecho', 'doble']);
const AYUDA = `Browser control over CDP (no extensions). Usage: node nav.mjs <command> [args] [--puerto 9222] [--tab <id>]
(Command and flag names are Spanish; the English meaning is in parentheses.)

Browser
  abrir (open) [--url U] [--navegador edge|chrome] [--perfil name] [--headless] [--puerto N]
        Without --perfil (profile) the profile is temporary (deleted on close). With --perfil the session is kept between uses.
  estado (status)             browsers opened by this skill and their tabs
  cerrar (close) [--borrar-perfil]    closes the browser on that port (temporary ones delete their profile)
Tabs
  pestanas (tabs) | nueva (new) <url> | cerrar-pestana (close-tab) <id>
On a tab (--tab <id> or the TID variable; if there is only one tab, that one is used)
  ir (goto) <url> | url | titulo (title)
  leer (read) [target] | html [target] | eval "<js>"
  captura (screenshot) <file.png> [--completa (full page)]
  esperar (wait) <target> [--ms 15000]
  clic (click) <target> [--derecho (right)] [--doble (double)]
  escribir (type) <target> "<text>" | seleccionar (select) <target> "<value>"
  tecla (key) <Enter|Tab|Escape|Ctrl+A|...>
  subir (upload) <target-that-opens-the-file-chooser> <file> [file...]
Target = CSS selector, texto=Save (visible element with that text) or x,y coordinates.`;

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

const { pos, f } = parsear(process.argv.slice(2));
const [cmd, ...a] = pos;
const puerto = Number(f.puerto || process.env.NAV_PUERTO || 9222);
const tid = f.tab || process.env.TID;

async function conPagina(fn) {
  const p = await Pagina.abrir(puerto, { tid });
  try { return await fn(p); } finally { p.desconectar(); }
}
const falta = (n, uso) => { if (a.length < n) throw new Error(`Missing argument. Usage: ${uso}`); };

try {
  if (!cmd || cmd === 'ayuda') console.log(AYUDA);
  else if (cmd === 'abrir') {
    const r = await lanzar({ navegador: f.navegador || 'auto', puerto, perfil: f.perfil || null, headless: !!f.headless, url: f.url || 'about:blank' });
    console.log(`Browser ready on port ${r.puerto}. ${r.temporal ? 'Temporary profile (deleted on close)' : 'Persistent profile'}: ${r.perfil}`);
    for (const t of await pestanas(puerto)) console.log(`  ${t.id}  ${t.url.slice(0, 80)}`);
  } else if (cmd === 'estado') {
    const reg = abiertos();
    const claves = Object.keys(reg);
    if (!claves.length) console.log('No browsers opened by this skill.');
    for (const p of claves) {
      const vivo = await responde(p);
      console.log(`port ${p} | ${vivo ? 'active' : 'NOT responding'} | ${reg[p].temporal ? 'temporary' : 'persistent'} profile${reg[p].headless ? ' | headless' : ''}`);
      if (vivo) for (const t of await pestanas(p)) console.log(`  ${t.id}  ${t.url.slice(0, 80)}`);
    }
  } else if (cmd === 'cerrar') {
    const r = await cerrarNavegador(puerto, { borrarPerfil: !!f['borrar-perfil'] });
    console.log(`Closed. ${r.perfilBorrado ? 'Profile deleted.' : 'Profile kept at ' + r.perfil}`);
  } else if (cmd === 'pestanas') {
    for (const t of await pestanas(puerto)) console.log(`${t.id}  ${t.url.slice(0, 100)}  | ${t.title.slice(0, 40)}`);
  } else if (cmd === 'nueva') {
    falta(1, 'nueva <url>');
    const p = await Pagina.abrir(puerto, { nueva: true, url: a[0] });
    console.log(p.id); p.desconectar();
  } else if (cmd === 'cerrar-pestana') {
    falta(1, 'cerrar-pestana <id>');
    await fetch(`http://127.0.0.1:${puerto}/json/close/${a[0]}`); console.log('closed');
  } else if (cmd === 'ir') { falta(1, 'ir <url>'); console.log('at:', await conPagina(p => p.ir(a[0]))); }
  else if (cmd === 'url') console.log(await conPagina(p => p.url()));
  else if (cmd === 'titulo') console.log(await conPagina(p => p.titulo()));
  else if (cmd === 'leer') console.log(await conPagina(p => p.leer(a[0])));
  else if (cmd === 'html') console.log(await conPagina(p => p.html(a[0])));
  else if (cmd === 'eval') { falta(1, 'eval "<js>"'); const v = await conPagina(p => p.evaluar(a[0])); console.log(typeof v === 'string' ? v : JSON.stringify(v, null, 1)); }
  else if (cmd === 'captura') { falta(1, 'captura <file.png>'); console.log('saved:', await conPagina(p => p.captura(a[0], { completa: !!f.completa }))); }
  else if (cmd === 'esperar') { falta(1, 'esperar <target>'); await conPagina(p => p.esperar(a[0], Number(f.ms || 15000))); console.log('found'); }
  else if (cmd === 'clic') { falta(1, 'clic <target>'); await conPagina(p => p.clic(a[0], { derecho: !!f.derecho, doble: !!f.doble })); console.log('clicked', a[0]); }
  else if (cmd === 'escribir') { falta(2, 'escribir <target> "<text>"'); await conPagina(p => p.escribir(a[0], a[1])); console.log('typed into', a[0]); }
  else if (cmd === 'seleccionar') { falta(2, 'seleccionar <target> "<value>"'); await conPagina(p => p.seleccionar(a[0], a[1])); console.log('selected', a[1]); }
  else if (cmd === 'tecla') { falta(1, 'tecla <key>'); await conPagina(p => p.tecla(a[0])); console.log('key', a[0]); }
  else if (cmd === 'subir') { falta(2, 'subir <target> <file...>'); await conPagina(p => p.subir(a[0], a.slice(1))); console.log('files assigned:', a.length - 1); }
  else { console.error(`Unknown command: ${cmd}\n`); console.error(AYUDA); process.exitCode = 1; }
} catch (e) {
  console.error('ERROR:', e.message);
  process.exitCode = 1;
}
// Exit only once the output has drained (with pipes, exiting abruptly can cut the text).
process.stderr.write('', () => process.stdout.write('', () => process.exit()));
