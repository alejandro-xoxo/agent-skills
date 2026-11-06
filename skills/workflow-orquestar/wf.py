#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-Proprietary — Copyright (c) 2026 alejandro-xoxo. All rights reserved.
# Copyright (c) 2026 alejandro-xoxo
"""wf: orchestrator of CLI agents (OpenCode, agy and Codex).

The leading agent (an LLM) writes a short script with the primitives (`phase`, `log`, `agent`, `parallel`, `pipeline`, `task`, `dag`, `check_collisions`, `auto_integrate`),
launches it with `python wf.py script.py` and reads the result. Each `agent()` runs a real CLI (`opencode run`, `agy -p` or `codex exec`),
requires the result inside a pair of markers, validates it against a JSON schema and returns it already converted to Python.

    python wf.py script.py [--args '{"a": 1}'] [--dry]
    python wf.py --monitor

The script may use top-level `await` and already has the primitives, plus `args` and `WORKSPACES`. With `--dry` nothing is launched:
it only prints the commands.
"""
from __future__ import annotations

import ast
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
BLOCK = re.compile(r"<{2,3}\s*WF_RESULT\s*(.*?)\s*WF_RESULT\s*>{2,3}", re.S)        # tolerates «<<» and spaces
UNAVAILABLE = re.compile(r"RESOURCE_EXHAUSTED|quota|need to sign in|sign in to use|not signed in|unauthori[sz]ed|rate.?limit|"
                         r"insufficient (credits|funds|balance)|no credentials|payment required|credit", re.I)

# Estimated prices per million tokens (in, out) in USD
COSTS_PER_MILLION = {
    "gemini-3.8-flash-high": (0.075, 0.30),
    "gemini-3.8-flash-medium": (0.075, 0.30),
    "gemini-3.8-flash-low": (0.075, 0.30),
    "gemini-4-argon-high": (1.25, 5.00),
    "claude-sonnet-5-5-medium": (3.00, 15.00),
    "default": (0.0, 0.0),  # free models by default (opencode)
}

# Quality levels per worker (editable in models.json)
TIERS = {
    # OpenCode: free models (nemotron, deepseek, minimax)
    "opencode": {"max": "opencode/nemotron-3-ultra-free", "pro": "opencode/nemotron-3-ultra-free",
                 "standard": "opencode/deepseek-v4.1-flash-free", "fast": "opencode/minimax-m3.1-flash-free"},
    # Antigravity CLI with Gemini / Claude
    "agy": {"max": "gemini-4-argon-high", "pro": "gemini-3.8-flash-high", "standard": "gemini-3.8-flash-medium",
            "fast": "gemini-3.8-flash-low", "design": "claude-sonnet-5-5-medium"},
    # Codex (OpenAI)
    "codex": {"max": "default", "pro": "default", "standard": "default", "fast": "default"},
}
try:
    for _w, _m in json.loads((HERE / "models.json").read_text(encoding="utf-8")).items():
        TIERS.setdefault(_w, {}).update(_m)
except (OSError, ValueError):
    pass

DRY = False
MAX_PARALLEL = int(os.environ.get("WF_MAX_PARALLEL", "4"))
CLI_WORKERS = {"claude": [], "agy": ["agy"], "opencode": ["opencode"], "codex": ["codex"]}


def orchestrator() -> str:
    """The orchestrator CLI the person chose at install time (`orchestrator.json`, or the older name `orquestador.json`); "claude" if there is no file."""
    for name, key in (("orchestrator.json", "orchestrator"), ("orquestador.json", "orquestador")):
        try:
            return str(json.loads((HERE / name).read_text(encoding="utf-8")).get(key, "claude"))
        except (OSError, ValueError, AttributeError):
            continue
    return "claude"


def default_workers() -> tuple[str, ...]:
    """Order of preference: opencode first (free) and agy as a fallback. The orchestrator CLI goes last."""
    base = [w for w in os.environ.get("WF_WORKERS", "opencode,agy").split(",") if w]
    mine = CLI_WORKERS.get(orchestrator(), [])
    return tuple([w for w in base if w not in mine] + [w for w in base if w in mine])


