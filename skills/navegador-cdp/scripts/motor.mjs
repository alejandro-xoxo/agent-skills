// SPDX-License-Identifier: LicenseRef-Proprietary — Copyright (c) 2026 alejandro-xoxo. All rights reserved.
// Copyright (c) 2026 alejandro-xoxo
// Engine to drive Chrome or Edge over the CDP protocol, with no extensions and no dependencies (Node 22 or later).
// Used by nav.mjs (one-off tasks) and by saved processes (borradores/ = drafts and procesos/ = processes).
// Identifier names are Spanish (lanzar = launch, pestanas = tabs, Pagina = Page, clic = click, ...).
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, execFileSync } from 'node:child_process';

export const DATOS = path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), '.local', 'share'), 'navegador-cdp');
const REGISTRO = path.join(DATOS, 'abiertos.json');
const dormir = ms => new Promise(r => setTimeout(r, ms));

// ---------- Registry of browsers this skill opened ----------
function leerRegistro() { try { return JSON.parse(fs.readFileSync(REGISTRO, 'utf8')); } catch { return {}; } }
function guardarRegistro(r) { fs.mkdirSync(DATOS, { recursive: true }); fs.writeFileSync(REGISTRO, JSON.stringify(r, null, 1)); }
export const abiertos = leerRegistro;

export async function responde(puerto) {
  try { return (await fetch(`http://127.0.0.1:${puerto}/json/version`, { signal: AbortSignal.timeout(1500) })).ok; } catch { return false; }
}

