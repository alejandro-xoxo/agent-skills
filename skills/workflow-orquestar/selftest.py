# SPDX-License-Identifier: LicenseRef-Proprietary — Copyright (c) 2026 alejandro-xoxo. All rights reserved.
# Copyright (c) 2026 alejandro-xoxo
"""Pruebas de wf.py con un trabajador falso (no gasta cuota ni llama a ningún modelo). Uso: python selftest.py"""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wf  # noqa: E402

FAKE = r"""
import json, os, sys
prompt = sys.argv[1]
mode = os.environ.get("FAKE_MODE", "ok")
cnt = os.environ.get("FAKE_COUNTER")
n = 0
if cnt:
    n = int(open(cnt).read() or 0) + 1
    open(cnt, "w").write(str(n))
if mode == "quota":
    print("error: Individual quota reached. Resets in 91h"); sys.exit(0)
if mode == "bad_first" and n == 1:
    print("no sé el formato"); sys.exit(0)
if mode == "fail":
    print("<<<WF_RESULT\n{nada\nWF_RESULT>>>"); sys.exit(0)
if "[Turno anterior]" in prompt:
    print('<<<WF_RESULT\n{"history": true}\nWF_RESULT>>>'); sys.exit(0)
if "texto libre" in prompt:
    print("<<<WF_RESULT\nhola texto\nWF_RESULT>>>"); sys.exit(0)
print("eco del encargo: <<<WF_RESULT\n<resultado aquí>\nWF_RESULT>>>")           # el CLI repite el ejemplo del encargo
print("<<<WF_RESULT\n" + os.environ.get("FAKE_REPLY", '{"ok": true}') + "\nWF_RESULT>>>")
"""


def fake_worker(model, prompt, cwd, edit, timeout, tmp):
    return [sys.executable, "-c", FAKE, prompt]


def unavailable_worker(model, prompt, cwd, edit, timeout, tmp):
    raise wf.WorkerUnavailable("sin sesión")


wf.WORKERS["fake"] = fake_worker
wf.WORKERS["muerto"] = unavailable_worker
wf.WORKERS["mudo"] = lambda m, p, c, e, t, tmp: [sys.executable, "-c", "print('nada util')"]
wf.WORKERS["lento"] = lambda m, p, c, e, t, tmp: [sys.executable, "-c", "import time; time.sleep(30)"]
wf.TIERS["mudo"] = {"standard": "m"}
wf.TIERS["lento"] = {"standard": "l"}
wf.TIERS["fake"] = {"standard": "f", "pro": "f", "max": "f", "fast": "f"}
wf.TIERS["muerto"] = {"standard": "m"}
wf.RUN_DIR = Path(tempfile.mkdtemp(prefix="wf-selftest-"))
OBJ = {"type": "object", "required": ["ok"], "properties": {"ok": {"type": "boolean"}}}
passed = []


def check(name):
    def deco(fn):
        try:
            r = fn()
            if asyncio.iscoroutine(r):
                asyncio.run(r)
            passed.append(name)
            print("OK  ", name)
        except Exception as ex:  # noqa: BLE001
            print("FALLA", name, "->", type(ex).__name__, ex)
            raise
        return fn
    return deco


@check("validate: tipos, required, enum e items")
def _():
    wf.validate({"a": [1, 2]}, {"type": "object", "required": ["a"], "properties": {"a": {"type": "array", "items": {"type": "integer"}}}})
    for bad, sch in [({"a": ["x"]}, {"type": "object", "properties": {"a": {"type": "array", "items": {"type": "integer"}}}}),
                     ({}, {"type": "object", "required": ["a"]}), ("z", {"enum": ["a"]}), (True, {"type": "integer"})]:
        try:
            wf.validate(bad, sch)
        except ValueError:
            continue
        raise AssertionError(f"debía fallar: {bad} {sch}")


