// SPDX-License-Identifier: LicenseRef-Proprietary — Copyright (c) 2026 alejandro-xoxo. All rights reserved.
// Copyright (c) 2026 alejandro-xoxo
// Motor para manejar Chrome o Edge por el protocolo CDP, sin extensiones y sin dependencias (Node 22 o superior).
// Lo usan nav.mjs (tareas puntuales) y los procesos guardados (borradores/ y procesos/).
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, execFileSync } from 'node:child_process';

export const DATOS = path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), '.local', 'share'), 'navegador-cdp');
const REGISTRO = path.join(DATOS, 'abiertos.json');
const dormir = ms => new Promise(r => setTimeout(r, ms));

// ---------- Registro de navegadores que abrió esta skill ----------
function leerRegistro() { try { return JSON.parse(fs.readFileSync(REGISTRO, 'utf8')); } catch { return {}; } }
function guardarRegistro(r) { fs.mkdirSync(DATOS, { recursive: true }); fs.writeFileSync(REGISTRO, JSON.stringify(r, null, 1)); }
export const abiertos = leerRegistro;

export async function responde(puerto) {
  try { return (await fetch(`http://127.0.0.1:${puerto}/json/version`, { signal: AbortSignal.timeout(1500) })).ok; } catch { return false; }
}

// ---------- Abrir y cerrar el navegador ----------
function buscarNavegador(nombre = 'auto') {
  const pf = process.env.ProgramFiles, pf86 = process.env['ProgramFiles(x86)'], la = process.env.LOCALAPPDATA;
  const edge = [pf86 && `${pf86}\\Microsoft\\Edge\\Application\\msedge.exe`, pf && `${pf}\\Microsoft\\Edge\\Application\\msedge.exe`,
    '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge', '/usr/bin/microsoft-edge'];
  const chrome = [pf && `${pf}\\Google\\Chrome\\Application\\chrome.exe`, pf86 && `${pf86}\\Google\\Chrome\\Application\\chrome.exe`,
    la && `${la}\\Google\\Chrome\\Application\\chrome.exe`, '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/usr/bin/google-chrome', '/usr/bin/chromium'];
  const lista = nombre === 'edge' ? edge : nombre === 'chrome' ? chrome : [...edge, ...chrome];
  const exe = lista.filter(Boolean).find(p => fs.existsSync(p));
  if (!exe) throw new Error(`No encuentro el navegador (${nombre}). Instala Edge o Chrome.`);
  return exe;
}

// perfil = null -> perfil temporal que se borra al cerrar. perfil = "nombre" -> perfil persistente (guarda la sesión entre usos).
export async function lanzar({ navegador = 'auto', puerto = 9222, perfil = null, headless = false, url = 'about:blank' } = {}) {
  if (await responde(puerto)) throw new Error(`El puerto ${puerto} ya está en uso por un navegador con depuración. Usa otro puerto o ciérralo con: node nav.mjs cerrar --puerto ${puerto}`);
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
  throw new Error(`El navegador no respondió en el puerto ${puerto}`);
}

function matarPorPerfil(dir) {
  if (process.platform === 'win32') {
    // La ruta va por variable de entorno para no tener problemas de comillas y para no coincidir con el propio PowerShell (se filtra por nombre de exe).
    const ps = "$d = $env:NAVCDP_PERFIL; Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'msedge.exe' -or $_.Name -eq 'chrome.exe') -and $_.CommandLine -and $_.CommandLine.Contains($d) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }";
    execFileSync('powershell', ['-NoProfile', '-NonInteractive', '-Command', ps], { env: { ...process.env, NAVCDP_PERFIL: dir }, stdio: 'ignore' });
  } else {
    try { execFileSync('pkill', ['-f', dir], { stdio: 'ignore' }); } catch { /* nada que cerrar */ }
  }
}

