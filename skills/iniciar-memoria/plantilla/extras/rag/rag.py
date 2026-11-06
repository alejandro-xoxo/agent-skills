#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-Proprietary — Copyright (c) 2026 alejandro-xoxo. All rights reserved.
# Copyright (c) 2026 alejandro-xoxo
"""Local semantic search (RAG) over the Obsidian vault and the project's docs.

Everything happens on this machine: the vector model is downloaded once and nothing goes out to any API.

Usage (with the Python of this folder's environment):
  rag.py index              builds or updates the index (only recomputes what changed)
  rag.py search "question"  shows the best chunks, with file and lines
  rag.py server             local server that keeps the model loaded and reindexes by itself
  rag.py start              starts the server in the background if it is not running
  rag.py stop               stops the server
  rag.py hook               called by the agent before every message: reads the message from stdin and
                            writes the retrieved context to stdout (nothing if nothing is relevant)
  rag.py hooks              registers the hooks in .claude/settings.local.json (merges, overwrites nothing)
  rag.py evaluate           measures the search quality with evaluation.json

Environment variables: RAG_DISABLE=1 turns off automatic retrieval; RAG_THRESHOLD, RAG_MODEL, RAG_MODELS_DIR, RAG_CURATED_WEIGHT.
The older Spanish names (RAG_DESACTIVAR, RAG_UMBRAL, RAG_MODELO, RAG_MODELOS, RAG_PESO_CURADO) and the Spanish command names
(indexar, buscar, servidor, arrancar, parar, ganchos, evaluar) are still accepted.
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


def env(*names, default=None):
    """First environment variable that is set among `names` (new English name first, older Spanish name after)."""
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return default


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
INDEX = ROOT / "index"
# The model (about 0.6 GB) is shared among all projects so it is not downloaded every time (RAG_MODELS_DIR changes it)
_cache = Path.home() / ".cache"
MODELS = Path(env("RAG_MODELS_DIR", "RAG_MODELOS") or (_cache / "rag-modelos" if (_cache / "rag-modelos").exists() and not (_cache / "rag-models").exists() else _cache / "rag-models"))
SERVER_FILE = ROOT / "server.json"
MODEL = env("RAG_MODEL", "RAG_MODELO", default="jinaai/jina-embeddings-v2-base-es")
THRESHOLD = float(env("RAG_THRESHOLD", "RAG_UMBRAL", default="0.50"))   # minimum similarity to inject context (tuned with evaluate)
# Curated content outranks raw material: in the fusion, its results weigh more (adjustable with RAG_CURATED_WEIGHT)
CURATED_WEIGHT = float(env("RAG_CURATED_WEIGHT", "RAG_PESO_CURADO", default="1.25"))
KIND_WEIGHT = {"curated note": CURATED_WEIGHT, "project state": CURATED_WEIGHT, "raw source": 1.0}
K = 4                      # chunks returned
MAX_CHUNK = 1500           # characters per chunk
MAX_CONTEXT = 3200         # maximum characters injected in each message
IDLE = 30 * 60             # the server shuts itself down after 30 minutes without use

# Words ignored by the keyword search (Spanish and English; the default model understands both languages)
STOPWORDS = set("""a al algo como con cual cuales cuando de del el ella ellas ellos en entre era es esta estan este esto
estos fue ha han hay la las le les lo los me mi mas mucho muy no nos o para pero por que se si sin sobre su sus te tu
un una uno unos y ya yo
about after all also an and any are as at be been but by can did do does for from had has have how if in into is it its
may more most no not of on or our so some such than that the their then there these they this to was we were what when
where which who why will with would you your""".split())


# ---------------------------------------------------------------- sources
def vault_path():
    agents = PROJECT / "AGENTS.md"
    if not agents.exists():
        sys.exit("Cannot find AGENTS.md in the project folder: that is where the vault path is (the ## Memory block).")
    m = re.search(r"(?:Obsidian vault|Vault de Obsidian):\s*`([^`]+)`", agents.read_text(encoding="utf-8"))
    if not m:
        sys.exit("AGENTS.md has no 'Obsidian vault: `path`' line in the ## Memory block.")
    vault = Path(m.group(1))
    if not vault.is_absolute():       # in the template the vault is the local "knowledge/" folder
        vault = PROJECT / vault
    if not vault.is_dir():
        sys.exit(f"The vault does not exist at this path: {vault}")
    return vault


def list_sources():
    """(path, label, kind). Folders whose name contains 'sources' (or 'fuentes') are raw material."""
    vault = vault_path()
    sources = []
    for f in sorted(vault.rglob("*.md")):
        rel = f.relative_to(vault)
        if ".obsidian" in rel.parts:
            continue
        raw = any(("sources" in p.lower() or "fuentes" in p.lower()) for p in rel.parts[:-1])
        sources.append((f, "vault/" + rel.as_posix(), "raw source" if raw else "curated note"))
    for name in ("STATE.md", "ESTADO.md", "DECISIONS.md"):
        f = PROJECT / "docs" / name
        if f.exists():
            sources.append((f, "docs/" + name, "project state"))
    return sources


def read(f):
    return f.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")


# ---------------------------------------------------------------- chunking
HEADING = re.compile(r"^(#{1,3})\s+(.*\S)\s*$")
ROLE = re.compile(r"^\*\*(User|Usuario|Claude|Assistant)\*\*\s*$")


def skip_frontmatter(lines):
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return i + 1
    return 0


def blocks_by_heading(lines, start, note):
    blocks, current, title = [], None, note
    for n in range(start, len(lines)):
        m = HEADING.match(lines[n])
        if m and current is not None:
            blocks.append(current)
            current = None
        if m:
            title = m.group(2) if len(m.group(1)) == 1 else f"{note} > {m.group(2)}"
        if current is None:
            current = [n + 1, title, []]
        current[2].append(lines[n])
    if current:
        blocks.append(current)
    return [(b[0], b[0] + len(b[2]) - 1, b[1], "\n".join(b[2])) for b in blocks if any(x.strip() for x in b[2])]


def blocks_by_separator(lines, start, name):
    """Raw material (conversations): turns are separated by a '---' line."""
    rough, current, l0 = [], [], start + 1
    for n in range(start, len(lines)):
        if lines[n].strip() == "---":
            if any(x.strip() for x in current):
                rough.append((l0, n, current))
            current, l0 = [], n + 2
        else:
            current.append(lines[n])
    if any(x.strip() for x in current):
        rough.append((l0, len(lines), current))
    out = []
    for a, b, ls in rough:
        role = next((ROLE.match(x).group(1) for x in ls if ROLE.match(x)), None)
        out.append((a, b, name + (f" ({role})" if role else ""), "\n".join(ls)))
    return out


def pack(blocks, fill, minimum=350, maximum=MAX_CHUNK):
    """Splits huge blocks and joins small ones. With fill=True it joins consecutive turns up to the maximum."""
    pieces = []
    for a, b, tit, txt in blocks:
        if len(txt) <= maximum:
            pieces.append((a, b, tit, txt))
            continue
        buf, n0, size = [], a, 0
        for i, line in enumerate(txt.split("\n")):
            if size + len(line) + 1 > maximum and buf:
                pieces.append((n0, a + i - 1, tit, "\n".join(buf)))
                buf, n0, size = [], a + i, 0
            while len(line) > maximum:
                pieces.append((a + i, a + i, tit, line[:maximum]))
                line = line[maximum:]
            buf.append(line)
            size += len(line) + 1
        if buf:
            pieces.append((n0, b, tit, "\n".join(buf)))
    out = []
    for p in pieces:
        if out:
            q = out[-1]
            joined = len(q[3]) + len(p[3]) + 1 <= maximum
            if joined and (fill or len(q[3]) < minimum):
                out[-1] = (q[0], p[1], q[2], q[3] + "\n" + p[3])
                continue
        out.append(p)
    return out


def chunk(text, kind, name):
    lines = text.split("\n")
    start = skip_frontmatter(lines)
    if kind == "raw source":
        return pack(blocks_by_separator(lines, start, name), fill=True)
    return pack(blocks_by_heading(lines, start, name), fill=False)


# ---------------------------------------------------------------- vectors
_model = None


def model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        MODELS.mkdir(parents=True, exist_ok=True)
        _model = TextEmbedding(MODEL, cache_dir=str(MODELS))
    return _model


def embed(texts):
    import numpy as np
    v = np.array(list(model().embed(texts)), dtype=np.float32)
    n = np.linalg.norm(v, axis=1, keepdims=True)
    n[n == 0] = 1
    return v / n


def vectorizable_text(t):
    return f"{t['title']}\n{t['text']}"


# ---------------------------------------------------------------- index
def read_index():
    import numpy as np
    try:
        state = json.loads((INDEX / "state.json").read_text(encoding="utf-8"))
        chunks = json.loads((INDEX / "chunks.json").read_text(encoding="utf-8"))
        vectors = np.load(INDEX / "vectors.npy")
        if len(chunks) != len(vectors):
            raise ValueError("inconsistent index")
        return state, chunks, vectors
    except (OSError, ValueError, KeyError):
        return None


def save_index(state, chunks, vectors):
    import numpy as np
    INDEX.mkdir(parents=True, exist_ok=True)
    for name, content in (("chunks.json", json.dumps(chunks, ensure_ascii=False)),
                          ("state.json", json.dumps(state, ensure_ascii=False, indent=1))):
        tmp = INDEX / (name + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, INDEX / name)
    tmp = INDEX / "vectors.tmp.npy"
    np.save(tmp, vectors)
    os.replace(tmp, INDEX / "vectors.npy")


def build_index(talk=False):
    """Incremental: reuses the vectors of the files that did not change."""
    import numpy as np
    previous = read_index()
    previous_by_file = {}
    if previous and previous[0].get("model") == MODEL:
        for i, t in enumerate(previous[1]):
            previous_by_file.setdefault(t["file"], []).append(i)
    result, hashes, reused, new = [], {}, 0, 0
    for f, label, kind in list_sources():
        text = read(f)
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()
        hashes[label] = h
        if previous and previous[0]["files"].get(label) == h and label in previous_by_file:
            for i in previous_by_file[label]:
                result.append([previous[1][i], previous[2][i]])
                reused += 1
            continue
        for a, b, tit, txt in chunk(text, kind, f.stem):
            result.append([{"file": label, "start": a, "end": b, "title": tit, "kind": kind, "text": txt}, None])
            new += 1
    pending = [i for i, (_, v) in enumerate(result) if v is None]
    if pending:
        if talk:
            print(f"Computing vectors for {len(pending)} chunks (the first time it downloads the model)...", flush=True)
        vs = embed([vectorizable_text(result[i][0]) for i in pending])
        for j, i in enumerate(pending):
            result[i][1] = vs[j]
    if not result:
        sys.exit("There is nothing to index.")
    save_index({"model": MODEL, "files": hashes}, [t for t, _ in result], np.vstack([v for _, v in result]))
    return {"files": len(hashes), "chunks": len(result), "new": new, "reused": reused}


# ---------------------------------------------------------------- search
def tokens(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return [w for w in re.findall(r"[a-z0-9]+", t) if len(w) > 1 and w not in STOPWORDS]


class BM25:
    def __init__(self, docs):
        import numpy as np
        self.np = np
        self.tf = [Counter(d) for d in docs]
        self.n = len(docs)
        self.length = np.array([len(d) for d in docs], dtype=np.float32)
        self.mean = float(self.length.mean()) or 1.0
        df = Counter()
        for tf in self.tf:
            df.update(tf.keys())
        self.idf = {t: math.log(1 + (self.n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def score(self, query):
        s = self.np.zeros(self.n, dtype=self.np.float32)
        for t in set(query):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(t, 0)
                if f:
                    s[i] += idf * f * 2.5 / (f + 1.5 * (0.25 + 0.75 * self.length[i] / self.mean))
        return s


class Index:
    def __init__(self, chunks, vectors):
        self.chunks, self.vectors = chunks, vectors
        self.bm25 = BM25([tokens(t["title"] + " " + t["text"]) for t in chunks])

    def scores(self, query):
        sem = self.vectors @ embed([query])[0]
        kw = self.bm25.score(tokens(query))
        return sem, kw

    def search(self, query, k=K, mode="hybrid", max_per_file=2):
        import numpy as np
        sem, kw = self.scores(query)
        if mode == "semantic":
            order = list(np.argsort(-sem))
        elif mode == "keywords":
            order = [i for i in np.argsort(-kw) if kw[i] > 0]
        else:  # rank fusion (RRF)
            fused = Counter()
            for r, i in enumerate(np.argsort(-sem)[:60]):
                fused[int(i)] += 1 / (60 + r)
            for r, i in enumerate([i for i in np.argsort(-kw)[:60] if kw[i] > 0]):
                fused[int(i)] += 1 / (60 + r)
            for i in fused:
                fused[i] *= KIND_WEIGHT.get(self.chunks[i]["kind"], 1.0)
            order = [i for i, _ in fused.most_common()]
        out, per_file, sem_max = [], Counter(), float(sem.max())
        for i in order:
            t = self.chunks[int(i)]
            if per_file[t["file"]] >= max_per_file:
                continue
            per_file[t["file"]] += 1
            out.append(dict(t, sem=float(sem[i]), kw=float(kw[i]), sem_max=sem_max))
            if len(out) >= k:
                break
        return out


def index_in_memory():
    previous = read_index()
    if not previous or previous[0].get("model") != MODEL:
        build_index(talk=True)
        previous = read_index()
    return Index(previous[1], previous[2])


def format_results(results):
    header = ("[Context retrieved automatically from the vault and from docs/ by local semantic search. It may be "
              "incomplete or outdated: verify it in the cited source before using it, and ignore it if it is not relevant.]")
    parts, total = [header], 0
    for n, r in enumerate(results, 1):
        excerpt = r["text"].strip()
        if len(excerpt) > 650:
            excerpt = excerpt[:650].rsplit(" ", 1)[0] + " [...]"
        block = f"{n}. {r['file']}:{r['start']}-{r['end']} ({r['kind']}, similarity {r['sem']:.2f}) - {r['title']}\n{excerpt}"
        if total + len(block) > MAX_CONTEXT and n > 1:
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts)


# ---------------------------------------------------------------- server
class Engine:
    """Keeps the model and the index in memory, and reindexes by itself if any file changes."""

    def __init__(self):
        self.lock = threading.Lock()
        self.reindexing = False
        self.load()

    def signature(self):
        return tuple((e, f.stat().st_mtime_ns, f.stat().st_size) for f, e, _ in list_sources())

    def load(self):
        # The signature is taken BEFORE indexing: if a file changes while indexing, the signature goes stale
        # and the next search triggers another pass, so no change is ever lost.
        signature = self.signature()
        build_index()
        previous = read_index()
        fresh = Index(previous[1], previous[2])
        with self.lock:
            self.index, self.current_signature = fresh, signature

    def reindex_in_background(self):
        if self.reindexing:
            return
        self.reindexing = True

        def work():
            try:
                self.load()
            except Exception as e:  # noqa: BLE001
                print("Error while reindexing:", e, flush=True)
            finally:
                self.reindexing = False

        threading.Thread(target=work, daemon=True).start()

    def search(self, query, k):
        # If a file changed, it is reindexed separately and meanwhile the previous index answers:
        # a search never waits for a reindex (the change shows up a few seconds later).
        if self.signature() != self.current_signature:
            self.reindex_in_background()
        with self.lock:
            index = self.index
        return index.search(query, k)


def server():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import secrets
    if sys.stdout is None or sys.stderr is None:      # started without a console (pythonw): the log goes to a file
        log = open(ROOT / "server.log", "a", buffering=1, encoding="utf-8")
        sys.stdout = sys.stderr = log
    if SERVER_FILE.exists():
        SERVER_FILE.unlink()
    engine = Engine()
    embed(["warm-up"])   # loads the model now: server.json only appears when it is really ready
    token = secrets.token_hex(16)
    last = [time.time()]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))   # the body is always read before answering
            if self.headers.get("X-Token") != token or self.path != "/search":
                self.send_response(403)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            try:
                data = json.loads(raw.decode("utf-8"))
                body = json.dumps(engine.search(data["query"], int(data.get("k", K))), ensure_ascii=False).encode("utf-8")
                self.send_response(200)
            except Exception as e:  # noqa: BLE001
                body = json.dumps({"error": str(e)}).encode("utf-8")
                self.send_response(500)
            last[0] = time.time()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            try:
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                pass   # the client already closed the connection (for example, because of its timeout)

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)   # reachable only from this machine
    SERVER_FILE.write_text(json.dumps({"port": srv.server_address[1], "token": token, "pid": os.getpid()}), encoding="utf-8")

    def watch():
        while time.time() - last[0] < IDLE:
            time.sleep(30)
        SERVER_FILE.unlink(missing_ok=True)
        os._exit(0)

    threading.Thread(target=watch, daemon=True).start()
    print(f"Server ready on 127.0.0.1:{srv.server_address[1]}", flush=True)
    try:
        srv.serve_forever()
    finally:
        SERVER_FILE.unlink(missing_ok=True)


def query_server(query, k=K, wait=3.0):
    try:
        data = json.loads(SERVER_FILE.read_text(encoding="utf-8"))
        req = urllib.request.Request(
            f"http://127.0.0.1:{data['port']}/search",
            data=json.dumps({"query": query, "k": k}).encode("utf-8"),
            headers={"X-Token": data["token"], "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=wait) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return None


def server_alive():
    return query_server("ping", 1, wait=2.0) is not None


def start():
    if server_alive():
        return False
    ROOT.mkdir(exist_ok=True)
    script = str(Path(__file__).resolve())
    if os.name == "nt":
        # A server launched from a hook used to die when the hook ended (the agent kills its process tree).
        # A process created through WMI does not hang from whoever launched it, so it survives. With pythonw it opens no window.
        no_console = Path(sys.executable).with_name("pythonw.exe")
        exe = str(no_console if no_console.exists() else sys.executable)
        ps = ("$si = New-CimInstance -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow=[uint16]0}; "
              "$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
              "@{CommandLine=$env:RAG_CMD; CurrentDirectory=$env:RAG_DIR; ProcessStartupInformation=$si}; "
              "exit ([int]($r.ReturnValue -ne 0))")
        environment = dict(os.environ, RAG_CMD=f'"{exe}" "{script}" server', RAG_DIR=str(ROOT))
        try:
            if subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=environment,
                              capture_output=True, timeout=30).returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            pass   # if WMI is not available, the normal method below is used
    log = open(ROOT / "server.log", "ab")
    flags = 0x00000008 | 0x00000200 if os.name == "nt" else 0   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([sys.executable, script, "server"], stdin=subprocess.DEVNULL,
                     stdout=log, stderr=log, creationflags=flags, close_fds=True)
    return True


def stop():
    try:
        pid = json.loads(SERVER_FILE.read_text(encoding="utf-8"))["pid"]
    except (OSError, ValueError, KeyError):
        print("The server is not running.")
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        os.kill(pid, 15)
    SERVER_FILE.unlink(missing_ok=True)
    print("Server stopped.")


# ---------------------------------------------------------------- the agent's hook
def hook():
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    if env("RAG_DISABLE", "RAG_DESACTIVAR") == "1":
        return
    try:
        message = (json.loads(sys.stdin.read()).get("prompt") or "").strip()
    except (ValueError, AttributeError):
        return
    if len(message) < 15 or message.startswith("/"):
        return
    if re.search(r"<task-notification>|\[SYSTEM NOTIFICATION", message):
        return                            # automatic system notices, not questions from the user
    results = None
    for attempt in range(6):              # never delays a message by more than ~3 s: if the server is starting now, this message goes without context
        results = query_server(message, K)
        if results is not None:
            break
        if attempt == 0:
            start()
        time.sleep(0.5)
    if not isinstance(results, list):
        return
    # The message must be about something in the vault (best chunk >= threshold); then the somewhat weaker chunks
    # that the exact-words fusion brings in (for example "brand 108") are admitted.
    if not results or results[0]["sem_max"] < THRESHOLD:
        return
    useful = [r for r in results if r["sem"] >= THRESHOLD - 0.10]
    if useful:
        # Documented JSON output of the hooks: additionalContext is injected into the model's context
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                                  "additionalContext": format_results(useful)}}, ensure_ascii=False))


# ---------------------------------------------------------------- registering the agent's hooks
def register_hooks():
    """Registers the hooks in the project's .claude/settings.local.json. Merges with what is already there and does not duplicate it."""
    target = PROJECT / ".claude" / "settings.local.json"
    data = {}
    if target.exists():
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except ValueError:
            sys.exit(f"{target} is not valid JSON: fix or delete it first. I am not touching it.")
        if not isinstance(data, dict) or not isinstance(data.get("hooks", {}), dict):
            sys.exit(f"{target} has an unexpected shape (an object with 'hooks' was expected). I am not touching it.")
    py = Path(sys.executable).as_posix()
    rag = Path(__file__).resolve().as_posix()
    new = {"SessionStart": ("start", 20, "Starting the local vault search..."),
           "UserPromptSubmit": ("hook", 15, "Searching the vault for context...")}
    hooks = data.setdefault("hooks", {})
    added = []
    for event, (argument, limit, message) in new.items():
        groups = hooks.setdefault(event, [])
        already = any(h.get("type") == "command" and h.get("args", [])[-2:] == [rag, argument]
                      for g in groups for h in g.get("hooks", []))
        if not already:
            groups.append({"hooks": [{"type": "command", "command": py, "args": [rag, argument],
                                      "timeout": limit, "statusMessage": message}]})
            added.append(event)
    if not added:
        print("The hooks were already registered in", target)
        return
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        backup = target.with_suffix(".json.bak")
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Hooks registered in", target, "->", ", ".join(added))
    print("Open /hooks once or restart the agent session so they get loaded.")