@check("extract: ignora el ejemplo repetido, toma el último válido y valida el esquema")
def _():
    txt = "x <<<WF_RESULT\n<resultado aquí>\nWF_RESULT>>> y <<<WF_RESULT\n{\"ok\": false}\nWF_RESULT>>> z <<<WF_RESULT\n{\"ok\": true}\nWF_RESULT>>>"
    assert wf.extract(txt, OBJ) == {"ok": True}
    assert wf.extract("\x1b[1m<<<WF_RESULT\n{\"ok\": 1}\nWF_RESULT>>>\x1b[0m <<<WF_RESULT\n{\"ok\": true}\nWF_RESULT>>>", OBJ) == {"ok": True}
    assert wf.extract("<<<WF_RESULT\nhola\nWF_RESULT>>>", {"type": "string"}) == "hola"
    for malo in ("sin bloque", "<<<WF_RESULT\n{\"ok\": 3}\nWF_RESULT>>>"):
        try:
            wf.extract(malo, OBJ)
        except wf.WorkerError:
            continue
        raise AssertionError("debía fallar")


@check("agent: ejecuta el trabajador y devuelve el valor ya validado; await dos veces corre una")
async def _():
    a = wf.agent("Di ok", OBJ, worker="fake")
    assert await a == {"ok": True} and await a == {"ok": True}
    assert len([s for s in wf.STATS if s["n"] == a.n]) == 1


@check("example: forma del resultado esperado para cada tipo")
def _():
    assert wf.example({"type": "integer"}) == "0" and wf.example({"type": "boolean"}) == "true"
    assert wf.example({"type": "array", "items": {"type": "string"}}) == '["texto", "texto"]'
    assert wf.example({"type": "object", "properties": {"a": {"type": "string"}, "n": {"type": "integer"}}}) == '{"a": "texto", "n": 0}'
    assert "no lo envuelvas" in wf.wrap("x", {"type": "integer"}) and "texto libre" in wf.wrap("x", {"type": "string"})


@check("agent: esquema de texto")
async def _():
    assert await wf.agent("Saluda", {"type": "string"}, worker="fake") == "hola texto"


@check("parallel mantiene el orden; pipeline va en orden; el tope de agentes a la vez se respeta")
async def _():
    os.environ["FAKE_REPLY"] = '{"ok": true}'
    r = await wf.parallel(range(6), lambda i: wf.agent(f"item {i}", OBJ, worker="fake", role=f"r{i}"))
    assert r == [{"ok": True}] * 6
    assert await wf.pipeline(range(3), lambda i: wf.agent(f"p {i}", OBJ, worker="fake")) == [{"ok": True}] * 3


@check("sin cuota: el trabajador se marca muerto y se pasa al siguiente; no se reintenta el muerto")
async def _():
    wf.DEAD.clear()
    os.environ["FAKE_MODE"] = "ok"
    r = await wf.agent("hola", OBJ, worker=["muerto", "fake"])
    assert r == {"ok": True} and "muerto" in wf.DEAD
    os.environ["FAKE_MODE"] = "quota"
    wf.DEAD.clear()
    try:
        await wf.agent("hola", OBJ, worker=["fake"])
    except wf.WorkerUnavailable:
        assert "fake" in wf.DEAD
    else:
        raise AssertionError("debía quedarse sin trabajador")
    os.environ["FAKE_MODE"] = "ok"
    wf.DEAD.clear()


@check("formato malo la primera vez: reintenta una vez y lo logra; si sigue mal, falla")
async def _():
    c = Path(wf.RUN_DIR) / "contador"
    c.write_text("0")
    os.environ["FAKE_MODE"], os.environ["FAKE_COUNTER"] = "bad_first", str(c)
    assert await wf.agent("hola", OBJ, worker="fake") == {"ok": True}
    os.environ["FAKE_MODE"] = "fail"
    try:
        await wf.agent("hola", OBJ, worker="fake")
    except wf.WorkerError:
        pass
    else:
        raise AssertionError("debía fallar")
    os.environ["FAKE_MODE"] = "ok"
    os.environ.pop("FAKE_COUNTER")


@check("formato inválido o tiempo agotado: pasa al siguiente trabajador sin marcar el primero como muerto")
async def _():
    wf.DEAD.clear()
    os.environ["FAKE_MODE"] = "ok"
    assert await wf.agent("hola", OBJ, worker=["mudo", "fake"], retries=0) == {"ok": True}
    assert await wf.agent("hola", OBJ, worker=["lento", "fake"], retries=0, timeout=1) == {"ok": True}
    assert "mudo" not in wf.DEAD and "lento" not in wf.DEAD
    try:
        await wf.agent("hola", OBJ, worker=["lento"], retries=1, timeout=1)
    except wf.WorkerError as ex:
        assert "tiempo agotado" in str(ex)
    else:
        raise AssertionError("debía agotar el tiempo")