// Cierre normal (Browser.close): el navegador guarda cookies y sesión en disco antes de salir.
// Matarlo de golpe pierde lo reciente, y en un perfil persistente eso puede ser un inicio de sesión recién hecho.
async function cierreSuave(puerto) {
  try {
    const v = await (await fetch(`http://127.0.0.1:${puerto}/json/version`, { signal: AbortSignal.timeout(2000) })).json();
    const c = await Cliente.conectar(v.webSocketDebuggerUrl);
    await c.send('Browser.close', {}, 5000).catch(() => {}); // suele cortar la conexión antes de responder
    c.cerrar();
  } catch { /* si no se pudo, se fuerza más abajo */ }
  for (let i = 0; i < 20; i++) { if (!(await responde(puerto))) return true; await dormir(500); }
  return false;
}

export async function cerrarNavegador(puerto, { borrarPerfil = false } = {}) {
  const reg = leerRegistro();
  const e = reg[puerto];
  if (!e) throw new Error(`No hay un navegador registrado en el puerto ${puerto}. Solo puedo cerrar los que abrí con "abrir".`);
  await cierreSuave(puerto);
  await dormir(1500);
  matarPorPerfil(e.perfil); // lo que haya quedado vivo
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
    throw new Error(`No hay navegador con depuración en el puerto ${puerto}. Ábrelo con: node nav.mjs abrir`);
  }
}

