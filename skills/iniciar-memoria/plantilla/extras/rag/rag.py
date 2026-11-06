#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-Proprietary — Copyright (c) 2026 alejandro-xoxo. All rights reserved.
# Copyright (c) 2026 alejandro-xoxo
"""Busqueda semantica local (RAG) sobre el vault de Obsidian y los docs del proyecto.

Todo ocurre en este equipo: el modelo de vectores se descarga una vez y nada sale a ninguna API.

Uso (con el Python del entorno de esta carpeta):
  rag.py indexar             construye o actualiza el indice (solo recalcula lo que cambio)
  rag.py buscar "pregunta"   muestra los mejores trozos, con archivo y lineas
  rag.py servidor            servidor local que mantiene el modelo cargado y se reindexa solo
  rag.py arrancar            arranca el servidor en segundo plano si no esta activo
  rag.py parar               detiene el servidor
  rag.py hook                lo llama el agente antes de cada mensaje: lee el mensaje por stdin y
                             escribe por stdout el contexto recuperado (nada si no hay nada relevante)
  rag.py ganchos             registra los ganchos en .claude/settings.local.json (mezcla, no pisa nada)
  rag.py evaluar             mide la calidad de la busqueda con evaluacion.json

Variables de entorno: RAG_DESACTIVAR=1 apaga la recuperacion automatica; RAG_UMBRAL, RAG_MODELO.
"""
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.request
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
PROYECTO = RAIZ.parent
INDICE = RAIZ / "indice"
# El modelo (unos 0,6 GB) se comparte entre todos los proyectos para no descargarlo cada vez (RAG_MODELOS lo cambia)
MODELOS = Path(os.environ.get("RAG_MODELOS") or (Path.home() / ".cache" / "rag-modelos"))
ARCHIVO_SERVIDOR = RAIZ / "servidor.json"
MODELO = os.environ.get("RAG_MODELO", "jinaai/jina-embeddings-v2-base-es")
UMBRAL = float(os.environ.get("RAG_UMBRAL", "0.50"))   # similitud minima para inyectar contexto (ajustado con evaluar)
# Lo curado manda sobre el material crudo: en la fusion, sus resultados pesan mas (ajustable con RAG_PESO_CURADO)
PESO_CURADO = float(os.environ.get("RAG_PESO_CURADO", "1.25"))
PESO_TIPO = {"nota curada": PESO_CURADO, "estado del proyecto": PESO_CURADO, "fuente cruda": 1.0}
K = 4                      # trozos que se devuelven
MAX_TROZO = 1500           # caracteres por trozo
MAX_CONTEXTO = 3200        # caracteres maximos que se inyectan en cada mensaje
INACTIVIDAD = 30 * 60      # el servidor se apaga solo tras 30 minutos sin uso

PARADA = set("""a al algo como con cual cuales cuando de del el ella ellas ellos en entre era es esta estan este esto
estos fue ha han hay la las le les lo los me mi mas mucho muy no nos o para pero por que se si sin sobre su sus te tu
un una uno unos y ya yo""".split())


# ---------------------------------------------------------------- fuentes
def ruta_vault():
    agentes = PROYECTO / "AGENTS.md"
    if not agentes.exists():
        sys.exit("No encuentro AGENTS.md en la carpeta del proyecto: ahi esta la ruta del vault (bloque ## Memoria).")
    m = re.search(r"Vault de Obsidian:\s*`([^`]+)`", agentes.read_text(encoding="utf-8"))
    if not m:
        sys.exit("AGENTS.md no tiene la linea 'Vault de Obsidian: `ruta`' en el bloque ## Memoria.")
    vault = Path(m.group(1))
    if not vault.is_absolute():       # en la plantilla el vault es la carpeta local "conocimiento/"
        vault = PROYECTO / vault
    if not vault.is_dir():
        sys.exit(f"El vault no existe en esta ruta: {vault}")
    return vault