// ---------- Open and close the browser ----------
function buscarNavegador(nombre = 'auto') {
  const pf = process.env.ProgramFiles, pf86 = process.env['ProgramFiles(x86)'], la = process.env.LOCALAPPDATA;
  const edge = [pf86 && `${pf86}\\Microsoft\\Edge\\Application\\msedge.exe`, pf && `${pf}\\Microsoft\\Edge\\Application\\msedge.exe`,
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge', '/usr/bin/microsoft-edge'];
  const chrome = [pf && `${pf}\\Google\\Chrome\\Application\\chrome.exe`, pf86 && `${pf86}\\Google\\Chrome\\Application\\chrome.exe`,
    la && `${la}\\Google\\Chrome\\Application\\chrome.exe`, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome', '/usr/bin/chromium'];
  const lista = nombre === 'edge' ? edge : nombre === 'chrome' ? chrome : [...edge, ...chrome];
  const exe = lista.filter(Boolean).find(p => fs.existsSync(p));
  if (!exe) throw new Error(`Cannot find the browser (${nombre}). Install Edge or Chrome.`);
  return exe;
}

// perfil = null -> temporary profile, deleted on close. perfil = "name" -> persistent profile (keeps the session between uses).
export async function lanzar({ navegador = 'auto', puerto = 9222, perfil = null, headless = false, url = 'about:blank' } = {}) {
  if (await responde(puerto)) throw new Error(`Port ${puerto} is already used by a browser with debugging enabled. Use another port or close it with: node nav.mjs cerrar --puerto ${puerto}`);
  const exe = buscarNavegador(navegador);
  const temporal = !perfil;
  const dir = temporal ? fs.mkdtempSync(path.join(os.tmpdir(), `navcdp-${puerto}-`)) : path.join(DATOS, 'perfiles', perfil);
  fs.mkdirSync(dir, { recursive: true });
  const args = [`--remote-debugging-port=${puerto}`, `--user-data-dir=${dir}`, '--no-first-run', '--no-default-browser-check'];
  if (headless) args.push('--headless=new');
  args.push(url);
  spawn(exe, args, { detached: true, stdio: 'ignore' }).unref();
  for (let i = 0; i < 40; i++) {
    await dormir(500);
    if (await responde(puerto)) {
      const reg = leerRegistro();
      reg[puerto] = { exe, perfil: dir, temporal, nombrePerfil: perfil, headless, inicio: new Date().toISOString() };
      guardarRegistro(reg);
      return { puerto, perfil: dir, temporal };
    }
  }
  throw new Error(`The browser did not respond on port ${puerto}`);
}

function matarPorPerfil(dir) {
  if (process.platform === 'win32') {
    // The path goes through an environment variable to avoid quoting problems and to not match PowerShell itself (filtered by exe name).
    const ps = "$d = $env:NAVCDP_PERFIL; Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'msedge.exe' -or $_.Name -eq 'chrome.exe') -and $_.CommandLine -and $_.CommandLine.Contains($d) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }";
    execFileSync('powershell', ['-NoProfile', '-NonInteractive', '-Command', ps], { env: { ...process.env, NAVCDP_PERFIL: dir }, stdio: 'ignore' });
  } else {
    try { execFileSync('pkill', ['-f', dir], { stdio: 'ignore' }); } catch { /* nothing to close */ }
  }
}

// Graceful close (Browser.close): the browser writes cookies and session to disk before exiting.
// Killing it abruptly loses recent data, and in a persistent profile that can be a login that was just completed.
async function cierreSuave(puerto) {
  try {
    const v = await (await fetch(`http://127.0.0.1:${puerto}/json/version`, { signal: AbortSignal.timeout(2000) })).json();
    const c = await Cliente.conectar(v.webSocketDebuggerUrl);
    await c.send('Browser.close', {}, 5000).catch(() => {}); // it usually drops the connection before answering
    c.cerrar();
  } catch { /* if this failed, it is forced below */ }
  for (let i = 0; i < 20; i++) { if (!(await responde(puerto))) return true; await dormir(500); }
  return false;
}

export async function cerrarNavegador(puerto, { borrarPerfil = false } = {}) {
  const reg = leerRegistro();
  const e = reg[puerto];
  if (!e) throw new Error(`No browser is registered on port ${puerto}. I can only close the ones I opened with "abrir".`);
  await cierreSuave(puerto);
  await dormir(1500);
  matarPorPerfil(e.perfil); // whatever is still alive
  await dormir(1500);
  const borrar = e.temporal || borrarPerfil;
  if (borrar) fs.rmSync(e.perfil, { recursive: true, force: true, maxRetries: 5, retryDelay: 500 });
  delete reg[puerto];
  guardarRegistro(reg);
  return { perfil: e.perfil, perfilBorrado: borrar && !fs.existsSync(e.perfil) };
}

export async function pestanas(puerto = 9222) {
  try {
    const r = await fetch(`http://127.0.0.1:${puerto}/json/list`, { signal: AbortSignal.timeout(3000) });
    return (await r.json()).filter(t => t.type === 'page');
  } catch {
    throw new Error(`No browser with debugging on port ${puerto}. Open one with: node nav.mjs abrir`);
  }
}

// ---------- CDP client ----------
class Cliente {
  constructor(ws) {
    this.ws = ws; this.n = 0; this.pend = new Map(); this.esc = [];
    ws.onmessage = e => {
      const m = JSON.parse(e.data);
      if (m.id && this.pend.has(m.id)) {
        const p = this.pend.get(m.id); this.pend.delete(m.id);
        m.error ? p.mal(new Error(m.error.message)) : p.ok(m.result);
      } else if (m.method) this.esc.forEach(f => f(m));
    };
    ws.onclose = () => { for (const p of this.pend.values()) p.mal(new Error('The connection to the browser was closed')); this.pend.clear(); };
  }
  static async conectar(url) {
    const ws = new WebSocket(url);
    await new Promise((ok, mal) => { ws.onopen = ok; ws.onerror = () => mal(new Error('Could not connect to the tab (was it closed?)')); });
    return new Cliente(ws);
  }
  send(method, params = {}, ms = 30000) {
    return new Promise((ok, mal) => {
      const id = ++this.n;
      const t = setTimeout(() => { this.pend.delete(id); mal(new Error(`Timed out in ${method}`)); }, ms);
      this.pend.set(id, { ok: v => { clearTimeout(t); ok(v); }, mal: e => { clearTimeout(t); mal(e); } });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  esperarEvento(nombre, ms = 15000) {
    return new Promise((ok, mal) => {
      const quitar = () => { this.esc = this.esc.filter(x => x !== f); };
      const t = setTimeout(() => { quitar(); mal(new Error(`Timed out waiting for ${nombre}`)); }, ms);
      const f = m => { if (m.method === nombre) { clearTimeout(t); quitar(); ok(m.params); } };
      this.esc.push(f);
    });
  }
  cerrar() { try { this.ws.close(); } catch { /* already closed */ } }
}

// Finds an element: CSS selector, or "texto=Save" (visible; the one with the shortest text that contains it).
const BUSCAR = `(o => {
  const txt = e => (e.innerText || e.value || e.getAttribute('aria-label') || e.placeholder || '').trim();
  const visible = e => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  if (o.startsWith('texto=')) {
    const t = o.slice(6).trim().toLowerCase();
    let c = [...document.querySelectorAll('button,a,input,select,textarea,label,summary,[role],li,span,div,p,h1,h2,h3,h4,td,th')]
      .filter(e => visible(e) && txt(e).toLowerCase().includes(t));
    c = c.filter(e => !c.some(o => o !== e && e.contains(o)));
    const activo = e => e.closest('button,a,input,select,textarea,summary,[role=button],[role=link],[role=menuitem],[role=option],[role=tab]') ? 0 : 1;
    c.sort((a, b) => (txt(a).toLowerCase() === t ? 0 : 1) - (txt(b).toLowerCase() === t ? 0 : 1) || activo(a) - activo(b) || txt(a).length - txt(b).length);
    return c[0] || null;
  }
  return document.querySelector(o);
})`;

const TECLAS = {
  Enter: { key: 'Enter', code: 'Enter', vk: 13, text: '\r' }, Tab: { key: 'Tab', code: 'Tab', vk: 9 },
  Escape: { key: 'Escape', code: 'Escape', vk: 27 }, Backspace: { key: 'Backspace', code: 'Backspace', vk: 8 },
  Delete: { key: 'Delete', code: 'Delete', vk: 46 }, Space: { key: ' ', code: 'Space', vk: 32, text: ' ' },
  ArrowUp: { key: 'ArrowUp', code: 'ArrowUp', vk: 38 }, ArrowDown: { key: 'ArrowDown', code: 'ArrowDown', vk: 40 },
  ArrowLeft: { key: 'ArrowLeft', code: 'ArrowLeft', vk: 37 }, ArrowRight: { key: 'ArrowRight', code: 'ArrowRight', vk: 39 },
  Home: { key: 'Home', code: 'Home', vk: 36 }, End: { key: 'End', code: 'End', vk: 35 },
  PageUp: { key: 'PageUp', code: 'PageUp', vk: 33 }, PageDown: { key: 'PageDown', code: 'PageDown', vk: 34 },
};

// ---------- A tab ----------
export class Pagina {
  constructor(c, puerto, id) { this.c = c; this.puerto = puerto; this.id = id; }

  // Without tid: uses the only open tab (if there are several, asks you to say which). nueva = opens a tab of its own.
  static async abrir(puerto = 9222, { tid, nueva = false, url = 'about:blank' } = {}) {
    let id = tid;
    if (nueva) {
      const r = await fetch(`http://127.0.0.1:${puerto}/json/new?${url}`, { method: 'PUT' });
      id = (await r.json()).id;
    }
    const lista = await pestanas(puerto);
    if (!id) {
      if (lista.length === 0) throw new Error('No tab is open. Create one with: node nav.mjs nueva <url>');
      if (lista.length > 1) throw new Error('There are several tabs; pick one with --tab <id> (or the TID variable):\n' + lista.map(t => `  ${t.id}  ${t.url.slice(0, 80)}`).join('\n'));
      id = lista[0].id;
    }
    const info = lista.find(t => t.id === id);
    if (!info) throw new Error(`Tab ${id} does not exist. See the existing ones with: node nav.mjs pestanas`);
    const c = await Cliente.conectar(info.webSocketDebuggerUrl);
    await c.send('Page.enable');
    return new Pagina(c, puerto, id);
  }

  async evaluar(expr) {
    const r = await this.c.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) {
      // Only the first line of the error: the rest is the injected script's internal stack and does not help.
      const d = (r.exceptionDetails.exception?.description || r.exceptionDetails.text || '').split('\n')[0].replace(/^Error: /, '');
      throw new Error('Error in the page: ' + d);
    }
    return r.result.value;
  }
  async url() { return this.evaluar('location.href'); }
  async titulo() { return this.evaluar('document.title'); }

  async ir(url) {
    const cargado = this.c.esperarEvento('Page.loadEventFired', 15000).catch(() => {});
    const r = await this.c.send('Page.navigate', { url });
    if (r.errorText) throw new Error(`Could not open ${url}: ${r.errorText}`);
    await cargado;
    await dormir(500);
    return this.url();
  }

  async existe(objetivo) {
    try { return !!(await this.evaluar(`!!(${BUSCAR})(${JSON.stringify(objetivo)})`)); } catch { return false; }
  }
  async esperar(objetivo, ms = 15000) {
    const fin = Date.now() + ms;
    while (Date.now() < fin) { if (await this.existe(objetivo)) return true; await dormir(200); }
    throw new Error(`Timed out waiting for: ${objetivo}`);
  }

  async _punto(objetivo) {
    if (/^\d+\s*,\s*\d+$/.test(objetivo)) { const [x, y] = objetivo.split(',').map(Number); return { x, y }; }
    await this.esperar(objetivo, 10000).catch(() => { throw new Error(`Cannot find: ${objetivo}`); });
    const r = await this.evaluar(`(() => { const e = (${BUSCAR})(${JSON.stringify(objetivo)}); if (!e) return null;
      e.scrollIntoView({ block: 'center', inline: 'center' }); const b = e.getBoundingClientRect();
      return { x: b.x + b.width / 2, y: b.y + b.height / 2, w: b.width, h: b.height }; })()`);
    if (!r) throw new Error(`Cannot find: ${objetivo}`);
    if (!r.w || !r.h) throw new Error(`The element is not visible: ${objetivo}`);
    await dormir(100);
    return r;
  }
  // objetivo (target): CSS selector, "texto=Save" or "x,y" coordinates.
  async clic(objetivo, { derecho = false, doble = false } = {}) {
    const { x, y } = await this._punto(objetivo);
    const boton = derecho ? 'right' : 'left';
    await this.c.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
    for (let i = 1; i <= (doble ? 2 : 1); i++) {
      await this.c.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: boton, clickCount: i });
      await this.c.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: boton, clickCount: i });
    }
  }
  // Replaces the content of the field. Empty texto = clear it.
  async escribir(objetivo, texto) {
    await this.esperar(objetivo, 10000).catch(() => { throw new Error(`Cannot find: ${objetivo}`); });
    await this.evaluar(`(() => { const e = (${BUSCAR})(${JSON.stringify(objetivo)}); e.scrollIntoView({ block: 'center' }); e.focus();
      if (e.select) e.select(); else if (e.isContentEditable) document.execCommand('selectAll', false); })()`);
    if (texto === '') await this.tecla('Delete'); else await this.c.send('Input.insertText', { text: String(texto) });
  }
  // Picks an option of a <select> by value or by visible text.
  async seleccionar(objetivo, valor) {
    const ok = await this.evaluar(`(() => { const e = (${BUSCAR})(${JSON.stringify(objetivo)}); if (!e || e.tagName !== 'SELECT') return false;
      const v = ${JSON.stringify(String(valor))}; const o = [...e.options].find(x => x.value === v) || [...e.options].find(x => x.text.trim() === v);
      if (!o) return false; e.value = o.value; e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
    if (!ok) throw new Error(`Could not select "${valor}" in ${objetivo}`);
  }
  // Examples: "Enter", "Tab", "Escape", "ArrowDown", "Ctrl+A", "Shift+Tab".
  async tecla(spec) {
    const partes = spec.split('+'); const nombre = partes.pop(); let mod = 0;
    for (const p of partes) {
      const m = p.toLowerCase();
      if (m === 'ctrl' || m === 'control') mod |= 2; else if (m === 'alt') mod |= 1; else if (m === 'shift') mod |= 8; else if (m === 'meta' || m === 'cmd') mod |= 4;
      else throw new Error(`Unknown modifier: ${p}`);
    }
    let t = TECLAS[nombre];
    if (!t) {
      if (nombre.length !== 1) throw new Error(`Unknown key: ${nombre}`);
      const up = nombre.toUpperCase();
      t = { key: nombre, code: /[a-z]/i.test(nombre) ? 'Key' + up : /\d/.test(nombre) ? 'Digit' + nombre : '', vk: up.charCodeAt(0), text: mod & 6 ? undefined : nombre };
    }
    const base = { key: t.key, code: t.code, windowsVirtualKeyCode: t.vk, nativeVirtualKeyCode: t.vk, modifiers: mod };
    if (mod & 2 && nombre.toLowerCase() === 'a') base.commands = ['selectAll'];
    await this.c.send('Input.dispatchKeyEvent', { type: t.text ? 'keyDown' : 'rawKeyDown', ...base, text: t.text });
    await this.c.send('Input.dispatchKeyEvent', { type: 'keyUp', ...base });
  }
  // Without a target: all the visible text of the page.
  async leer(objetivo) {
    if (!objetivo) return this.evaluar('document.body ? document.body.innerText : ""');
    return this.evaluar(`(() => { const e = (${BUSCAR})(${JSON.stringify(objetivo)}); if (!e) throw new Error('Cannot find: ' + ${JSON.stringify(objetivo)});
      return (/^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName) && e.value !== '') ? e.value : e.innerText; })()`);
  }
  async html(objetivo) {
    if (!objetivo) return this.evaluar('document.documentElement.outerHTML');
    return this.evaluar(`(() => { const e = (${BUSCAR})(${JSON.stringify(objetivo)}); if (!e) throw new Error('Cannot find: ' + ${JSON.stringify(objetivo)}); return e.outerHTML; })()`);
  }
  async captura(ruta, { completa = false } = {}) {
    const r = await this.c.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: completa });
    const destino = path.resolve(ruta);
    fs.mkdirSync(path.dirname(destino), { recursive: true });
    fs.writeFileSync(destino, Buffer.from(r.data, 'base64'));
    return destino;
  }
  // Clicks the target (a button or an <input type=file>) and fills in the file chooser that opens.
  async subir(objetivo, rutas) {
    const archivos = [].concat(rutas).map(r => path.resolve(r));
    for (const a of archivos) if (!fs.existsSync(a)) throw new Error(`File does not exist: ${a}`);
    await this.c.send('DOM.enable');
    await this.c.send('Page.setInterceptFileChooserDialog', { enabled: true });
    try {
      const abierto = this.c.esperarEvento('Page.fileChooserOpened', 15000);
      await this.clic(objetivo);
      const ev = await abierto;
      await this.c.send('DOM.setFileInputFiles', { files: archivos, backendNodeId: ev.backendNodeId });
    } finally {
      await this.c.send('Page.setInterceptFileChooserDialog', { enabled: false }).catch(() => {});
    }
  }
  async cerrarPestana() { await fetch(`http://127.0.0.1:${this.puerto}/json/close/${this.id}`).catch(() => {}); this.c.cerrar(); }
  desconectar() { this.c.cerrar(); }
}

// ---------- Wrapper for saved processes ----------
class NecesitaConfirmacion extends Error {}

// Used by the ejecutar.mjs scripts in borradores/ and procesos/. Prints one "RESULTADO {json}" line (RESULTADO = RESULT) and exits with:
// 0 = all good and verified · 1 = error · 3 = finished without any verification · 10 = irreversible step not confirmed.
export async function proceso(nombre, fn) {
  const params = JSON.parse(process.env.PROCESO_PARAMS || '{}');
  const puerto = Number(process.env.NAV_PUERTO || 9222);
  const confirmo = process.env.PROCESO_CONFIRMO === '1';
  const carpeta = process.env.PROCESO_DIR || process.cwd();
  const res = { proceso: nombre, estado: 'ok', pasos: [], verificaciones: [], irreversibles: [], error: null, ms: 0 };
  const t0 = Date.now();
  let pagina = null;

  const paso = async (titulo, f) => {
    const t = Date.now();
    try { const r = await f(); res.pasos.push({ titulo, ok: true, ms: Date.now() - t }); return r; }
    catch (e) { res.pasos.push({ titulo, ok: false, ms: Date.now() - t, error: e.message }); throw e; }
  };
  const verificar = (cond, mensaje) => {
    res.verificaciones.push({ mensaje, ok: !!cond });
    if (!cond) throw new Error(`Verification failed: ${mensaje}`);
  };
  // Call it right before something that cannot be undone (send, pay, delete, publish). Without the user's confirmation, the process stops.
  const irreversible = descripcion => {
    if (!confirmo) throw new NecesitaConfirmacion(descripcion);
    res.irreversibles.push(descripcion);
  };

  try {
    pagina = await Pagina.abrir(puerto, { nueva: true });
    await fn({ pagina, params, paso, verificar, irreversible, carpeta });
    if (res.verificaciones.length === 0) {
      res.estado = 'sin_verificaciones';
      res.error = 'The process finished without any verificar(...) call. Add at least one that checks the real result, not just that there was no error.';
    }
  } catch (e) {
    if (e instanceof NecesitaConfirmacion) { res.estado = 'necesita_confirmacion'; res.error = `Irreversible step: ${e.message}`; }
    else {
      res.estado = 'error'; res.error = e.message;
      if (pagina) {
        try { res.url = await pagina.url(); res.texto = (await pagina.leer()).replace(/\s+/g, ' ').slice(0, 400); res.captura = await pagina.captura(path.join(carpeta, 'ultimo-error.png')); } catch { /* the page may have been closed */ }
      }
    }
  } finally {
    if (pagina) { if (process.env.PROCESO_MANTENER === '1') pagina.desconectar(); else await pagina.cerrarPestana(); }
  }
  res.ms = Date.now() - t0;
  const codigo = { ok: 0, error: 1, sin_verificaciones: 3, necesita_confirmacion: 10 }[res.estado];
  process.stdout.write('RESULTADO ' + JSON.stringify(res) + '\n', () => process.exit(codigo));
}