// ---------- Cliente CDP ----------
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
    ws.onclose = () => { for (const p of this.pend.values()) p.mal(new Error('Se cerró la conexión con el navegador')); this.pend.clear(); };
  }
  static async conectar(url) {
    const ws = new WebSocket(url);
    await new Promise((ok, mal) => { ws.onopen = ok; ws.onerror = () => mal(new Error('No pude conectar con la pestaña (¿se cerró?)')); });
    return new Cliente(ws);
  }
  send(method, params = {}, ms = 30000) {
    return new Promise((ok, mal) => {
      const id = ++this.n;
      const t = setTimeout(() => { this.pend.delete(id); mal(new Error(`Tiempo agotado en ${method}`)); }, ms);
      this.pend.set(id, { ok: v => { clearTimeout(t); ok(v); }, mal: e => { clearTimeout(t); mal(e); } });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  esperarEvento(nombre, ms = 15000) {
    return new Promise((ok, mal) => {
      const quitar = () => { this.esc = this.esc.filter(x => x !== f); };
      const t = setTimeout(() => { quitar(); mal(new Error(`Tiempo agotado esperando ${nombre}`)); }, ms);
      const f = m => { if (m.method === nombre) { clearTimeout(t); quitar(); ok(m.params); } };
      this.esc.push(f);
    });
  }
  cerrar() { try { this.ws.close(); } catch { /* ya cerrada */ } }
}

// Busca un elemento: selector CSS, o "texto=Guardar" (visible, el de texto más corto que lo contiene).
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

// ---------- Una pestaña ----------
export class Pagina {
  constructor(c, puerto, id) { this.c = c; this.puerto = puerto; this.id = id; }

  // Sin tid: usa la única pestaña abierta (si hay varias, pide que indiques cuál). nueva = abre una pestaña propia.
  static async abrir(puerto = 9222, { tid, nueva = false, url = 'about:blank' } = {}) {
    let id = tid;
    if (nueva) {
      const r = await fetch(`http://127.0.0.1:${puerto}/json/new?${url}`, { method: 'PUT' });
      id = (await r.json()).id;
    }
    const lista = await pestanas(puerto);
    if (!id) {
      if (lista.length === 0) throw new Error('No hay ninguna pestaña abierta. Crea una con: node nav.mjs nueva <url>');
      if (lista.length > 1) throw new Error('Hay varias pestañas; indica una con --tab <id> (o la variable TID):\n' + lista.map(t => `  ${t.id}  ${t.url.slice(0, 80)}`).join('\n'));
      id = lista[0].id;
    }
    const info = lista.find(t => t.id === id);
    if (!info) throw new Error(`La pestaña ${id} no existe. Mira las que hay con: node nav.mjs pestanas`);
    const c = await Cliente.conectar(info.webSocketDebuggerUrl);
    await c.send('Page.enable');
    return new Pagina(c, puerto, id);
  }

  async evaluar(expr) {
    const r = await this.c.send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.exceptionDetails) {
      // Solo la primera línea del error: el resto es la pila interna del script inyectado y no ayuda.
      const d = (r.exceptionDetails.exception?.description || r.exceptionDetails.text || '').split('\n')[0].replace(/^Error: /, '');
      throw new Error('Error en la página: ' + d);
    }
    return r.result.value;
  }
  async url() { return this.evaluar('location.href'); }
  async titulo() { return this.evaluar('document.title'); }

  async ir(url) {
    const cargado = this.c.esperarEvento('Page.loadEventFired', 15000).catch(() => {});
    const r = await this.c.send('Page.navigate', { url });
    if (r.errorText) throw new Error(`No se pudo abrir ${url}: ${r.errorText}`);
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
    throw new Error(`Tiempo agotado esperando: ${objetivo}`);
  }

  async _punto(objetivo) {
    if (/^\d+\s*,\s*\d+$/.test(objetivo)) { const [x, y] = objetivo.split(',').map(Number); return { x, y }; }
    await this.esperar(objetivo, 10000).catch(() => { throw new Error(`No encuentro: ${objetivo}`); });
    const r = await this.evaluar(`(() => { const e = (${BUSCAR})(${JSON.stringify(objetivo)}); if (!e) return null;
      e.scrollIntoView({ block: 'center', inline: 'center' }); const b = e.getBoundingClientRect();
      return { x: b.x + b.width / 2, y: b.y + b.height / 2, w: b.width, h: b.height }; })()`);
    if (!r) throw new Error(`No encuentro: ${objetivo}`);
    if (!r.w || !r.h) throw new Error(`El elemento no es visible: ${objetivo}`);
    await dormir(100);
    return r;
  }
  // objetivo: selector CSS, "texto=Guardar" o coordenadas "x,y".
  async clic(objetivo, { derecho = false, doble = false } = {}) {
    const { x, y } = await this._punto(objetivo);
    const boton = derecho ? 'right' : 'left';
    await this.c.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
    for (let i = 1; i <= (doble ? 2 : 1); i++) {
      await this.c.send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: boton, clickCount: i });
      await this.c.send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: boton, clickCount: i });
    }
  }
  // Reemplaza el contenido del campo. texto vacío = borrarlo.
  async escribir(objetivo, texto) {
    await this.esperar(objetivo, 10000).catch(() => { throw new Error(`No encuentro: ${objetivo}`); });
    await this.evaluar(`(() => { const e = (${BUSCAR})(${JSON.stringify(objetivo)}); e.scrollIntoView({ block: 'center' }); e.focus();
      if (e.select) e.select(); else if (e.isContentEditable) document.execCommand('selectAll', false); })()`);
    if (texto === '') await this.tecla('Delete'); else await this.c.send('Input.insertText', { text: String(texto) });
  }
  // Elige una opción de un <select> por valor o por texto visible.
  async seleccionar(objetivo, valor) {
    const ok = await this.evaluar(`(() => { const e = (${BUSCAR})(${JSON.stringify(objetivo)}); if (!e || e.tagName !== 'SELECT') return false;
      const v = ${JSON.stringify(String(valor))}; const o = [...e.options].find(x => x.value === v) || [...e.options].find(x => x.text.trim() === v);
      if (!o) return false; e.value = o.value; e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
    if (!ok) throw new Error(`No pude elegir "${valor}" en ${objetivo}`);
  }
  // Ejemplos: "Enter", "Tab", "Escape", "ArrowDown", "Ctrl+A", "Shift+Tab".
  async tecla(spec) {
    const partes = spec.split('+'); const nombre = partes.pop(); let mod = 0;
    for (const p of partes) {
      const m = p.toLowerCase();
      if (m === 'ctrl' || m === 'control') mod |= 2; else if (m === 'alt') mod |= 1; else if (m === 'shift') mod |= 8; else if (m === 'meta' || m === 'cmd') mod |= 4;
      else throw new Error(`Modificador desconocido: ${p}`);
    }
    let t = TECLAS[nombre];
    if (!t) {
      if (nombre.length !== 1) throw new Error(`Tecla desconocida: ${nombre}`);
      const up = nombre.toUpperCase();
      t = { key: nombre, code: /[a-z]/i.test(nombre) ? 'Key' + up : /\d/.test(nombre) ? 'Digit' + nombre : '', vk: up.charCodeAt(0), text: mod & 6 ? undefined : nombre };
    }
    const base = { key: t.key, code: t.code, windowsVirtualKeyCode: t.vk, nativeVirtualKeyCode: t.vk, modifiers: mod };
    if (mod & 2 && nombre.toLowerCase() === 'a') base.commands = ['selectAll'];
    await this.c.send('Input.dispatchKeyEvent', { type: t.text ? 'keyDown' : 'rawKeyDown', ...base, text: t.text });
    await this.c.send('Input.dispatchKeyEvent', { type: 'keyUp', ...base });
  }
  // Sin objetivo: todo el texto visible de la página.
  async leer(objetivo) {
    if (!objetivo) return this.evaluar('document.body ? document.body.innerText : ""');
    return this.evaluar(`(() => { const e = (${BUSCAR})(${JSON.stringify(objetivo)}); if (!e) throw new Error('No encuentro: ' + ${JSON.stringify(objetivo)});
      return (/^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName) && e.value !== '') ? e.value : e.innerText; })()`);
  }
  async html(objetivo) {
    if (!objetivo) return this.evaluar('document.documentElement.outerHTML');
    return this.evaluar(`(() => { const e = (${BUSCAR})(${JSON.stringify(objetivo)}); if (!e) throw new Error('No encuentro: ' + ${JSON.stringify(objetivo)}); return e.outerHTML; })()`);
  }
  async captura(ruta, { completa = false } = {}) {
    const r = await this.c.send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: completa });
    const destino = path.resolve(ruta);
    fs.mkdirSync(path.dirname(destino), { recursive: true });
    fs.writeFileSync(destino, Buffer.from(r.data, 'base64'));
    return destino;
  }
  // Pulsa el objetivo (un botón o un <input type=file>) y rellena el selector de archivos que se abre.
  async subir(objetivo, rutas) {
    const archivos = [].concat(rutas).map(r => path.resolve(r));
    for (const a of archivos) if (!fs.existsSync(a)) throw new Error(`No existe el archivo: ${a}`);
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

// ---------- Envoltorio de los procesos guardados ----------
class NecesitaConfirmacion extends Error {}

// Lo usan los ejecutar.mjs de borradores/ y procesos/. Imprime una línea "RESULTADO {json}" y sale con:
// 0 = todo bien y verificado · 1 = error · 3 = terminó sin ninguna verificación · 10 = paso irreversible sin confirmar.
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
    if (!cond) throw new Error(`Verificación fallida: ${mensaje}`);
  };
  // Llámala justo antes de algo que no se puede deshacer (enviar, pagar, borrar, publicar). Sin confirmación del usuario, el proceso se detiene.
  const irreversible = descripcion => {
    if (!confirmo) throw new NecesitaConfirmacion(descripcion);
    res.irreversibles.push(descripcion);
  };

  try {
    pagina = await Pagina.abrir(puerto, { nueva: true });
    await fn({ pagina, params, paso, verificar, irreversible, carpeta });
    if (res.verificaciones.length === 0) {
      res.estado = 'sin_verificaciones';
      res.error = 'El proceso terminó sin ninguna verificar(...). Añade al menos una que compruebe el resultado real, no solo que no hubo error.';
    }
  } catch (e) {
    if (e instanceof NecesitaConfirmacion) { res.estado = 'necesita_confirmacion'; res.error = `Paso irreversible: ${e.message}`; }
    else {
      res.estado = 'error'; res.error = e.message;
      if (pagina) {
        try { res.url = await pagina.url(); res.texto = (await pagina.leer()).replace(/\s+/g, ' ').slice(0, 400); res.captura = await pagina.captura(path.join(carpeta, 'ultimo-error.png')); } catch { /* la página puede haberse cerrado */ }
      }
    }
  } finally {
    if (pagina) { if (process.env.PROCESO_MANTENER === '1') pagina.desconectar(); else await pagina.cerrarPestana(); }
  }
  res.ms = Date.now() - t0;
  const codigo = { ok: 0, error: 1, sin_verificaciones: 3, necesita_confirmacion: 10 }[res.estado];
  process.stdout.write('RESULTADO ' + JSON.stringify(res) + '\n', () => process.exit(codigo));
}
