// SPDX-License-Identifier: MIT
// Copyright (c) 2026 alejandro-xoxo
// Manejo puntual del navegador por línea de comandos. Cada comando imprime poco y falla con un mensaje claro.
// Uso: node nav.mjs <comando> [argumentos] [--puerto 9222] [--tab <id>]
import { lanzar, cerrarNavegador, abiertos, responde, pestanas, Pagina } from './motor.mjs';

const BOOLEANAS = new Set(['headless', 'borrar-perfil', 'completa', 'derecho', 'doble']);
const AYUDA = `Navegador por CDP (sin extensiones). Uso: node nav.mjs <comando> [args] [--puerto 9222] [--tab <id>]

Navegador
  abrir [--url U] [--navegador edge|chrome] [--perfil nombre] [--headless] [--puerto N]
        Sin --perfil el perfil es temporal (se borra al cerrar). Con --perfil la sesión se conserva entre usos.
  estado                      navegadores abiertos por esta skill y sus pestañas
  cerrar [--borrar-perfil]    cierra el navegador del puerto (los temporales borran su perfil)
Pestañas
  pestanas | nueva <url> | cerrar-pestana <id>
En una pestaña (--tab <id> o variable TID; si solo hay una, se usa esa)
  ir <url> | url | titulo
  leer [objetivo] | html [objetivo] | eval "<js>"
  captura <archivo.png> [--completa]
  esperar <objetivo> [--ms 15000]
  clic <objetivo> [--derecho] [--doble]
  escribir <objetivo> "<texto>" | seleccionar <objetivo> "<valor>"
  tecla <Enter|Tab|Escape|Ctrl+A|...>
  subir <objetivo-que-abre-el-selector> <archivo> [archivo...]
Objetivo = selector CSS, texto=Guardar (elemento visible con ese texto) o coordenadas x,y.`;

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
const falta = (n, uso) => { if (a.length < n) throw new Error(`Falta algún argumento. Uso: ${uso}`); };

try {
  if (!cmd || cmd === 'ayuda') console.log(AYUDA);
  else if (cmd === 'abrir') {
    const r = await lanzar({ navegador: f.navegador || 'auto', puerto, perfil: f.perfil || null, headless: !!f.headless, url: f.url || 'about:blank' });
    console.log(`Navegador listo en el puerto ${r.puerto}. Perfil ${r.temporal ? 'temporal (se borra al cerrar)' : 'persistente'}: ${r.perfil}`);
    for (const t of await pestanas(puerto)) console.log(`  ${t.id}  ${t.url.slice(0, 80)}`);
  } else if (cmd === 'estado') {
    const reg = abiertos();
    const claves = Object.keys(reg);
    if (!claves.length) console.log('No hay navegadores abiertos por esta skill.');
    for (const p of claves) {
      const vivo = await responde(p);
      console.log(`puerto ${p} | ${vivo ? 'activo' : 'NO responde'} | perfil ${reg[p].temporal ? 'temporal' : 'persistente'}${reg[p].headless ? ' | headless' : ''}`);
      if (vivo) for (const t of await pestanas(p)) console.log(`  ${t.id}  ${t.url.slice(0, 80)}`);
    }
  } else if (cmd === 'cerrar') {
    const r = await cerrarNavegador(puerto, { borrarPerfil: !!f['borrar-perfil'] });
    console.log(`Cerrado. ${r.perfilBorrado ? 'Perfil borrado.' : 'Perfil conservado en ' + r.perfil}`);
  } else if (cmd === 'pestanas') {
    for (const t of await pestanas(puerto)) console.log(`${t.id}  ${t.url.slice(0, 100)}  | ${t.title.slice(0, 40)}`);
  } else if (cmd === 'nueva') {
    falta(1, 'nueva <url>');
    const p = await Pagina.abrir(puerto, { nueva: true, url: a[0] });
    console.log(p.id); p.desconectar();
  } else if (cmd === 'cerrar-pestana') {
    falta(1, 'cerrar-pestana <id>');
    await fetch(`http://127.0.0.1:${puerto}/json/close/${a[0]}`); console.log('cerrada');
  } else if (cmd === 'ir') { falta(1, 'ir <url>'); console.log('en:', await conPagina(p => p.ir(a[0]))); }
  else if (cmd === 'url') console.log(await conPagina(p => p.url()));
  else if (cmd === 'titulo') console.log(await conPagina(p => p.titulo()));
  else if (cmd === 'leer') console.log(await conPagina(p => p.leer(a[0])));
  else if (cmd === 'html') console.log(await conPagina(p => p.html(a[0])));
  else if (cmd === 'eval') { falta(1, 'eval "<js>"'); const v = await conPagina(p => p.evaluar(a[0])); console.log(typeof v === 'string' ? v : JSON.stringify(v, null, 1)); }
  else if (cmd === 'captura') { falta(1, 'captura <archivo.png>'); console.log('guardada:', await conPagina(p => p.captura(a[0], { completa: !!f.completa }))); }
  else if (cmd === 'esperar') { falta(1, 'esperar <objetivo>'); await conPagina(p => p.esperar(a[0], Number(f.ms || 15000))); console.log('encontrado'); }
  else if (cmd === 'clic') { falta(1, 'clic <objetivo>'); await conPagina(p => p.clic(a[0], { derecho: !!f.derecho, doble: !!f.doble })); console.log('clic en', a[0]); }
  else if (cmd === 'escribir') { falta(2, 'escribir <objetivo> "<texto>"'); await conPagina(p => p.escribir(a[0], a[1])); console.log('escrito en', a[0]); }
  else if (cmd === 'seleccionar') { falta(2, 'seleccionar <objetivo> "<valor>"'); await conPagina(p => p.seleccionar(a[0], a[1])); console.log('elegido', a[1]); }
  else if (cmd === 'tecla') { falta(1, 'tecla <tecla>'); await conPagina(p => p.tecla(a[0])); console.log('tecla', a[0]); }
  else if (cmd === 'subir') { falta(2, 'subir <objetivo> <archivo...>'); await conPagina(p => p.subir(a[0], a.slice(1))); console.log('archivos asignados:', a.length - 1); }
  else { console.error(`Comando desconocido: ${cmd}\n`); console.error(AYUDA); process.exitCode = 1; }
} catch (e) {
  console.error('ERROR:', e.message);
  process.exitCode = 1;
}
// Se sale cuando la salida ya se vació (con tuberías, salir de golpe puede cortar el texto).
process.stderr.write('', () => process.stdout.write('', () => process.exit()));