def listar_fuentes():
    """(ruta, etiqueta, tipo). Las carpetas cuyo nombre contiene 'fuentes' son material crudo."""
    vault = ruta_vault()
    fuentes = []
    for f in sorted(vault.rglob("*.md")):
        rel = f.relative_to(vault)
        if ".obsidian" in rel.parts:
            continue
        crudo = any("fuentes" in p.lower() for p in rel.parts[:-1])
        fuentes.append((f, "vault/" + rel.as_posix(), "fuente cruda" if crudo else "nota curada"))
    for nombre in ("ESTADO.md", "DECISIONS.md"):
        f = PROYECTO / "docs" / nombre
        if f.exists():
            fuentes.append((f, "docs/" + nombre, "estado del proyecto"))
    return fuentes


def leer(f):
    return f.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


# ---------------------------------------------------------------- troceado
ENCABEZADO = re.compile(r"^(#{1,3})\s+(.*\S)\s*$")
ROL = re.compile(r"^\*\*(Usuario|Claude)\*\*\s*$")


def quitar_frontmatter(lineas):
    if lineas and lineas[0].strip() == "---":
        for i in range(1, len(lineas)):
            if lineas[i].strip() == "---":
                return i + 1
    return 0


def bloques_por_encabezado(lineas, ini, nota):
    bloques, actual, titulo = [], None, nota
    for n in range(ini, len(lineas)):
        m = ENCABEZADO.match(lineas[n])
        if m and actual is not None:
            bloques.append(actual)
            actual = None
        if m:
            titulo = m.group(2) if len(m.group(1)) == 1 else f"{nota} > {m.group(2)}"
        if actual is None:
            actual = [n + 1, titulo, []]
        actual[2].append(lineas[n])
    if actual:
        bloques.append(actual)
    return [(b[0], b[0] + len(b[2]) - 1, b[1], "\n".join(b[2])) for b in bloques if any(x.strip() for x in b[2])]


def bloques_por_separador(lineas, ini, nombre):
    """Material crudo (conversaciones): los turnos se separan con una linea '---'."""
    bruto, actual, l0 = [], [], ini + 1
    for n in range(ini, len(lineas)):
        if lineas[n].strip() == "---":
            if any(x.strip() for x in actual):
                bruto.append((l0, n, actual))
            actual, l0 = [], n + 2
        else:
            actual.append(lineas[n])
    if any(x.strip() for x in actual):
        bruto.append((l0, len(lineas), actual))
    salida = []
    for a, b, ls in bruto:
        rol = next((ROL.match(x).group(1) for x in ls if ROL.match(x)), None)
        salida.append((a, b, nombre + (f" ({rol})" if rol else ""), "\n".join(ls)))
    return salida


def empaquetar(bloques, llenar, minimo=350, maximo=MAX_TROZO):
    """Parte los bloques enormes y une los pequenos. Con llenar=True junta turnos seguidos hasta el maximo."""
    piezas = []
    for a, b, tit, txt in bloques:
        if len(txt) <= maximo:
            piezas.append((a, b, tit, txt))
            continue
        buf, n0, tam = [], a, 0
        for i, linea in enumerate(txt.split("\n")):
            if tam + len(linea) + 1 > maximo and buf:
                piezas.append((n0, a + i - 1, tit, "\n".join(buf)))
                buf, n0, tam = [], a + i, 0
            while len(linea) > maximo:
                piezas.append((a + i, a + i, tit, linea[:maximo]))
                linea = linea[maximo:]
            buf.append(linea)
            tam += len(linea) + 1
        if buf:
            piezas.append((n0, b, tit, "\n".join(buf)))
    salida = []
    for p in piezas:
        if salida:
            q = salida[-1]
            junta = len(q[3]) + len(p[3]) + 1 <= maximo
            if junta and (llenar or len(q[3]) < minimo):
                salida[-1] = (q[0], p[1], q[2], q[3] + "\n" + p[3])
                continue
        salida.append(p)
    return salida


def trocear(texto, tipo, nombre):
    lineas = texto.split("\n")
    ini = quitar_frontmatter(lineas)
    if tipo == "fuente cruda":
        return empaquetar(bloques_por_separador(lineas, ini, nombre), llenar=True)
    return empaquetar(bloques_por_encabezado(lineas, ini, nombre), llenar=False)


# ---------------------------------------------------------------- vectores
_modelo = None