@check("parallel: si uno falla se cancela el resto y sube el primer error")
async def _():
    os.environ["FAKE_MODE"] = "fail"
    try:
        await wf.parallel(range(3), lambda i: wf.agent(f"x{i}", OBJ, worker="fake", retries=0))
    except wf.WorkerError:
        pass
    else:
        raise AssertionError("debía fallar")
    os.environ["FAKE_MODE"] = "ok"


@check("agente con contexto: el segundo turno recibe el historial")
async def _():
    a = wf.agent("Eres un revisor.", worker="fake")
    await a("primer turno", {"type": "string"})
    assert await a("segundo turno", {"type": "object", "properties": {"history": {"type": "boolean"}}}) == {"history": True}


@check("un agente que edita exige rama aislada")
def _():
    try:
        wf.agent("edita", {"type": "string"}, edit=True)
    except ValueError:
        return
    raise AssertionError("debía rechazar edit sin branch")


@check("workspace='branch': crea un worktree aislado y se limpia")
async def _():
    repo = Path(tempfile.mkdtemp(prefix="wf-repo-")) / "proyecto"
    repo.mkdir()
    run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True)  # noqa: E731
    run("init", "-q"), run("config", "user.email", "t@t"), run("config", "user.name", "t")
    (repo / "a.txt").write_text("hola")
    run("add", "."), run("commit", "-qm", "base")
    old = os.getcwd()
    os.chdir(repo)
    try:
        a = wf.agent("edita", OBJ, worker="fake", workspace="branch", edit=True)
        assert await a == {"ok": True}
        assert len(wf.WORKTREES) == 1 and (Path(wf.WORKTREES[0][1]) / "a.txt").exists()
        folder = Path(wf.WORKTREES[0][1])
        assert folder != repo and (folder / ".git").is_dir()                                    # clon independiente, no worktree
        assert subprocess.run(["git", "branch", "--show-current"], cwd=folder, capture_output=True, text=True).stdout.strip().startswith("wf/")
        assert "wf/" not in run("branch").stdout                                                # el repositorio principal no recibe la rama
        root = lambda d: subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=d, capture_output=True, text=True).stdout.strip()  # noqa: E731
        assert root(folder) and root(folder) != root(repo)                                      # otro primer commit: no se confunde con el original
        assert subprocess.run(["git", "remote"], cwd=folder, capture_output=True, text=True).stdout.strip() == ""
        wf.cleanup_worktrees(delete_branches=True)
        assert not wf.WORKTREES and not folder.exists()
    finally:
        os.chdir(old)
        shutil.rmtree(repo.parent, ignore_errors=True)


@check("el CLI recibe PWD igual a su carpeta de trabajo (el PWD heredado de la shell hacía que OpenCode editara el árbol principal)")
async def _():
    d = Path(tempfile.mkdtemp(prefix="wf-pwd-"))
    wf.WORKERS["pwd"] = lambda m, p, c, e, t, tmp: [sys.executable, "-c", "import os; print('<<<WF_RESULT'); print(os.environ['PWD']); print('WF_RESULT>>>')"]
    wf.TIERS["pwd"] = {"standard": "p"}
    old = os.getcwd()
    os.chdir(d)
    try:
        assert Path(await wf.agent("x", {"type": "string"}, worker="pwd")).resolve() == d.resolve()
    finally:
        os.chdir(old)
        shutil.rmtree(d, ignore_errors=True)


@check("guardia: un agente que edita el árbol principal en vez de su copia hace fallar el workflow")
async def _():
    repo = Path(tempfile.mkdtemp(prefix="wf-esc-")) / "proyecto"
    repo.mkdir()
    run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True)  # noqa: E731
    run("init", "-q"), run("config", "user.email", "t@t"), run("config", "user.name", "t")
    (repo / "a.txt").write_text("hola")
    run("add", "."), run("commit", "-qm", "base")
    wf.WORKERS["tramposo"] = lambda m, p, c, e, t, tmp: [sys.executable, "-c", f"open(r'{repo}/escapado.txt','w').write('x')"]
    wf.TIERS["tramposo"] = {"standard": "t"}
    old = os.getcwd()
    os.chdir(repo)
    try:
        try:
            await wf.agent("edita", OBJ, worker="tramposo", workspace="branch", edit=True)
        except RuntimeError as ex:
            assert "TOCÓ EL ÁRBOL PRINCIPAL" in str(ex)
        else:
            raise AssertionError("el guardia debía detectar la fuga")
    finally:
        os.chdir(old)
        wf.cleanup_worktrees()
        shutil.rmtree(repo.parent, ignore_errors=True)


