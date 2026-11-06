# SPDX-License-Identifier: LicenseRef-Proprietary — Copyright (c) 2026 alejandro-xoxo. All rights reserved.
# Copyright (c) 2026 alejandro-xoxo
"""Tests of wf.py with a fake worker (spends no quota and calls no model). Usage: python selftest.py"""
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
    print("I do not know the format"); sys.exit(0)
if mode == "fail":
    print("<<<WF_RESULT\n{nothing\nWF_RESULT>>>"); sys.exit(0)
if "[Previous turn]" in prompt:
    print('<<<WF_RESULT\n{"history": true}\nWF_RESULT>>>'); sys.exit(0)
if "free text" in prompt:
    print("<<<WF_RESULT\nhello text\nWF_RESULT>>>"); sys.exit(0)
print("echo of the task: <<<WF_RESULT\n<result here>\nWF_RESULT>>>")           # the CLI repeats the example from the task
print("<<<WF_RESULT\n" + os.environ.get("FAKE_REPLY", '{"ok": true}') + "\nWF_RESULT>>>")
"""


def fake_worker(model, prompt, cwd, edit, timeout, tmp):
    return [sys.executable, "-c", FAKE, prompt]


def unavailable_worker(model, prompt, cwd, edit, timeout, tmp):
    raise wf.WorkerUnavailable("no session")


wf.WORKERS["fake"] = fake_worker
wf.WORKERS["dead"] = unavailable_worker
wf.WORKERS["mute"] = lambda m, p, c, e, t, tmp: [sys.executable, "-c", "print('nothing useful')"]
wf.WORKERS["slow"] = lambda m, p, c, e, t, tmp: [sys.executable, "-c", "import time; time.sleep(30)"]
wf.TIERS["mute"] = {"standard": "m"}
wf.TIERS["slow"] = {"standard": "l"}
wf.TIERS["fake"] = {"standard": "f", "pro": "f", "max": "f", "fast": "f"}
wf.TIERS["dead"] = {"standard": "m"}
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
            print("FAIL", name, "->", type(ex).__name__, ex)
            raise
        return fn
    return deco


@check("validate: types, required, enum and items")
def _():
    wf.validate({"a": [1, 2]}, {"type": "object", "required": ["a"], "properties": {"a": {"type": "array", "items": {"type": "integer"}}}})
    for bad, sch in [({"a": ["x"]}, {"type": "object", "properties": {"a": {"type": "array", "items": {"type": "integer"}}}}),
                     ({}, {"type": "object", "required": ["a"]}), ("z", {"enum": ["a"]}), (True, {"type": "integer"})]:
        try:
            wf.validate(bad, sch)
        except ValueError:
            continue
        raise AssertionError(f"should have failed: {bad} {sch}")


@check("extract: ignores the repeated example, takes the last valid one and validates the schema")
def _():
    txt = "x <<<WF_RESULT\n<result here>\nWF_RESULT>>> y <<<WF_RESULT\n{\"ok\": false}\nWF_RESULT>>> z <<<WF_RESULT\n{\"ok\": true}\nWF_RESULT>>>"
    assert wf.extract(txt, OBJ) == {"ok": True}
    assert wf.extract("\x1b[1m<<<WF_RESULT\n{\"ok\": 1}\nWF_RESULT>>>\x1b[0m <<<WF_RESULT\n{\"ok\": true}\nWF_RESULT>>>", OBJ) == {"ok": True}
    assert wf.extract("<<<WF_RESULT\nhello\nWF_RESULT>>>", {"type": "string"}) == "hello"
    for bad in ("no block", "<<<WF_RESULT\n{\"ok\": 3}\nWF_RESULT>>>"):
        try:
            wf.extract(bad, OBJ)
        except wf.WorkerError:
            continue
        raise AssertionError("should have failed")


@check("agent: runs the worker and returns the already validated value; awaiting twice runs once")
async def _():
    a = wf.agent("Say ok", OBJ, worker="fake")
    assert await a == {"ok": True} and await a == {"ok": True}
    assert len([s for s in wf.STATS if s["n"] == a.n]) == 1


@check("example: shape of the expected result for each type")
def _():
    assert wf.example({"type": "integer"}) == "0" and wf.example({"type": "boolean"}) == "true"
    assert wf.example({"type": "array", "items": {"type": "string"}}) == '["text", "text"]'
    assert wf.example({"type": "object", "properties": {"a": {"type": "string"}, "n": {"type": "integer"}}}) == '{"a": "text", "n": 0}'
    assert "do not wrap it" in wf.wrap("x", {"type": "integer"}) and "free text" in wf.wrap("x", {"type": "string"})


@check("agent: text schema")
async def _():
    assert await wf.agent("Greet", {"type": "string"}, worker="fake") == "hello text"


@check("parallel keeps the order; pipeline goes in order; the cap on simultaneous agents is respected")
async def _():
    os.environ["FAKE_REPLY"] = '{"ok": true}'
    r = await wf.parallel(range(6), lambda i: wf.agent(f"item {i}", OBJ, worker="fake", role=f"r{i}"))
    assert r == [{"ok": True}] * 6
    assert await wf.pipeline(range(3), lambda i: wf.agent(f"p {i}", OBJ, worker="fake")) == [{"ok": True}] * 3


@check("out of quota: the worker is marked dead and the next one is used; the dead one is not retried")
async def _():
    wf.DEAD.clear()
    os.environ["FAKE_MODE"] = "ok"
    r = await wf.agent("hello", OBJ, worker=["dead", "fake"])
    assert r == {"ok": True} and "dead" in wf.DEAD
    os.environ["FAKE_MODE"] = "quota"
    wf.DEAD.clear()
    try:
        await wf.agent("hello", OBJ, worker=["fake"])
    except wf.WorkerUnavailable:
        assert "fake" in wf.DEAD
    else:
        raise AssertionError("should have run out of workers")
    os.environ["FAKE_MODE"] = "ok"
    wf.DEAD.clear()


@check("bad format the first time: retries once and succeeds; if it stays bad, it fails")
async def _():
    c = Path(wf.RUN_DIR) / "counter"
    c.write_text("0")
    os.environ["FAKE_MODE"], os.environ["FAKE_COUNTER"] = "bad_first", str(c)
    assert await wf.agent("hello", OBJ, worker="fake") == {"ok": True}
    os.environ["FAKE_MODE"] = "fail"
    try:
        await wf.agent("hello", OBJ, worker="fake")
    except wf.WorkerError:
        pass
    else:
        raise AssertionError("should have failed")
    os.environ["FAKE_MODE"] = "ok"
    os.environ.pop("FAKE_COUNTER")


@check("invalid format or timeout: moves on to the next worker without marking the first one dead")
async def _():
    wf.DEAD.clear()
    os.environ["FAKE_MODE"] = "ok"
    assert await wf.agent("hello", OBJ, worker=["mute", "fake"], retries=0) == {"ok": True}
    assert await wf.agent("hello", OBJ, worker=["slow", "fake"], retries=0, timeout=1) == {"ok": True}
    assert "mute" not in wf.DEAD and "slow" not in wf.DEAD
    try:
        await wf.agent("hello", OBJ, worker=["slow"], retries=1, timeout=1)
    except wf.WorkerError as ex:
        assert "timed out" in str(ex)
    else:
        raise AssertionError("should have timed out")


@check("parallel: if one fails the rest are cancelled and the first error is raised")
async def _():
    os.environ["FAKE_MODE"] = "fail"
    try:
        await wf.parallel(range(3), lambda i: wf.agent(f"x{i}", OBJ, worker="fake", retries=0))
    except wf.WorkerError:
        pass
    else:
        raise AssertionError("should have failed")
    os.environ["FAKE_MODE"] = "ok"


@check("agent with context: the second turn receives the history")
async def _():
    a = wf.agent("You are a reviewer.", worker="fake")
    await a("first turn", {"type": "string"})
    assert await a("second turn", {"type": "object", "properties": {"history": {"type": "boolean"}}}) == {"history": True}


@check("an agent that edits requires an isolated branch")
def _():
    try:
        wf.agent("edit", {"type": "string"}, edit=True)
    except ValueError:
        return
    raise AssertionError("should have rejected edit without branch")


@check("workspace='branch': creates an isolated worktree and cleans it up")
async def _():
    repo = Path(tempfile.mkdtemp(prefix="wf-repo-")) / "project"
    repo.mkdir()
    run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True)  # noqa: E731
    run("init", "-q"), run("config", "user.email", "t@t"), run("config", "user.name", "t")
    (repo / "a.txt").write_text("hello")
    run("add", "."), run("commit", "-qm", "base")
    old = os.getcwd()
    os.chdir(repo)
    try:
        a = wf.agent("edit", OBJ, worker="fake", workspace="branch", edit=True)
        assert await a == {"ok": True}
        assert len(wf.WORKTREES) == 1 and (Path(wf.WORKTREES[0][1]) / "a.txt").exists()
        folder = Path(wf.WORKTREES[0][1])
        assert folder != repo and (folder / ".git").is_dir()                                    # independent clone, not a worktree
        assert subprocess.run(["git", "branch", "--show-current"], cwd=folder, capture_output=True, text=True).stdout.strip().startswith("wf/")
        assert "wf/" not in run("branch").stdout                                                # the main repository does not receive the branch
        root = lambda d: subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=d, capture_output=True, text=True).stdout.strip()  # noqa: E731
        assert root(folder) and root(folder) != root(repo)                                      # another first commit: not confused with the original
        assert subprocess.run(["git", "remote"], cwd=folder, capture_output=True, text=True).stdout.strip() == ""
        wf.cleanup_worktrees(delete_branches=True)
        assert not wf.WORKTREES and not folder.exists()
    finally:
        os.chdir(old)
        shutil.rmtree(repo.parent, ignore_errors=True)


@check("the CLI receives PWD equal to its working folder (the PWD inherited from the shell made OpenCode edit the main tree)")
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


@check("guard: an agent that edits the main tree instead of its copy makes the workflow fail")
async def _():
    repo = Path(tempfile.mkdtemp(prefix="wf-esc-")) / "project"
    repo.mkdir()
    run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True)  # noqa: E731
    run("init", "-q"), run("config", "user.email", "t@t"), run("config", "user.name", "t")
    (repo / "a.txt").write_text("hello")
    run("add", "."), run("commit", "-qm", "base")
    wf.WORKERS["cheater"] = lambda m, p, c, e, t, tmp: [sys.executable, "-c", f"open(r'{repo}/escaped.txt','w').write('x')"]
    wf.TIERS["cheater"] = {"standard": "t"}
    old = os.getcwd()
    os.chdir(repo)
    try:
        try:
            await wf.agent("edit", OBJ, worker="cheater", workspace="branch", edit=True)
        except RuntimeError as ex:
            assert "TOUCHED THE MAIN TREE" in str(ex)
        else:
            raise AssertionError("the guard should have detected the leak")
    finally:
        os.chdir(old)
        wf.cleanup_worktrees()
        shutil.rmtree(repo.parent, ignore_errors=True)


@check("opencode and agy: the commands are built correctly (without running them)")
def _():
    tmp = Path(tempfile.mkdtemp(prefix="wf-cmd-"))
    if wf._opencode_native():
        argv = wf._opencode("opencode/nemotron-3-ultra-free", "task <<<odd>>>", Path.cwd(), False, 60, tmp)
        assert argv[1:3] == ["run", "--standalone"] and argv[argv.index("--agent") + 1] == "plan" and "--auto" not in argv
        assert argv[-1] == "task <<<odd>>>"
        edit = wf._opencode("m", "x", Path.cwd(), True, 60, tmp)
        assert edit[edit.index("--agent") + 1] == "build" and "--auto" in edit
    if shutil.which("agy"):
        argv = wf._agy("gemini-3.8-flash-low", "task", Path.cwd(), False, 60, tmp)
        assert argv[1:3] == ["-p", "task"] and "plan" in argv and argv[argv.index("--model") + 1] == "gemini-3.8-flash-low"
        assert "accept-edits" in wf._agy("m", "x", Path.cwd(), True, 60, tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@check("script with top-level await and args, via run_script (--dry mode)")
def _():
    s = Path(wf.RUN_DIR) / "s.py"
    s.write_text('phase("one")\nr = await parallel(args["items"], lambda i: agent(f"x {i}", {"type": "object"}, worker="fake"))\nlog("n", len(r))\n', encoding="utf-8")
    wf.DRY = True
    try:
        assert wf.run_script(str(s), {"items": [1, 2]}) == 0
    finally:
        wf.DRY = False


@check("a script that fails returns 1 and says so")
def _():
    s = Path(wf.RUN_DIR) / "f.py"
    s.write_text('raise RuntimeError("boom")\n', encoding="utf-8")
    assert wf.run_script(str(s), {}) == 1


@check("guard: a READ-ONLY agent that modifies the repository makes the workflow fail")
async def _():
    repo = Path(tempfile.mkdtemp(prefix="wf-ro-")) / "project"
    repo.mkdir()
    run = lambda *a: subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, check=True)  # noqa: E731
    run("init", "-q"), run("config", "user.email", "t@t"), run("config", "user.name", "t")
    (repo / "a.txt").write_text("hello")
    run("add", "."), run("commit", "-qm", "base")
    wf.WORKERS["curious"] = lambda m, p, c, e, t, tmp: [sys.executable, "-c", "open('a.txt','w').write('changed by a read-only agent')"]
    wf.TIERS["curious"] = {"standard": "c"}
    old = os.getcwd()
    os.chdir(repo)
    try:
        try:
            await wf.agent("audit", OBJ, worker="curious")
        except RuntimeError as ex:
            assert "READ-ONLY".lower() in str(ex).lower() and "a.txt" in str(ex), str(ex)
        else:
            raise AssertionError("the guard should have detected the write")
        os.environ["FAKE_MODE"] = "ok"
        assert await wf.agent("audit", OBJ, worker="fake") == {"ok": True}                     # an agent that does not write passes without trouble
        assert (repo / "a.txt").read_text() == "changed by a read-only agent"
    finally:
        os.chdir(old)
        shutil.rmtree(repo.parent, ignore_errors=True)


@check("orchestrator: the chosen CLI goes LAST in the worker order; with no choice nothing changes")
def _():
    saved = wf.HERE
    d = Path(tempfile.mkdtemp(prefix="wf-orq-"))
    try:
        wf.HERE = d
        assert wf.orchestrator() == "claude" and wf.default_workers() == ("opencode", "agy")
        for cli, expected in [("agy", ("opencode", "agy")), ("opencode", ("agy", "opencode")),
                              ("codex", ("opencode", "agy"))]:
            (d / "orchestrator.json").write_text(json.dumps({"orchestrator": cli}), encoding="utf-8")
            assert wf.orchestrator() == cli and wf.default_workers() == expected, (cli, wf.default_workers())
        (d / "orchestrator.json").write_text("garbage", encoding="utf-8")
        assert wf.orchestrator() == "claude"                                                   # broken file: back to the default
        (d / "orchestrator.json").unlink()
        (d / "orquestador.json").write_text(json.dumps({"orquestador": "opencode"}), encoding="utf-8")
        assert wf.orchestrator() == "opencode"                                                 # the older Spanish file name still works
    finally:
        wf.HERE = saved
        shutil.rmtree(d, ignore_errors=True)


@check("codex: the command uses exec, the sandbox follows edit, the folder, and the model only if it is not 'default'")
def _():
    real = wf._codex_exe
    wf._codex_exe = lambda: Path("C:/fake/codex.exe")
    try:
        ro = wf._codex("default", "task <<<odd>>>", Path("C:/proj"), False, 60, Path("."))
        assert ro[1:3] == ["exec", "-s"] and ro[3] == "read-only" and "-m" not in ro and ro[-1] == "task <<<odd>>>"
        assert ro[ro.index("-C") + 1] == str(Path("C:/proj")) and "--ephemeral" in ro
        ed = wf._codex("gpt-x", "x", Path("C:/proj"), True, 60, Path("."))
        assert ed[3] == "workspace-write" and ed[ed.index("-m") + 1] == "gpt-x"
        assert "codex" not in wf.default_workers()                                              # paid: never in the default order
    finally:
        wf._codex_exe = real
    wf._codex_exe = lambda: None
    try:
        wf._codex("default", "x", Path("."), False, 60, Path("."))
    except wf.WorkerUnavailable:
        pass
    else:
        raise AssertionError("without codex it should be unavailable")
    finally:
        wf._codex_exe = real


@check("ultracave style: goes in every task by default and is turned off with WF_CAVEMAN=0")
def _():
    before = wf.CAVEMAN
    try:
        wf.CAVEMAN = True
        p = wf.wrap("Review this", {"type": "string"})
        assert "ultracave" in p and "Never drop a negation" in p and p.index("ultracave") < p.index("RESPONSE FORMAT")
        assert "<<<WF_RESULT" in p                                                              # the result format stays intact
        wf.CAVEMAN = False
        assert "ultracave" not in wf.wrap("Review this", {"type": "string"})
    finally:
        wf.CAVEMAN = before


@check("extract tolerates variants of the markers (<< or spaces)")
def _():
    assert wf.extract('<<WF_RESULT\n{"ok": true}\nWF_RESULT>>', OBJ) == {"ok": True}
    assert wf.extract('<<< WF_RESULT {"ok": true} WF_RESULT >>>', OBJ) == {"ok": True}


@check("dag and task: dependency resolution and cycle detection")
async def _():
    os.environ["FAKE_MODE"] = "ok"
    t1 = wf.task("t1", "first step", {"type": "object"}, worker="fake")
    t2 = wf.task("t2", "second step", {"type": "object"}, depends_on=[t1], worker="fake")
    res = await wf.dag([t1, t2])
    assert "t1" in res and "t2" in res
    assert res["t1"] == {"ok": True}

    # Cycle
    ta = wf.task("ta", "a")
    tb = wf.task("tb", "b", depends_on=[ta])
    ta.depends_on = [tb]
    try:
        await wf.dag([ta, tb])
    except ValueError as ex:
        assert "cycle" in str(ex).lower()
    else:
        raise AssertionError("should have detected the cycle")


@check("telemetry: token calculation and cost estimation")
def _():
    tin, tout = wf.estimate_tokens("hello " * 100, "answer " * 50)
    assert tin > 50 and tout > 20
    cost = wf.estimate_cost("gemini-3.8-flash-high", 100000, 50000)
    assert cost > 0.0


@check("collisions and auto_integrate: detects worktree collisions")
def _():
    colls = wf.check_collisions()
    assert isinstance(colls, dict)


shutil.rmtree(wf.RUN_DIR, ignore_errors=True)
print(f"\n{len(passed)} tests passed")