# ---------------------------------------------------------------- evaluation
def evaluate():
    data = json.loads((ROOT / "evaluation.json").read_text(encoding="utf-8"))
    index = index_in_memory()
    pos, neg = data["questions"], data.get("negatives", [])
    print(f"{len(index.chunks)} chunks | {len(pos)} questions with a known answer | {len(neg)} unrelated\n")
    print(f"{'mode':<10} {'hit@1':>10} {'hit@3':>10} {'hit@5':>10} {'MRR':>7}")
    for mode in ("keywords", "semantic", "hybrid"):
        a1 = a3 = a5 = 0
        mrr = 0.0
        for p in pos:
            res = index.search(p["q"], 5, mode, max_per_file=5)
            ranks = [n for n, r in enumerate(res, 1) if any(r["file"].endswith(e) for e in p["expected"])]
            if ranks:
                r = ranks[0]
                a1 += r <= 1
                a3 += r <= 3
                a5 += r <= 5
                mrr += 1 / r
        n = len(pos)
        print(f"{mode:<10} {a1 / n:>10.0%} {a3 / n:>10.0%} {a5 / n:>10.0%} {mrr / n:>7.2f}")
    print("\nMisses of the hybrid mode (expected | what it brought first):")
    for p in pos:
        res = index.search(p["q"], 3, "hybrid", max_per_file=3)
        if not any(r["file"].endswith(e) for r in res for e in p["expected"]):
            print(f"  - {p['q']}\n      expected: {p['expected'][0]}\n      brought: {[r['file'].split('/')[-1] for r in res]}")
    sp = sorted(float(index.scores(p["q"])[0].max()) for p in pos)
    sn = sorted(float(index.scores(q)[0].max()) for q in neg) if neg else []
    print(f"\nMaximum similarity (semantic): with an answer in the vault min {sp[0]:.2f} | median {sp[len(sp) // 2]:.2f} | max {sp[-1]:.2f}")
    if sn:
        print(f"                               unrelated                   min {sn[0]:.2f} | median {sn[len(sn) // 2]:.2f} | max {sn[-1]:.2f}")
    print("\nSignals per question (maximum similarity | maximum keywords):")
    for label, qs in (("WITH an answer in the vault", [p["q"] for p in pos]), ("UNRELATED", neg)):
        print(f"  {label}")
        for q in sorted(qs, key=lambda q: float(index.scores(q)[0].max())):
            s, w = index.scores(q)
            print(f"    sem {float(s.max()):.2f} | kw {float(w.max()):5.1f} | {q[:68]}")
    print("\nthreshold -> % of questions with an answer that DO inject | % of unrelated questions that inject (noise)")
    for u in (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65):
        print(f"  {u:.2f}  -> {sum(s >= u for s in sp) / len(sp):>4.0%} | {(sum(s >= u for s in sn) / len(sn)) if sn else 0:>4.0%}")


# Spanish command names from earlier versions still work
ALIASES = {"indexar": "index", "buscar": "search", "servidor": "server", "arrancar": "start", "parar": "stop",
           "ganchos": "hooks", "evaluar": "evaluate"}


def main():
    if sys.stdout is not None:        # with pythonw (server without a console) there is no standard output
        sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    cmd = ALIASES.get(cmd, cmd)
    if cmd == "index":
        t0 = time.time()
        print(json.dumps(build_index(talk=True), ensure_ascii=False), f"| {time.time() - t0:.1f} s")
    elif cmd == "search" and len(sys.argv) > 2:
        query = " ".join(sys.argv[2:])
        results = query_server(query, K) or index_in_memory().search(query, K)
        for n, r in enumerate(results, 1):
            print(f"{n}. {r['file']}:{r['start']}-{r['end']} ({r['kind']}) sim {r['sem']:.2f} - {r['title']}")
            print("   " + r["text"].strip()[:260].replace("\n", " ") + " ...")
    elif cmd == "server":
        server()
    elif cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "hook":
        hook()
    elif cmd == "hooks":
        register_hooks()
    elif cmd == "evaluate":
        evaluate()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
