#!/usr/bin/env python3
"""
Git-Doctor (Universal Cross-Platform GitFlow & Commit Hygiene Auditor)
Works on Windows, Linux, and macOS using only the Python standard library.

Checks:
1. GitFlow structure: presence of `develop` alongside `main`/`master`.
2. Direct edits on protected branches (`main`, `master`, `develop`).
3. Branch naming convention (`feat/*`, `fix/*`, `chore/*`, `refactor/*`, `release/*`, `hotfix/*`).
4. Sensitive files in working tree / staging area (`.env`, `.pem`, `.key`, credentials, etc.).
5. Recent commits: Conventional Commits format, subject length <= 72 chars, no trailing period,
   and ZERO AI watermarks (`Co-Authored-By: Claude/Gemini/Cursor/Copilot`, `Generated with...`, etc.).
6. Dry-run conflict simulation (`git merge-tree --write-tree`) for:
   - current branch -> develop
   - develop -> main
7. Optional `--fix-config` flag to configure `merge.conflictstyle=zdiff3`, `rerere.enabled=true`,
   and create `develop` from `main` if missing.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from typing import List, Tuple

# ANSI colors (supported on Linux, macOS, and modern Windows terminals)
RESET = "\033[0m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
GRAY = "\033[90m"


def run_git(args: List[str]) -> Tuple[int, str]:
    """Run a git command and return (returncode, stdout_and_stderr)."""
    proc = subprocess.run(
        ["git"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout.strip()


def main() -> int:
    # Enable ANSI colors on Windows console if needed
    if sys.platform == "win32":
        subprocess.run("", shell=True)
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Git-Work Universal Auditor (GitFlow + Conventional Commits + Conflict Dry-Run)"
    )
    parser.add_argument(
        "-n",
        "--last-commits",
        type=int,
        default=15,
        help="Number of recent commits to audit (default: 15)",
    )
    parser.add_argument(
        "--fix-config",
        action="store_true",
        help="Apply recommended git config (zdiff3, rerere) and create 'develop' if missing",
    )
    args = parser.parse_args()

    code, inside = run_git(["rev-parse", "--is-inside-work-tree"])
    if code != 0 or inside != "true":
        print(f"{RED}[ERROR] El directorio actual no es un repositorio Git.{RESET}")
        return 1

    code, branches_raw = run_git(["branch", "--format=%(refname:short)"])
    branches = [b.strip() for b in branches_raw.splitlines() if b.strip()]

    prod_branch = "main" if "main" in branches else ("master" if "master" in branches else "main")
    dev_branch = (
        "develop"
        if "develop" in branches
        else ("developer" if "developer" in branches else "")
    )

    if args.fix_config:
        run_git(["config", "merge.conflictstyle", "zdiff3"])
        run_git(["config", "rerere.enabled", "true"])
        run_git(["config", "rerere.autoupdate", "true"])
        print(
            f"{GREEN}[OK] Configuracion Git aplicada: merge.conflictstyle=zdiff3, rerere.enabled=true{RESET}"
        )
        has_head, _ = run_git(["rev-parse", "--verify", "HEAD"])
        if has_head == 0 and not dev_branch and prod_branch in branches:
            c, _ = run_git(["branch", "develop", prod_branch])
            if c == 0:
                dev_branch = "develop"
                branches.append("develop")
                print(
                    f"{GREEN}[OK] Rama 'develop' creada automaticamente desde '{prod_branch}' (GitFlow).{RESET}"
                )

    _, current_branch = run_git(["branch", "--show-current"])

    print(f"{CYAN}=== GIT-WORK AUDITORIA UNIVERSAL (GITFLOW) ==={RESET}")
    print(f"Rama actual     : {current_branch or '(detached HEAD)'}")
    print(f"Rama produccion : {prod_branch}")
    print(f"Rama integracion: {dev_branch if dev_branch else '[FALTA CREAR develop]'}")

    warnings = 0

    # 1. Check develop branch existence
    if not dev_branch:
        print(
            f"{YELLOW}[ALERTA GITFLOW] No existe la rama 'develop'. En GitFlow todo el desarrollo se integra en 'develop' antes de pasar a '{prod_branch}'.{RESET}"
        )
        print(
            f"{YELLOW}                 Creala con: git checkout -b develop {prod_branch} (o ejecuta con --fix-config){RESET}"
        )
        warnings += 1

    # 2. Check uncommitted changes directly on main/master/develop
    _, status_raw = run_git(["status", "--porcelain"])
    status_lines = [line for line in status_raw.splitlines() if line.strip()]

    if current_branch in ("main", "master", "develop", "developer") and status_lines:
        print(
            f"{YELLOW}[ALERTA GITFLOW] Tienes {len(status_lines)} archivo(s) modificado(s) directamente sobre la rama protegida '{current_branch}'.{RESET}"
        )
        print(
            f"{YELLOW}                 En GitFlow el codigo se escribe en ramas hijas desde 'develop': git switch -c feat/nombre-corto{RESET}"
        )
        warnings += 1

    # 3. Check branch naming convention
    valid_branch_re = re.compile(
        r"^(main|master|develop|developer|(feat|fix|chore|refactor|docs|test|perf|style|build|ci|release|hotfix)/[a-z0-9._\-]+)$"
    )
    if current_branch and not valid_branch_re.match(current_branch):
        print(
            f"{YELLOW}[ALERTA RAMA] La rama '{current_branch}' no sigue la nomenclatura GitFlow (feat/*, fix/*, refactor/*, chore/*, release/*, hotfix/*).{RESET}"
        )
        warnings += 1

    # 4. Check sensitive files in status
    sensitive_re = re.compile(
        r"(\.env(\..+)?$|\.pem$|\.key$|credentials|secret|id_rsa|local\.properties$)",
        re.IGNORECASE,
    )
    for line in status_lines:
        if sensitive_re.search(line):
            print(
                f"{RED}[PELIGRO] Posible archivo sensible detectado en git status: {line}{RESET}"
            )
            warnings += 1

    # 5. Audit recent commits
    has_head, _ = run_git(["rev-parse", "--verify", "HEAD"])
    if has_head != 0:
        print(f"\n{CYAN}--- Auditoria de ultimos commits ---{RESET}")
        print(f"  {GRAY}[INFO] El repositorio aun no tiene commits.{RESET}")
        color = GREEN if warnings == 0 else YELLOW
        print(f"\n{color}=== Resumen: {warnings} advertencia(s) encontrada(s) ==={RESET}")
        return 0

    _, log_raw = run_git(
        ["log", f"-n{args.last_commits}", "--format=%h|%s|%b<<<END_COMMIT>>>"]
    )
    entries = [e.strip() for e in log_raw.split("<<<END_COMMIT>>>") if e.strip()]

    conv_re = re.compile(
        r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([a-zA-Z0-9_\-/]+\))?!?: .+"
    )
    watermark_re = re.compile(
        r"(Co-Authored-By:\s*(Claude|Gemini|Cursor|Copilot|OpenAI|Anthropic|Aider|Windsurf)|Generated with (Claude|Gemini|Cursor)|🤖)",
        re.IGNORECASE,
    )

    print(f"\n{CYAN}--- Auditoria de ultimos commits ---{RESET}")
    for entry in entries:
        parts = entry.split("|", 2)
        if len(parts) < 2:
            continue
        commit_hash = parts[0].strip()
        subject = parts[1].strip()
        body = parts[2].strip() if len(parts) > 2 else ""

        issues: List[str] = []
        if len(subject) > 72:
            issues.append(f"Asunto demasiado largo ({len(subject)} chars > 72)")
        if not subject.startswith("Merge ") and not conv_re.match(subject):
            issues.append("No sigue Conventional Commits (<tipo>(<alcance>): <desc>)")
        if subject.endswith("."):
            issues.append("Termina en punto final")
        if watermark_re.search(subject) or watermark_re.search(body):
            issues.append("CONTIENE MARCA DE AGUA / CO-AUTHOR DE IA")

        if issues:
            print(f"  {YELLOW}[!] {commit_hash} : {subject}{RESET}")
            for iss in issues:
                print(f"      {RED}-> {iss}{RESET}")
            warnings += 1
        else:
            print(f"  {GREEN}[OK] {commit_hash} : {subject}{RESET}")

    # 6. Pre-check merges in GitFlow chain (current -> develop -> main)
    print(f"\n{CYAN}--- Pre-chequeo de Fusiones GitFlow ---{RESET}")
    target_base = dev_branch if dev_branch else prod_branch
    if current_branch and current_branch not in (prod_branch, dev_branch):
        c, out = run_git(["merge-tree", "--write-tree", target_base, current_branch])
        if c == 0:
            print(
                f"  {GREEN}[OK] '{current_branch}' -> '{target_base}': Fusion limpia garantizada (0 conflictos).{RESET}"
            )
        else:
            print(
                f"  {RED}[CONFLICTO] '{current_branch}' -> '{target_base}' tendra conflictos:{RESET}"
            )
            for line in out.splitlines():
                if "CONFLICT" in line:
                    print(f"      {YELLOW}{line}{RESET}")
            warnings += 1

    if dev_branch and prod_branch in branches:
        c, out = run_git(["merge-tree", "--write-tree", prod_branch, dev_branch])
        if c == 0:
            print(
                f"  {GREEN}[OK] '{dev_branch}' -> '{prod_branch}': Pase a produccion limpio (0 conflictos).{RESET}"
            )
        else:
            print(
                f"  {RED}[CONFLICTO] '{dev_branch}' -> '{prod_branch}' tendra conflictos al pasar a produccion:{RESET}"
            )
            for line in out.splitlines():
                if "CONFLICT" in line:
                    print(f"      {YELLOW}{line}{RESET}")
            warnings += 1

    color = GREEN if warnings == 0 else YELLOW
    print(f"\n{color}=== Resumen: {warnings} advertencia(s) encontrada(s) ==={RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