def modelo():
    global _modelo
    if _modelo is None:
        from fastembed import TextEmbedding
        MODELOS.mkdir(exist_ok=True)
        _modelo = TextEmbedding(MODELO, cache_dir=str(MODELOS))
    return _modelo


def embeber(textos):
    import numpy as np
    v = np.array(list(modelo().embed(textos)), dtype=np.float32)
    n = np.linalg.norm(v, axis=1, keepdims=True)
    n[n == 0] = 1
    return v / n


def texto_vectorizable(t):
    return f"{t['titulo']}\n{t['texto']}"


# ---------------------------------------------------------------- indice
def leer_indice():
    import numpy as np
    try:
        estado = json.loads((INDICE / "estado.json").read_text(encoding="utf-8"))
        trozos = json.loads((INDICE / "trozos.json").read_text(encoding="utf-8"))
        vectores = np.load(INDICE / "vectores.npy")
        if len(trozos) != len(vectores):
            raise ValueError("indice incoherente")
        return estado, trozos, vectores
    except (OSError, ValueError, KeyError):
        return None


def guardar_indice(estado, trozos, vectores):
    import numpy as np
    INDICE.mkdir(parents=True, exist_ok=True)
    for nombre, contenido in (("trozos.json", json.dumps(trozos, ensure_ascii=False)),
                              ("estado.json", json.dumps(estado, ensure_ascii=False, indent=1))):
        tmp = INDICE / (nombre + ".tmp")
        tmp.write_text(contenido, encoding="utf-8")
        os.replace(tmp, INDICE / nombre)
    tmp = INDICE / "vectores.tmp.npy"
    np.save(tmp, vectores)
    os.replace(tmp, INDICE / "vectores.npy")


def indexar(hablar=False):
    """Incremental: reutiliza los vectores de los archivos que no cambiaron."""
    import numpy as np
    previo = leer_indice()
    previos = {}
    if previo and previo[0].get("modelo") == MODELO:
        for i, t in enumerate(previo[1]):
            previos.setdefault(t["archivo"], []).append(i)
    resultado, hashes, reutilizados, nuevos = [], {}, 0, 0
    for f, etiqueta, tipo in listar_fuentes():
        texto = leer(f)
        h = hashlib.sha1(texto.encode("utf-8")).hexdigest()
        hashes[etiqueta] = h
        if previo and previo[0]["archivos"].get(etiqueta) == h and etiqueta in previos:
            for i in previos[etiqueta]:
                resultado.append([previo[1][i], previo[2][i]])
                reutilizados += 1
            continue
        for a, b, tit, txt in trocear(texto, tipo, f.stem):
            resultado.append([{"archivo": etiqueta, "ini": a, "fin": b, "titulo": tit, "tipo": tipo, "texto": txt}, None])
            nuevos += 1
    pendientes = [i for i, (_, v) in enumerate(resultado) if v is None]
    if pendientes:
        if hablar:
            print(f"Calculando vectores de {len(pendientes)} trozos (la primera vez descarga el modelo)...", flush=True)
        vs = embeber([texto_vectorizable(resultado[i][0]) for i in pendientes])
        for j, i in enumerate(pendientes):
            resultado[i][1] = vs[j]
    if not resultado:
        sys.exit("No hay nada que indexar.")
    guardar_indice({"modelo": MODELO, "archivos": hashes}, [t for t, _ in resultado], np.vstack([v for _, v in resultado]))
    return {"archivos": len(hashes), "trozos": len(resultado), "nuevos": nuevos, "reutilizados": reutilizados}