DEFAULT_WORKERS = default_workers()
RUN_ID = datetime.now().strftime("%Y%m%d-%H%M%S")
RUN_DIR = Path(os.environ.get("WF_RUNS") or tempfile.gettempdir()) / "wf-runs" / RUN_ID
EXTRA_ENV: dict[str, str] = {}
DEAD: set[str] = set()
WORKTREES: list[tuple[str, str, str]] = []                      # (branch, folder, repository)
STATS: list[dict] = []
_phase = ""
_counter = 0
_sem: asyncio.Semaphore | None = None
_start_time = time.time()


class WorkerUnavailable(RuntimeError):
    """The CLI is missing, has no session or ran out of quota."""


class WorkerError(RuntimeError):
    """The agent finished but without a valid result."""


# ---------------------------------------------------------------- logging and telemetry
def log(*parts) -> None:
    line = f"[{datetime.now():%H:%M:%S}]{f' [{_phase}]' if _phase else ''} " + " ".join(str(p) for p in parts)
    print(line, flush=True)
    try:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        with open(RUN_DIR / "log.txt", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def phase(name: str) -> None:
    global _phase
    _phase = name
    log("=== phase:", name)
    update_status()


def update_status(worker_num: int | None = None, **kwargs) -> None:
    """Writes the real-time state to disk so monitor.py can display it."""
    try:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        status_file = RUN_DIR / "status.json"
        data = {"run_id": RUN_ID, "phase": _phase, "workers": {}}
        if status_file.exists():
            try:
                data = json.loads(status_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        data["phase"] = _phase
        data["run_id"] = RUN_ID
        if worker_num is not None:
            w_str = str(worker_num)
            w_dict = data.setdefault("workers", {}).setdefault(w_str, {})
            w_dict["n"] = worker_num
            w_dict.update(kwargs)
        status_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def estimate_tokens(prompt_text: str, output_text: str) -> tuple[int, int]:
    """Estimates input and output tokens (~3.8 characters per token)."""
    return max(1, int(len(prompt_text) / 3.8)), max(1, int(len(output_text) / 3.8))


def estimate_cost(model: str, in_tok: int, out_tok: int) -> float:
    r_in, r_out = COSTS_PER_MILLION.get(model, COSTS_PER_MILLION["default"])
    return (in_tok / 1_000_000) * r_in + (out_tok / 1_000_000) * r_out


# ---------------------------------------------------------------- schema
def validate(value, schema, path="result") -> None:
    """Minimal JSON Schema validation."""
    if not isinstance(schema, dict) or not schema:
        return
    types = {"object": dict, "array": list, "string": str, "number": (int, float), "integer": int, "boolean": bool, "null": type(None)}
    t = schema.get("type")
    if t == "number":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif t == "integer":
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif t in types:
        ok = isinstance(value, types[t])
    else:
        ok = True
    if not ok:
        raise ValueError(f"{path}: expected {t}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValueError(f"{path}: must be one of {schema['enum']}")
    if t == "object":
        for k in schema.get("required", []):
            if k not in value:
                raise ValueError(f"{path}: missing '{k}'")
        for k, sub in schema.get("properties", {}).items():
            if k in value:
                validate(value[k], sub, f"{path}.{k}")
    if t == "array" and "items" in schema:
        for i, v in enumerate(value):
            validate(v, schema["items"], f"{path}[{i}]")


def extract(text: str, schema):
    clean = ANSI.sub("", text)
    is_text = isinstance(schema, dict) and schema.get("type") == "string"
    last_err = "there is no result block"
    for raw in reversed(BLOCK.findall(clean)):
        try:
            value = json.loads(raw)
        except ValueError:
            if is_text and raw.strip() and "<result" not in raw:
                return raw.strip()
            last_err = "the block is not valid JSON"
            continue
        try:
            validate(value, schema)
            return value
        except ValueError as ex:
            last_err = str(ex)
    raise WorkerError(last_err)


def example(schema) -> str:
    t = schema.get("type") if isinstance(schema, dict) else None
    if "enum" in (schema or {}):
        return json.dumps(schema["enum"][0], ensure_ascii=False)
    if t == "object":
        props = schema.get("properties", {})
        return "{" + ", ".join(f'"{k}": {example(v)}' for k, v in props.items()) + "}" if props else "{}"
    if t == "array":
        item = example(schema.get("items", {"type": "string"}))
        return f"[{item}, {item}]"
    return {"integer": "0", "number": "0.0", "boolean": "true", "null": "null"}.get(t, '"text"')


CAVEMAN = os.environ.get("WF_CAVEMAN", "1") != "0"
STYLE = ("STYLE (ultracave): answer with the fewest words possible. Fragments, no greetings, do not repeat the task, no final summary and no "
         "explaining what you are about to do. Facts, numbers, paths, code, commands and error messages, EXACT. Never drop a negation "
         "(no, never, only, except). This applies to your text and to the text fields of the result. If something can be read two "
         "ways, or there is a security risk or an irreversible action, use full sentences.")


def wrap(prompt: str, schema) -> str:
    if CAVEMAN:
        prompt = f"{prompt.rstrip()}\n\n{STYLE}"
    if isinstance(schema, dict) and schema.get("type") == "string":
        shape, form = "free text (no JSON or quotes)", ""
    else:
        shape = "the value as valid JSON, ONLY the value: do not wrap it in another structure and do not copy the schema"
        form = f"Expected shape (the values are placeholders, they only show the shape): {example(schema)}\n"
    return (f"{prompt.rstrip()}\n\n---\nRESPONSE FORMAT (mandatory): end with the result between these two lines and nothing "
            f"else between them. Content: {shape}.\n{form}Schema to validate against: {json.dumps(schema, ensure_ascii=False)}\n"
            "<<<WF_RESULT\n<result here>\nWF_RESULT>>>\n")


# ---------------------------------------------------------------- workers
def _opencode_native() -> Path | None:
    cmd = shutil.which("opencode.cmd") or shutil.which("opencode")
    if not cmd:
        return None
    base = Path(cmd).resolve().parent / "node_modules" / "@opencode" / "cli" / "node_modules" / "@opencode"
    for pkg in ("cli-windows-x64", "cli-windows-x64-baseline", "cli-linux-x64", "cli-darwin-arm64", "cli-darwin-x64"):
        for name in ("opencode.exe", "opencode"):
            if (base / pkg / "bin" / name).is_file():
                return base / pkg / "bin" / name
    return None


def _opencode(model: str, prompt: str, cwd: Path, edit: bool, timeout: int, tmp: Path) -> list[str]:
    exe = _opencode_native()
    if exe is None:
        raise WorkerUnavailable("cannot find the native opencode.exe (npm install -g @opencode/cli)")
    if len(prompt) > 28000:
        raise ValueError("task too long to pass as an argument: put the context in project files and refer to them")
    argv = [str(exe), "run", "--standalone", "-m", model, "--agent", "build" if edit else "plan"]
    if edit:
        argv.append("--auto")
    return argv + [prompt]


def _agy(model: str, prompt: str, cwd: Path, edit: bool, timeout: int, tmp: Path) -> list[str]:
    exe = shutil.which("agy")
    if not exe:
        raise WorkerUnavailable("agy is not installed")
    return [exe, "-p", prompt, "--mode", "accept-edits" if edit else "plan", "--model", model,
            "--print-timeout", f"{timeout}s", "--output-format", "stream-json"]


def _codex_exe() -> Path | None:
    found = shutil.which("codex")
    if found:
        return Path(found)
    for base in (os.environ.get("LOCALAPPDATA"), str(Path.home() / "AppData" / "Local")):
        if base and (Path(base) / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe").is_file():
            return Path(base) / "Programs" / "OpenAI" / "Codex" / "bin" / "codex.exe"
    return None


def _codex(model: str, prompt: str, cwd: Path, edit: bool, timeout: int, tmp: Path) -> list[str]:
    exe = _codex_exe()
    if exe is None:
        raise WorkerUnavailable("cannot find codex (install Codex and sign in)")
    if len(prompt) > 28000:
        raise ValueError("task too long to pass as an argument: put the context in project files and refer to them")
    argv = [str(exe), "exec", "-s", "workspace-write" if edit else "read-only", "-C", str(cwd), "--skip-git-repo-check",
            "--ephemeral", "--color", "never"]
    if model and model != "default":
        argv += ["-m", model]
    return argv + [prompt]


WORKERS = {"opencode": _opencode, "agy": _agy, "codex": _codex}


def _agy_event(line: str) -> tuple[str | None, str | None, str | None]:
    """Translates one line of `agy --output-format stream-json` into (readable line for the log, final answer, partial text).
    A line that is not JSON (e.g. an error from the CLI itself) is left as it is in the log."""
    try:
        ev = json.loads(line)
    except ValueError:
        return line.rstrip("\n"), None, None
    if not isinstance(ev, dict):
        return line.rstrip("\n"), None, None
    if ev.get("event") == "result":
        r = ev.get("result") or {}
        summary_line = f"✔ {r.get('status')} ({r.get('duration_seconds')}s)"
        return summary_line, str(r.get("response") or "") if r.get("status") == "SUCCESS" else json.dumps(r, ensure_ascii=False), None
    if ev.get("event") == "step_update":
        s = ev.get("step_update") or {}
        if s.get("step_type") == "tool" and s.get("state") == "ACTIVE":
            params = (s.get("tool_info") or {}).get("parameters") or {}
            detail = next((str(v) for v in params.values() if isinstance(v, str) and v), "")
            return f"🔧 {s.get('tool_name')} {detail}"[:220], None, None
        if s.get("step_type") == "agent_response" and s.get("text_delta"):
            delta = s["text_delta"]
            return "💬 " + delta.strip().replace("\n", " ")[:200], None, delta
    return None, None, None


async def _exec(argv: list[str], cwd: Path, timeout: int, log_path: Path | None = None) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(*argv, cwd=str(cwd), stdin=asyncio.subprocess.DEVNULL,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                                                env={**os.environ, **EXTRA_ENV, "PWD": str(cwd)})
    buffer = []
    partial = []  # the agent's text, in case the CLI ends without a final event
    final = []
    stream = "stream-json" in argv
    log_file = None
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "a", encoding="utf-8", buffering=1, errors="replace")

    try:
        async def _read_stream():
            while True:
                line_bytes = await proc.stdout.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", "replace")
                if stream:
                    visible, answer, delta = _agy_event(line)
                    if answer is not None:
                        final.append(answer)
                    if delta:
                        partial.append(delta)
                    if visible is None:
                        continue
                    if answer is None and delta is None and not line.lstrip().startswith("{"):
                        buffer.append(line)  # loose text from the CLI (errors, quota): kept so it can be detected
                    line = visible + "\n"
                else:
                    buffer.append(line)
                if log_file:
                    log_file.write(line)
                    log_file.flush()

        await asyncio.wait_for(_read_stream(), timeout)
        await proc.wait()
    except (asyncio.TimeoutError, asyncio.CancelledError):
        _kill(proc.pid)
        raise
    finally:
        if log_file:
            log_file.close()

    if stream:
        buffer.append("".join(final) or "".join(partial))
    return proc.returncode or 0, "".join(buffer)


def _kill(pid: int) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True, timeout=15)
        else:
            os.kill(pid, 9)
    except Exception:
        pass


# ---------------------------------------------------------------- workspaces and merging
def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=True).stdout.strip()


def make_branch(n: int, base: Path) -> tuple[Path, str]:
    top = Path(_git("rev-parse", "--show-toplevel", cwd=base))
    branch, folder = f"wf/{RUN_ID}-{n}", top.parent / f"{top.name}-wf-{RUN_ID}-{n}"
    if DRY:
        return folder, branch
    files = [f for f in subprocess.run(["git", "ls-files", "-z"], cwd=str(top), capture_output=True, check=True).stdout.decode("utf-8").split("\0") if f]
    for f in files:
        src, dst = top / f, folder / f
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for cmd in (["init", "-q"], ["config", "user.email", "wf@local"], ["config", "user.name", "wf"], ["config", "core.autocrlf", "false"],
                ["config", "core.safecrlf", "false"], ["checkout", "-q", "-b", branch], ["add", "-A"], ["commit", "-qm", "starting snapshot (wf)"]):
        _git(*cmd, cwd=folder)
    WORKTREES.append((branch, str(folder), str(top)))
    return folder, branch


def _repo_top(path: Path) -> Path | None:
    try:
        return Path(_git("rev-parse", "--show-toplevel", cwd=path))
    except (subprocess.CalledProcessError, OSError):
        return None


def main_state(top: Path) -> str:
    return _git("rev-parse", "HEAD", cwd=top) + "\n" + _git("status", "--porcelain", "--untracked-files=all", cwd=top)


def _rmtree(folder: str) -> None:
    import stat

    def fix(func, path, _exc):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    shutil.rmtree(folder, onexc=fix) if sys.version_info >= (3, 12) else shutil.rmtree(folder, onerror=fix)


def cleanup_worktrees(delete_branches: bool = False) -> None:
    for _branch, folder, _top in list(WORKTREES):
        try:
            _rmtree(folder)
        except Exception as ex:
            log("could not clean up", folder, "-", type(ex).__name__, str(ex)[:100])
    WORKTREES.clear()


def check_collisions() -> dict[str, list[str]]:
    """Detects whether two or more isolated copies modified the same files."""
    mods: dict[str, list[str]] = {}
    for branch, folder, _top in WORKTREES:
        p = subprocess.run(["git", "diff", "--name-only", "HEAD"], cwd=folder, capture_output=True, text=True)
        for line in p.stdout.splitlines():
            f = line.strip()
            if f:
                mods.setdefault(f, []).append(branch)
    return {f: b for f, b in mods.items() if len(b) > 1}


def auto_integrate(target_repo: Path | None = None) -> list[str]:
    """Automatically integrates non-colliding copies using a 3-way merge (`git apply --3way`)."""
    colls = check_collisions()
    if colls:
        raise RuntimeError(f"File collision detected between tasks: {colls}. Resolve it manually.")
    integrated = []
    for branch, folder, top in list(WORKTREES):
        target = target_repo or Path(top)
        diff_p = subprocess.run(["git", "diff", "HEAD"], cwd=folder, capture_output=True, text=True)
        diff_text = diff_p.stdout
        if not diff_text.strip():
            continue
        apply_p = subprocess.run(["git", "apply", "--3way", "--whitespace=fix"], input=diff_text, text=True, cwd=str(target), capture_output=True)
        if apply_p.returncode != 0:
            raise RuntimeError(f"Error applying the changes from {branch}: {apply_p.stderr.strip() or apply_p.stdout.strip()}")
        integrated.append(branch)
    return integrated


# ---------------------------------------------------------------- agents
class Agent:
    def __init__(self, prompt=None, schema=None, role=None, tier="standard", worker=None, workspace="inherit", edit=False,
                 timeout=1800, model=None, retries=1, verify_cmd: str | None = None, max_fixes: int = 2):
        global _counter
        _counter += 1
        self.n, self.prompt, self.schema, self.role = _counter, prompt, schema, role or (prompt or "agent").strip().splitlines()[0][:50]
        self.tier, self.model, self.workspace, self.edit, self.timeout, self.retries = tier, model, workspace, edit, timeout, retries
        self.verify_cmd = verify_cmd
        self.max_fixes = max_fixes
        self.workers = [worker] if isinstance(worker, str) else list(worker or DEFAULT_WORKERS)
        if edit and workspace != "branch":
            raise ValueError("an agent that edits must use workspace='branch' (the main tree is never edited)")
        if workspace not in ("inherit", "branch"):
            raise ValueError("workspace: 'inherit' or 'branch'")
        self.history: list[tuple[str, str]] = []
        self._done, self._value = False, None
        self._cwd: Path | None = None

    def __await__(self):
        return self._once().__await__()

    async def _once(self):
        if not self._done:
            if self.prompt is None:
                raise ValueError("agent() without a prompt: call it as a(prompt, schema)")
            self._value, self._done = await self._turn(self.prompt, self.schema), True
        return self._value

    def __call__(self, prompt: str, schema=None):
        return self._turn(prompt, schema if schema is not None else self.schema, standing=self.prompt)

    async def _turn(self, prompt: str, schema, standing: str | None = None):
        schema = schema if schema is not None else {"type": "string"}
        text = (f"{standing}\n\n" if standing else "") + "".join(f"[Previous turn]\n{q}\n[Your answer]\n{a}\n\n" for q, a in self.history) + prompt
        global _sem
        _sem = _sem or asyncio.Semaphore(MAX_PARALLEL)
        async with _sem:
            value = await self._dispatch(wrap(text, schema), schema)
        if standing is not None or self.history:
            self.history.append((prompt, value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)))
        return value

    async def _dispatch(self, prompt: str, schema):
        errors, last = [], None
        for worker in [w for w in self.workers if w not in DEAD]:
            model = self.model or TIERS.get(worker, {}).get(self.tier)
            if not model:
                continue
            try:
                return await self._run(worker, model, prompt, schema)
            except WorkerUnavailable as ex:
                DEAD.add(worker)
                log(f"{worker} unavailable ({ex}); moving on to the next worker")
                errors.append(f"{worker}: {ex}")
            except WorkerError as ex:
                last = ex
                log(f"{worker}/{model} did not give a valid result ({ex}); moving on to the next worker")
        if last:
            raise last
        raise WorkerUnavailable("no worker available: " + "; ".join(errors or ["empty list"]))

    async def _run(self, worker: str, model: str, prompt: str, schema):
        if self._cwd is None:
            self._top = _repo_top(Path.cwd())
            self._cwd, branch = (make_branch(self.n, Path.cwd()) if self.workspace == "branch" else (Path.cwd(), ""))
            self.branch = branch
            if branch:
                log(f"agent {self.n} '{self.role}': branch {branch} in {self._cwd}")
        extra = ""
        guard = None if DRY else self._top
        before = main_state(guard) if guard else None
        for attempt in range(self.retries + 1):
            tmp = Path(tempfile.mkdtemp(prefix="wf-"))
            argv = WORKERS[worker](model, prompt + extra, self._cwd, self.edit, self.timeout, tmp)
            log(f"agent {self.n} '{self.role}' -> {worker}/{model}" + (f" (attempt {attempt + 1})" if attempt else ""))
            if DRY:
                log("  [dry] " + " ".join(f'"{a}"' if " " in a else a for a in argv)[:600])
                return {} if isinstance(schema, dict) and schema.get("type") == "object" else [] if schema.get("type") == "array" else ""
            t0 = time.time()
            update_status(self.n, role=self.role, worker=worker, model=model, status="running", started_at=t0)
            log_file = RUN_DIR / f"agent-{self.n}.log"
            try:
                code, out = await _exec(argv, self._cwd, self.timeout, log_path=log_file)
            except asyncio.TimeoutError:
                STATS.append({"n": self.n, "role": self.role, "worker": worker, "model": model, "cwd": str(self._cwd),
                              "secs": round(time.time() - t0, 1), "exit": -1, "tail": "", "ok": False, "why": "timed out",
                              "in_tok": 0, "out_tok": 0, "cost": 0.0})
                if attempt == self.retries:
                    raise WorkerError(f"agent {self.n} '{self.role}': timed out ({self.timeout}s)") from None
                continue
            clean = ANSI.sub("", out)
            after = main_state(guard) if guard else None
            if guard and after != before:
                changes = sorted(set(after.splitlines()) ^ set(before.splitlines()))[:8]
                what = "EDITED" if not self.edit else "TOUCHED"
                raise RuntimeError(f"agent {self.n} '{self.role}' ({worker}) {what} THE MAIN TREE ({guard})"
                                   + (" while being read-only" if not self.edit else " instead of its copy") + f". Changes: {changes}. "
                                   "Check `git status` there and discard whatever you do not want; do not use this worker for this.")
            in_tok, out_tok = estimate_tokens(prompt + extra, clean)
            cost_val = estimate_cost(model, in_tok, out_tok)
            rec = {"n": self.n, "role": self.role, "worker": worker, "model": model, "cwd": str(self._cwd), "secs": round(time.time() - t0, 1),
                   "exit": code, "tail": clean[-1500:], "in_tok": in_tok, "out_tok": out_tok, "cost": cost_val}
            try:
                value = extract(clean, schema)

                # Self-healing loop (verify_cmd)
                if self.edit and self.verify_cmd and not DRY:
                    for fix_idx in range(self.max_fixes):
                        log(f"agent {self.n} '{self.role}': running verification ({self.verify_cmd})...")
                        v_proc = subprocess.run(self.verify_cmd, shell=True, cwd=str(self._cwd), capture_output=True, text=True, timeout=300)
                        if v_proc.returncode == 0:
                            log(f"agent {self.n} '{self.role}': verification passed ✓ ({self.verify_cmd})")
                            break
                        trace = ((v_proc.stderr or "") + "\n" + (v_proc.stdout or "")).strip()[-1800:]
                        log(f"agent {self.n} '{self.role}': verification failed ({v_proc.returncode}). Self-healing {fix_idx + 1}/{self.max_fixes}...")
                        fix_prompt = (
                            f"The code you changed produced an error when running '{self.verify_cmd}' (code {v_proc.returncode}):\n"
                            f"```\n{trace}\n```\n"
                            f"Fix the necessary files in your copy so that the verification passes."
                        )
                        extra += f"\n\n[Correction turn - Test error]:\n{trace}\n"
                        argv_fix = WORKERS[worker](model, wrap(prompt + extra, schema), self._cwd, True, self.timeout, tmp)
                        code_fix, out_fix = await _exec(argv_fix, self._cwd, self.timeout, log_path=log_file)
                        clean_fix = ANSI.sub("", out_fix)
                        try:
                            value = extract(clean_fix, schema)
                        except WorkerError:
                            pass

                update_status(self.n, status="ok", secs=rec["secs"], exit=code, in_tok=in_tok, out_tok=out_tok, cost=cost_val)
                STATS.append({**rec, "ok": True})
                self._save(rec, value)
                return value
            except WorkerError as ex:
                if UNAVAILABLE.search(clean[-2000:]):
                    STATS.append({**rec, "ok": False, "why": "unavailable"})
                    raise WorkerUnavailable(clean.strip().splitlines()[-1][:160] if clean.strip() else "no output") from None
                STATS.append({**rec, "ok": False, "why": str(ex)})
                self._save(rec, None)
                extra = f"\n\nYour previous answer did not follow the format ({ex}). Answer again with the correct block."
                if attempt == self.retries:
                    raise WorkerError(f"agent {self.n} '{self.role}': {ex}") from None
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

    def _save(self, rec: dict, value) -> None:
        try:
            RUN_DIR.mkdir(parents=True, exist_ok=True)
            (RUN_DIR / f"agent-{self.n}.json").write_text(json.dumps({**rec, "result": value}, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass


def agent(prompt=None, schema=None, role=None, tier="standard", worker=None, workspace="inherit", edit=False, timeout=1800,
          model=None, retries=1, verify_cmd: str | None = None, max_fixes: int = 2) -> Agent:
    """Defines an agent (it does not run until you `await` it). `worker`: "opencode" (free), "agy" (Gemini/Claude) or "codex".
    `verify_cmd`: optional test command used for self-healing when it fails."""
    return Agent(prompt, schema, role, tier, worker, workspace, edit, timeout, model, retries, verify_cmd, max_fixes)


async def _aw(x):
    return await x


async def parallel(items, fn):
    """Calls `fn(item)` for each element and waits for everything at once (at most WF_MAX_PARALLEL agents at a time). If one fails, cancels the rest."""
    items = list(items)
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(_aw(fn(i))) for i in items]
    except BaseExceptionGroup as eg:
        raise eg.exceptions[0] from None
    return [t.result() for t in tasks]


async def pipeline(items, fn):
    """Like `parallel` but one by one and in order."""
    return [await _aw(fn(i)) for i in list(items)]


# ---------------------------------------------------------------- dependency graphs (DAG)
class Task:
    def __init__(self, id: str, prompt: str, schema=None, depends_on: list[Task] | None = None, **agent_kwargs):
        self.id = str(id)
        self.prompt = prompt
        self.schema = schema
        self.depends_on = list(depends_on or [])
        self.agent_kwargs = agent_kwargs
        self.result = None


def task(id: str, prompt: str, schema=None, depends_on: list[Task] | None = None, **kwargs) -> Task:
    """Defines a task with optional dependencies, to be used with `await dag([...])`."""
    return Task(id, prompt, schema, depends_on, **kwargs)


async def dag(tasks: list[Task]) -> dict[str, any]:
    """Runs a graph of tasks, resolving data dependencies and parallelizing the tasks that are ready."""
    tasks_map = {t.id: t for t in tasks}
    results: dict[str, any] = {}
    pending = set(tasks_map.keys())
    running: dict[str, asyncio.Task] = {}

    def has_cycle(tid: str, visited: set, stack: set) -> bool:
        visited.add(tid)
        stack.add(tid)
        for dep in tasks_map.get(tid, task(tid, "")).depends_on:
            if dep.id not in visited and has_cycle(dep.id, visited, stack):
                return True
            if dep.id in stack:
                return True
        stack.remove(tid)
        return False

    visited = set()
    for tid in tasks_map:
        if tid not in visited and has_cycle(tid, visited, set()):
            raise ValueError(f"Cycle detected in the DAG dependencies (task: {tid})")

    while pending or running:
        ready = [tid for tid in list(pending) if all(dep.id in results for dep in tasks_map[tid].depends_on)]
        for tid in ready:
            pending.remove(tid)
            t_obj = tasks_map[tid]
            dep_context = ""
            if t_obj.depends_on:
                parts = []
                for dep in t_obj.depends_on:
                    res_str = json.dumps(results[dep.id], ensure_ascii=False) if not isinstance(results[dep.id], str) else results[dep.id]
                    parts.append(f"[Result of {dep.id}]:\n{res_str}")
                dep_context = "\n\n".join(parts) + "\n\n"

            full_prompt = dep_context + t_obj.prompt
            ag = agent(full_prompt, t_obj.schema, role=t_obj.id, **t_obj.agent_kwargs)
            running[tid] = asyncio.create_task(_aw(ag))

        if not running:
            if pending:
                raise RuntimeError(f"Tasks blocked with unresolved dependencies: {pending}")
            break

        done, _ = await asyncio.wait(running.values(), return_when=asyncio.FIRST_COMPLETED)
        for tid, t_fut in list(running.items()):
            if t_fut in done:
                results[tid] = t_fut.result()
                tasks_map[tid].result = results[tid]
                del running[tid]

    return results


# ---------------------------------------------------------------- summary and cli
def summary() -> None:
    ok = sum(1 for s in STATS if s["ok"])
    total_time = round(time.time() - _start_time, 1)
    worker_time = round(sum(s.get("secs", 0) for s in STATS), 1)
    speedup = round(worker_time / max(0.1, total_time), 1) if STATS else 1.0
    total_in = sum(s.get("in_tok", 0) for s in STATS)
    total_out = sum(s.get("out_tok", 0) for s in STATS)
    total_cost = round(sum(s.get("cost", 0.0) for s in STATS), 4)

    log(f"summary: {ok}/{len(STATS)} successful runs; records in {RUN_DIR}")
    if STATS:
        log(f"  telemetry: total time {total_time}s | agent time {worker_time}s ({speedup}x speed-up) | tokens: {total_in:,} in / {total_out:,} out | est. cost: ${total_cost} USD")
    for s in STATS:
        log(f"  agent {s['n']} '{s['role']}' {s['worker']}/{s['model']} {s['secs']}s {'OK' if s['ok'] else 'FAILED: ' + s.get('why', '')}")
    for branch, folder, top in WORKTREES:
        log(f"  COPY {branch} in {folder} (auto merge: auto_integrate(); manual: git -C {folder} diff HEAD | git -C {top} apply --3way)")

    try:
        (RUN_DIR / "telemetry.json").write_text(json.dumps({
            "run_id": RUN_ID, "ok": ok, "total": len(STATS), "total_secs": total_time,
            "worker_secs": worker_time, "speedup": speedup, "in_tokens": total_in,
            "out_tokens": total_out, "cost_usd": total_cost, "stats": STATS
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


PRIMS = {
    "log": log, "phase": phase, "agent": agent, "parallel": parallel, "pipeline": pipeline,
    "task": task, "dag": dag, "check_collisions": check_collisions, "auto_integrate": auto_integrate,
    "cleanup_worktrees": cleanup_worktrees, "TIERS": TIERS
}


def run_script(path: str, args: dict) -> int:
    src = Path(path).read_text(encoding="utf-8")
    code = compile(src, path, "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    g = {**PRIMS, "args": args, "WORKSPACES": (os.getcwd(),), "__name__": "__wf__"}

    async def go() -> None:
        r = eval(code, g)
        if asyncio.iscoroutine(r):
            await r

    try:
        asyncio.run(go())
        return 0
    except BaseException as ex:
        log(f"THE WORKFLOW FAILED: {type(ex).__name__}: {ex}")
        return 1
    finally:
        summary()


def main(argv: list[str]) -> int:
    global DRY
    if argv and (argv[0] in ("--monitor", "monitor") or "--monitor" in argv):
        try:
            from . import monitor
        except ImportError:
            import monitor
        monitor.run_monitor()
        return 0
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    script, args = argv[0], {}
    if "--dry" in argv:
        DRY = True
    if "--args" in argv:
        args = json.loads(argv[argv.index("--args") + 1])
    return run_script(script, args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