@check("opencode y agy: los comandos se arman bien (sin ejecutarlos)")
def _():
    tmp = Path(tempfile.mkdtemp(prefix="wf-cmd-"))
    if wf._opencode_native():
        argv = wf._opencode("opencode/nemotron-3-ultra-free", "encargo <<<raro>>>", Path.cwd(), False, 60, tmp)
        assert argv[1:3] == ["run", "--standalone"] and argv[argv.index("--agent") + 1] == "plan" and "--auto" not in argv
        assert argv[-1] == "encargo <<<raro>>>"
        edit = wf._opencode("m", "x", Path.cwd(), True, 60, tmp)
        assert edit[edit.index("--agent") + 1] == "build" and "--auto" in edit
    if shutil.which("agy"):
        argv = wf._agy("gemini-3.8-flash-low", "encargo", Path.cwd(), False, 60, tmp)
        assert argv[1:3] == ["-p", "encargo"] and "plan" in argv and argv[argv.index("--model") + 1] == "gemini-3.8-flash-low"
        assert "accept-edits" in wf._agy("m", "x", Path.cwd(), True, 60, tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@check("script con await de nivel superior y args, vía run_script (modo --dry)")
def _():
    s = Path(wf.RUN_DIR) / "s.py"
    s.write_text('phase("uno")\nr = await parallel(args["items"], lambda i: agent(f"x {i}", {"type": "object"}, worker="fake"))\nlog("n", len(r))\n', encoding="utf-8")
    wf.DRY = True
    try:
        assert wf.run_script(str(s), {"items": [1, 2]}) == 0
    finally:
        wf.DRY = False


@check("script que falla devuelve 1 y lo dice")
def _():
    s = Path(wf.RUN_DIR) / "f.py"
    s.write_text('raise RuntimeError("boom")\n', encoding="utf-8")
    assert wf.run_script(str(s), {}) == 1


@check("guardia: un agente de SOLO LECTURA que modifica el repositorio hace fallar el workflow")
async def _():
    repo = Path(tempfile.mkdtemp(prefix="wf-ro-")) / "proyecto"
    repo.mkdir()
    run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True)  # noqa: E731
    run("init", "-q"), run("config", "user.email", "t@t"), run("config", "user.name", "t")
    (repo / "a.txt").write_text("hola")
    run("add", "."), run("commit", "-qm", "base")
    wf.WORKERS["curioso"] = lambda m, p, c, e, t, tmp: [sys.executable, "-c", "open('a.txt','w').write('cambiado por un agente de lectura')"]
    wf.TIERS["curioso"] = {"standard": "c"}
    old = os.getcwd()
    os.chdir(repo)
    try:
        try:
            await wf.agent("audita", OBJ, worker="curioso")
        except RuntimeError as ex:
            assert "SOLO LECTURA".lower() in str(ex).lower() and "a.txt" in str(ex), str(ex)
        else:
            raise AssertionError("el guardia debía detectar la escritura")
        os.environ["FAKE_MODE"] = "ok"
        assert await wf.agent("audita", OBJ, worker="fake") == {"ok": True}                    # un agente que no escribe pasa sin problema
        assert (repo / "a.txt").read_text() == "cambiado por un agente de lectura"
    finally:
        os.chdir(old)
        shutil.rmtree(repo.parent, ignore_errors=True)