# ---------------------------------------------------------------- busqueda
def tokens(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return [w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 1 and w not in PARADA]


class BM25:
    def __init__(self, docs):
        import numpy as np
        self.np = np
        self.tf = [Counter(d) for d in docs]
        self.n = len(docs)
        self.largo = np.array([len(d) for d in docs], dtype=np.float32)
        self.medio = float(self.largo.mean()) or 1.0
        df = Counter()
        for tf in self.tf:
            df.update(tf.keys())
        self.idf = {t: math.log(1 + (self.n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def puntuar(self, consulta):
        s = self.np.zeros(self.n, dtype=self.np.float32)
        for t in set(consulta):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(t, 0)
                if f:
                    s[i] += idf * f * 2.5 / (f + 1.5 * (0.25 + 0.75 * self.largo[i] / self.medio))
        return s


class Indice:
    def __init__(self, trozos, vectores):
        self.trozos, self.vectores = trozos, vectores
        self.bm25 = BM25([tokens(t["titulo"] + " " + t["texto"]) for t in trozos])

    def puntuaciones(self, consulta):
        sem = self.vectores @ embeber([consulta])[0]
        kw = self.bm25.puntuar(tokens(consulta))
        return sem, kw

    def buscar(self, consulta, k=K, modo="hibrido", max_por_archivo=2):
        import numpy as np
        sem, kw = self.puntuaciones(consulta)
        if modo == "semantico":
            orden = list(np.argsort(-sem))
        elif modo == "palabras":
            orden = [i for i in np.argsort(-kw) if kw[i] > 0]
        else:  # fusion por rangos (RRF)
            fus = Counter()
            for r, i in enumerate(np.argsort(-sem)[:60]):
                fus[int(i)] += 1 / (60 + r)
            for r, i in enumerate([i for i in np.argsort(-kw)[:60] if kw[i] > 0]):
                fus[int(i)] += 1 / (60 + r)
            for i in fus:
                fus[i] *= PESO_TIPO.get(self.trozos[i]["tipo"], 1.0)
            orden = [i for i, _ in fus.most_common()]
        salida, por_archivo, sem_max = [], Counter(), float(sem.max())
        for i in orden:
            t = self.trozos[int(i)]
            if por_archivo[t["archivo"]] >= max_por_archivo:
                continue
            por_archivo[t["archivo"]] += 1
            salida.append(dict(t, sem=float(sem[i]), kw=float(kw[i]), sem_max=sem_max))
            if len(salida) >= k:
                break
        return salida


def indice_en_memoria():
    previo = leer_indice()
    if not previo or previo[0].get("modelo") != MODELO:
        indexar(hablar=True)
        previo = leer_indice()
    return Indice(previo[1], previo[2])


def formatear(resultados):
    cab = ("[Contexto recuperado automaticamente del vault y de docs/ por busqueda semantica local. Puede estar "
           "incompleto o desactualizado: verificalo en la fuente citada antes de usarlo, e ignoralo si no es relevante.]")
    partes, total = [cab], 0
    for n, r in enumerate(resultados, 1):
        ext = r["texto"].strip()
        if len(ext) > 650:
            ext = ext[:650].rsplit(" ", 1)[0] + " [...]"
        bloque = f"{n}. {r['archivo']}:{r['ini']}-{r['fin']} ({r['tipo']}, similitud {r['sem']:.2f}) - {r['titulo']}\n{ext}"
        if total + len(bloque) > MAX_CONTEXTO and n > 1:
            break
        partes.append(bloque)
        total += len(bloque)
    return "\n\n".join(partes)


# ---------------------------------------------------------------- servidor
class Motor:
    """Mantiene el modelo y el indice en memoria, y se reindexa solo si cambia algun archivo."""

    def __init__(self):
        self.lock = threading.Lock()
        self.reindexando = False
        self.cargar()

    def firma(self):
        return tuple((e, f.stat().st_mtime_ns, f.stat().st_size) for f, e, _ in listar_fuentes())

    def cargar(self):
        # La firma se toma ANTES de indexar: si un archivo cambia mientras se indexa, la firma queda vieja
        # y la siguiente busqueda dispara otra pasada, asi no se pierde ningun cambio.
        firma = self.firma()
        indexar()
        previo = leer_indice()
        nuevo = Indice(previo[1], previo[2])
        with self.lock:
            self.indice, self.firma_actual = nuevo, firma

    def reindexar_en_segundo_plano(self):
        if self.reindexando:
            return
        self.reindexando = True

        def trabajo():
            try:
                self.cargar()
            except Exception as e:  # noqa: BLE001
                print("Error al reindexar:", e, flush=True)
            finally:
                self.reindexando = False

        threading.Thread(target=trabajo, daemon=True).start()

    def buscar(self, consulta, k):
        # Si cambio algun archivo, se reindexa aparte y mientras tanto se contesta con el indice anterior:
        # una busqueda nunca espera a un reindexado (el cambio se ve unos segundos despues).
        if self.firma() != self.firma_actual:
            self.reindexar_en_segundo_plano()
        with self.lock:
            indice = self.indice
        return indice.buscar(consulta, k)


def servidor():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import secrets
    if sys.stdout is None or sys.stderr is None:      # arrancado sin consola (pythonw): el registro va a un archivo
        registro = open(RAIZ / "servidor.log", "a", buffering=1, encoding="utf-8")
        sys.stdout = sys.stderr = registro
    if ARCHIVO_SERVIDOR.exists():
        ARCHIVO_SERVIDOR.unlink()
    motor = Motor()
    embeber(["calentamiento"])   # carga el modelo ahora: servidor.json solo aparece cuando de verdad esta listo
    token = secrets.token_hex(16)
    ultimo = [time.time()]

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            crudo = self.rfile.read(int(self.headers.get("Content-Length", 0)))   # siempre se lee el cuerpo antes de responder
            if self.headers.get("X-Token") != token or self.path != "/buscar":
                self.send_response(403)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            try:
                datos = json.loads(crudo.decode("utf-8"))
                cuerpo = json.dumps(motor.buscar(datos["consulta"], int(datos.get("k", K))), ensure_ascii=False).encode("utf-8")
                self.send_response(200)
            except Exception as e:  # noqa: BLE001
                cuerpo = json.dumps({"error": str(e)}).encode("utf-8")
                self.send_response(500)
            ultimo[0] = time.time()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            try:
                self.send_header("Content-Length", str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
            except OSError:
                pass   # el cliente ya cerro la conexion (por ejemplo, por su limite de espera)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)   # solo accesible desde este equipo
    ARCHIVO_SERVIDOR.write_text(json.dumps({"puerto": srv.server_address[1], "token": token, "pid": os.getpid()}), encoding="utf-8")

    def vigilar():
        while time.time() - ultimo[0] < INACTIVIDAD:
            time.sleep(30)
        ARCHIVO_SERVIDOR.unlink(missing_ok=True)
        os._exit(0)

    threading.Thread(target=vigilar, daemon=True).start()
    print(f"Servidor listo en 127.0.0.1:{srv.server_address[1]}", flush=True)
    try:
        srv.serve_forever()
    finally:
        ARCHIVO_SERVIDOR.unlink(missing_ok=True)


def consultar_servidor(consulta, k=K, espera=3.0):
    try:
        datos = json.loads(ARCHIVO_SERVIDOR.read_text(encoding="utf-8"))
        req = urllib.request.Request(
            f"http://127.0.0.1:{datos['puerto']}/buscar",
            data=json.dumps({"consulta": consulta, "k": k}).encode("utf-8"),
            headers={"X-Token": datos["token"], "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=espera) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def servidor_vivo():
    return consultar_servidor("ping", 1, espera=2.0) is not None


def arrancar():
    if servidor_vivo():
        return False
    RAIZ.mkdir(exist_ok=True)
    script = str(Path(__file__).resolve())
    if os.name == "nt":
        # Un servidor lanzado desde un gancho moria al terminar el gancho (el agente cierra su arbol de procesos).
        # Un proceso creado por WMI no cuelga del que lo lanza, asi que sobrevive. Con pythonw no abre ventana.
        sin_consola = Path(sys.executable).with_name("pythonw.exe")
        exe = str(sin_consola if sin_consola.exists() else sys.executable)
        ps = ("$si = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow=[uint16]0}; "
              "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
              "@{CommandLine=$env:RAG_CMD; CurrentDirectory=$env:RAG_DIR; ProcessStartupInformation=$si}; "
              "exit ([int]($r.ReturnValue -ne 0))")
        entorno = dict(os.environ, RAG_CMD=f'"{exe}" "{script}" servidor', RAG_DIR=str(RAIZ))
        try:
            if subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=entorno,
                              capture_output=True, timeout=30).returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            pass   # si WMI no esta disponible, se usa el metodo normal de abajo
    registro = open(RAIZ / "servidor.log", "ab")
    banderas = 0x00000008 | 0x00000200 if os.name == "nt" else 0   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([sys.executable, script, "servidor"], stdin=subprocess.DEVNULL,
                     stdout=registro, stderr=registro, creationflags=banderas, close_fds=True)
    return True


def parar():
    try:
        pid = json.loads(ARCHIVO_SERVIDOR.read_text(encoding="utf-8"))["pid"]
    except (OSError, ValueError, KeyError):
        print("El servidor no esta activo.")
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        os.kill(pid, 15)
    ARCHIVO_SERVIDOR.unlink(missing_ok=True)
    print("Servidor detenido.")


# ---------------------------------------------------------------- gancho del agente
def gancho():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    if os.environ.get("RAG_DESACTIVAR") == "1":
        return
    try:
        mensaje = (json.loads(sys.stdin.read()).get("prompt") or "").strip()
    except (ValueError, AttributeError):
        return
    if len(mensaje) < 15 or mensaje.startswith("/"):
        return
    if re.search(r"<task-notification>|\[SYSTEM NOTIFICATION", mensaje):
        return                            # avisos automaticos del sistema, no preguntas del usuario
    resultados = None
    for intento in range(6):              # nunca retrasa un mensaje mas de ~3 s: si el servidor arranca ahora, este mensaje va sin contexto
        resultados = consultar_servidor(mensaje, K)
        if resultados is not None:
            break
        if intento == 0:
            arrancar()
        time.sleep(0.5)
    if not isinstance(resultados, list):
        return
    # El mensaje debe tratar de algo del vault (mejor trozo >= umbral); entonces se admiten los trozos algo mas flojos
    # que traiga la fusion con palabras exactas (por ejemplo "marca 108").
    if not resultados or resultados[0]["sem_max"] < UMBRAL:
        return
    utiles = [r for r in resultados if r["sem"] >= UMBRAL - 0.10]
    if utiles:
        # Salida JSON documentada de los ganchos: additionalContext se inyecta en el contexto del modelo
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                  "additionalContext": formatear(utiles)}}, ensure_ascii=False))


# ---------------------------------------------------------------- ganchos del agente
def ganchos():
    """Registra los ganchos en .claude/settings.local.json del proyecto. Mezcla con lo que ya haya y no lo duplica."""
    destino = PROYECTO / ".claude" / "settings.local.json"
    datos = {}
    if destino.exists():
        try:
            datos = json.loads(destino.read_text(encoding="utf-8"))
        except ValueError:
            sys.exit(f"{destino} no es un JSON valido: arreglalo o borralo antes. No lo toco.")
        if not isinstance(datos, dict) or not isinstance(datos.get("hooks", {}), dict):
            sys.exit(f"{destino} tiene una forma inesperada (se esperaba un objeto con 'hooks'). No lo toco.")
    py = Path(sys.executable).as_posix()
    rag = Path(__file__).resolve().as_posix()
    nuevos = {"SessionStart": ("arrancar", 20, "Arrancando la búsqueda local del vault..."),
              "UserPromptSubmit": ("hook", 15, "Buscando contexto en el vault...")}
    hooks = datos.setdefault("hooks", {})
    agregados = []
    for evento, (argumento, limite, mensaje) in nuevos.items():
        grupos = hooks.setdefault(evento, [])
        ya = any(h.get("type") == "command" and h.get("args", [])[-2:] == [rag, argumento]
                 for g in grupos for h in g.get("hooks", []))
        if not ya:
            grupos.append({"hooks": [{"type": "command", "command": py, "args": [rag, argumento],
                                      "timeout": limite, "statusMessage": mensaje}]})
            agregados.append(evento)
    if not agregados:
        print("Los ganchos ya estaban registrados en", destino)
        return
    destino.parent.mkdir(exist_ok=True)
    if destino.exists():
        copia = destino.with_suffix(".json.bak")
        copia.write_text(destino.read_text(encoding="utf-8"), encoding="utf-8")
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Ganchos registrados en", destino, "->", ", ".join(agregados))
    print("Abre /hooks una vez o reinicia la sesion del agente para que se carguen.")


# ---------------------------------------------------------------- evaluacion
def evaluar():
    datos = json.loads((RAIZ / "evaluacion.json").read_text(encoding="utf-8"))
    indice = indice_en_memoria()
    pos, neg = datos["preguntas"], datos.get("negativas", [])
    print(f"{len(indice.trozos)} trozos | {len(pos)} preguntas con respuesta conocida | {len(neg)} sin relacion\n")
    print(f"{'modo':<10} {'acierto@1':>10} {'acierto@3':>10} {'acierto@5':>10} {'MRR':>7}")
    for modo in ("palabras", "semantico", "hibrido"):
        a1 = a3 = a5 = 0
        mrr = 0.0
        for p in pos:
            res = indice.buscar(p["p"], 5, modo, max_por_archivo=5)
            rangos = [n for n, r in enumerate(res, 1) if any(r["archivo"].endswith(e) for e in p["esperado"])]
            if rangos:
                r = rangos[0]
                a1 += r <= 1
                a3 += r <= 3
                a5 += r <= 5
                mrr += 1 / r
        n = len(pos)
        print(f"{modo:<10} {a1 / n:>10.0%} {a3 / n:>10.0%} {a5 / n:>10.0%} {mrr / n:>7.2f}")
    print("\nFallos del modo hibrido (esperado | lo que trajo primero):")
    for p in pos:
        res = indice.buscar(p["p"], 3, "hibrido", max_por_archivo=3)
        if not any(r["archivo"].endswith(e) for r in res for e in p["esperado"]):
            print(f"  - {p['p']}\n      esperado: {p['esperado'][0]}\n      trajo: {[r['archivo'].split('/')[-1] for r in res]}")
    sp = sorted(float(indice.puntuaciones(p["p"])[0].max()) for p in pos)
    sn = sorted(float(indice.puntuaciones(q)[0].max()) for q in neg) if neg else []
    print(f"\nSimilitud maxima (semantica): con respuesta en el vault min {sp[0]:.2f} | mediana {sp[len(sp) // 2]:.2f} | max {sp[-1]:.2f}")
    if sn:
        print(f"                              sin relacion               min {sn[0]:.2f} | mediana {sn[len(sn) // 2]:.2f} | max {sn[-1]:.2f}")
    print("\nSenales por pregunta (similitud maxima | palabras maxima):")
    for etiqueta, qs in (("CON respuesta en el vault", [p["p"] for p in pos]), ("SIN relacion", neg)):
        print(f"  {etiqueta}")
        for q in sorted(qs, key=lambda q: float(indice.puntuaciones(q)[0].max())):
            s, w = indice.puntuaciones(q)
            print(f"    sem {float(s.max()):.2f} | kw {float(w.max()):5.1f} | {q[:68]}")
    print("\numbral -> % de preguntas con respuesta que SI inyectan | % de preguntas sin relacion que inyectan (ruido)")
    for u in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65):
        print(f"  {u:.2f}  -> {sum(s >= u for s in sp) / len(sp):>4.0%} | {(sum(s >= u for s in sn) / len(sn)) if sn else 0:>4.0%}")


def principal():
    if sys.stdout is not None:        # con pythonw (servidor sin consola) no hay salida estandar
        sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "indexar":
        t0 = time.time()
        print(json.dumps(indexar(hablar=True), ensure_ascii=False), f"| {time.time() - t0:.1f} s")
    elif cmd == "buscar" and len(sys.argv) > 2:
        consulta = " ".join(sys.argv[2:])
        resultados = consultar_servidor(consulta, K) or indice_en_memoria().buscar(consulta, K)
        for n, r in enumerate(resultados, 1):
            print(f"{n}. {r['archivo']}:{r['ini']}-{r['fin']} ({r['tipo']}) sim {r['sem']:.2f} - {r['titulo']}")
            print("   " + r["texto"].strip()[:260].replace("\n", " ") + " ...")
    elif cmd == "servidor":
        servidor()
    elif cmd == "arrancar":
        arrancar()
    elif cmd == "parar":
        parar()
    elif cmd == "hook":
        gancho()
    elif cmd == "ganchos":
        ganchos()
    elif cmd == "evaluar":
        evaluar()
    else:
        print(__doc__)


if __name__ == "__main__":
    principal()