@check("orquestador: el CLI elegido va al FINAL del orden de trabajadores; sin elección no cambia nada")
def _():
    saved = wf.HERE
    d = Path(tempfile.mkdtemp(prefix="wf-orq-"))
    try:
        wf.HERE = d
        assert wf.orchestrator() == "claude" and wf.default_workers() == ("opencode", "agy")
        for cli, esperado in [("agy", ("opencode", "agy")), ("opencode", ("agy", "opencode")),
                              ("codex", ("opencode", "agy"))]:
            (d / "orquestador.json").write_text(json.dumps({"orquestador": cli}), encoding="utf-8")
            assert wf.orchestrator() == cli and wf.default_workers() == esperado, (cli, wf.default_workers())
        (d / "orquestador.json").write_text("basura", encoding="utf-8")
        assert wf.orchestrator() == "claude"                                                   # archivo roto: vuelve al predeterminado
    finally:
        wf.HERE = saved
        shutil.rmtree(d, ignore_errors=True)


@check("codex: el comando usa exec, el sandbox según edit, la carpeta y el modelo solo si no es «default»")
def _():
    real = wf._codex_exe
    wf._codex_exe = lambda: Path("C:/falso/codex.exe")
    try:
        ro = wf._codex("default", "encargo <<<raro>>>", Path("C:/proy"), False, 60, Path("."))
        assert ro[1:3] == ["exec", "-s"] and ro[3] == "read-only" and "-m" not in ro and ro[-1] == "encargo <<<raro>>>"
        assert ro[ro.index("-C") + 1] == str(Path("C:/proy")) and "--ephemeral" in ro
        ed = wf._codex("gpt-x", "x", Path("C:/proy"), True, 60, Path("."))
        assert ed[3] == "workspace-write" and ed[ed.index("-m") + 1] == "gpt-x"
        assert "codex" not in wf.default_workers()                                              # de pago: nunca en el orden por defecto
    finally:
        wf._codex_exe = real
    wf._codex_exe = lambda: None
    try:
        wf._codex("default", "x", Path("."), False, 60, Path("."))
    except wf.WorkerUnavailable:
        pass
    else:
        raise AssertionError("sin codex debía quedar como no disponible")
    finally:
        wf._codex_exe = real


@check("estilo ultracave: va en todo encargo por defecto y se apaga con WF_CAVEMAN=0")
def _():
    antes = wf.CAVEMAN
    try:
        wf.CAVEMAN = True
        p = wf.wrap("Revisa esto", {"type": "string"})
        assert "ultracave" in p and "Nunca quites una negación" in p and p.index("ultracave") < p.index("FORMATO DE LA RESPUESTA")
        assert "<<<WF_RESULT" in p                                                              # el formato del resultado sigue intacto
        wf.CAVEMAN = False
        assert "ultracave" not in wf.wrap("Revisa esto", {"type": "string"})
    finally:
        wf.CAVEMAN = antes


@check("extract tolera variantes de las marcas (<< o espacios)")
def _():
    assert wf.extract('<<WF_RESULT\n{"ok": true}\nWF_RESULT>>', OBJ) == {"ok": True}
    assert wf.extract('<<< WF_RESULT {"ok": true} WF_RESULT >>>', OBJ) == {"ok": True}


shutil.rmtree(wf.RUN_DIR, ignore_errors=True)
print(f"\n{len(passed)} pruebas correctas")


@check("dag y task: resolución de dependencias y detección de ciclos")
async def _():
    os.environ["FAKE_MODE"] = "ok"
    t1 = wf.task("t1", "primer paso", {"type": "object"}, worker="fake")
    t2 = wf.task("t2", "segundo paso", {"type": "object"}, depends_on=[t1], worker="fake")
    res = await wf.dag([t1, t2])
    assert "t1" in res and "t2" in res
    assert res["t1"] == {"ok": True}
    
    # Ciclo
    ta = wf.task("ta", "a")
    tb = wf.task("tb", "b", depends_on=[ta])
    ta.depends_on = [tb]
    try:
        await wf.dag([ta, tb])
    except ValueError as ex:
        assert "ciclo" in str(ex).lower()
    else:
        raise AssertionError("debía detectar el ciclo")


@check("telemetría: cálculo de tokens y estimación de coste")
def _():
    tin, tout = wf.estimate_tokens("hola " * 100, "respuesta " * 50)
    assert tin > 50 and tout > 20
    cost = wf.estimate_cost("gemini-3.8-flash-high", 100000, 50000)
    assert cost > 0.0


@check("colisiones y auto_integrate: detecta colisiones de worktree")
def _():
    colls = wf.check_collisions()
    assert isinstance(colls, dict)
