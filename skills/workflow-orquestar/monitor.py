#!/usr/bin/env python3
# SPDX-License-Identifier: LicenseRef-Proprietary — Copyright (c) 2026 alejandro-xoxo. All rights reserved.
# Copyright (c) 2026 alejandro-xoxo
"""
Visual terminal monitor for workflow-orquestar.
Lets you watch live what each subagent is doing (commands, tools,
modified files, tests, logs) in a single dedicated terminal.

Usage:
    python monitor.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Enable ANSI support on Windows if applicable
if os.name == "nt":
    os.system("")
    import msvcrt

# ANSI palette
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
UNDERLINE = "\033[4m"

# Text colors
BLACK = "\033[30m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

# Background colors
BG_DARK = "\033[48;5;235m"
BG_BLUE = "\033[44m"
BG_GRAY = "\033[48;5;238m"

SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
ANSI_CLEAN = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def clear_screen():
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def get_wf_runs_dir() -> Path:
    base = os.environ.get("WF_RUNS")
    if base:
        return Path(base)
    return Path(tempfile.gettempdir()) / "wf-runs"


def find_latest_run(base_dir: Path) -> Path | None:
    if not base_dir.exists():
        return None
    runs = [d for d in base_dir.iterdir() if d.is_dir()]
    if not runs:
        return None
    runs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
    return runs[0]


class AgentLogReader:
    """Reads an agent's log incrementally without blocking."""
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.offset = 0
        self.lines: list[str] = []

    def update(self) -> list[str]:
        if not self.log_path.exists():
            return []
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self.offset)
                new_data = f.read()
                self.offset = f.tell()
                if new_data:
                    new_lines = new_data.splitlines()
                    self.lines.extend(new_lines)
                    return new_lines
        except OSError:
            pass
        return []


def format_cli_line(line: str, max_w: int) -> str:
    """Semantically colors what the CLI is doing, as if it were a native terminal."""
    clean = ANSI_CLEAN.sub("", line).rstrip()
    if not clean:
        return ""

    prefix = "  "
    c_line = clean

    # Detection of tools and commands
    if re.search(r"\b(read_file|reading)\b", clean, re.I):
        prefix = f"{CYAN}📖 READ{RESET} "
    elif re.search(r"\b(edit_file|writing|modifying)\b", clean, re.I):
        prefix = f"{YELLOW}✏️  EDIT{RESET} "
    elif re.search(r"\b(run_command|bash|exec|running|mvn|pytest|python)\b", clean, re.I):
        prefix = f"{GREEN}💻 CMD {RESET} "
    elif re.search(r"\b(fail|failed|error|exception|timed out)\b", clean, re.I):
        prefix = f"{RED}❌ ERR {RESET} "
        c_line = f"{RED}{clean}{RESET}"
    elif re.search(r"\b(tests run:|build success|passed|success|ok)\b", clean, re.I):
        prefix = f"{GREEN}✔ TEST{RESET} "
        c_line = f"{GREEN}{clean}{RESET}"
    elif re.search(r"^\[\d{2}:\d{2}:\d{2}\]", clean):
        prefix = f"{MAGENTA}⏱ {RESET} "
    elif clean.startswith("<<<") or clean.startswith(">>>"):
        prefix = f"{DIM}──{RESET} "
        c_line = f"{DIM}{clean}{RESET}"

    # Visually truncate so lines do not wrap
    raw_len = len(clean) + 4
    if raw_len > max_w:
        c_line = clean[: max_w - 7] + "..."

    return f"{prefix} {c_line}"


def run_monitor():
    clear_screen()
    base_dir = get_wf_runs_dir()
    selected_agent = 1  # 1-N, or 0 for the global view
    spin_idx = 0
    readers: dict[int, AgentLogReader] = {}
    current_run: Path | None = None

    sys.stdout.write("\033[?25l")  # Hide the cursor
    try:
        while True:
            # Non-blocking keyboard input
            if os.name == "nt":
                while msvcrt.kbhit():
                    ch = msvcrt.getch()
                    try:
                        k = ch.decode("utf-8").lower()
                        if k in "123456789":
                            selected_agent = int(k)
                        elif k in ("0", "a"):
                            selected_agent = 0  # Global / all
                        elif k == "q":
                            return
                        elif k == "l":
                            clear_screen()
                    except UnicodeDecodeError:
                        pass

            term_size = shutil.get_terminal_size((90, 26))
            cols, rows = term_size.columns, term_size.lines
            spin_idx = (spin_idx + 1) % len(SPINNERS)
            spinner = SPINNERS[spin_idx]

            # Find the latest run
            latest_run = find_latest_run(base_dir)
            if latest_run != current_run:
                current_run = latest_run
                readers.clear()

            # Read the metadata if it exists
            status_file = current_run / "status.json" if current_run else None
            status_data = {}
            if status_file and status_file.exists():
                try:
                    status_data = json.loads(status_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

            run_id = status_data.get("run_id", current_run.name if current_run else "None")
            phase_name = status_data.get("phase", "Waiting...")
            workers_info = status_data.get("workers", {})

            # If there is no status.json but there are agent-*.log or .json files
            if current_run and not workers_info:
                for f in current_run.glob("agent-*.log"):
                    m = re.match(r"agent-(\d+)\.log", f.name)
                    if m:
                        n = int(m.group(1))
                        workers_info.setdefault(str(n), {"n": n, "role": f"Agent {n}", "status": "running"})
                for f in current_run.glob("agent-*.json"):
                    m = re.match(r"agent-(\d+)\.json", f.name)
                    if m:
                        try:
                            j = json.loads(f.read_text(encoding="utf-8"))
                            n = j.get("n", int(m.group(1)))
                            workers_info[str(n)] = {
                                "n": n,
                                "role": j.get("role", f"Agent {n}"),
                                "worker": j.get("worker", "agy"),
                                "model": j.get("model", ""),
                                "status": "ok" if j.get("exit", 0) == 0 else "error",
                                "secs": j.get("secs", 0)
                            }
                        except Exception:
                            pass

            # Update the log readers
            for n_str in workers_info.keys():
                n = int(n_str)
                log_file = current_run / f"agent-{n}.log" if current_run else None
                if log_file and n not in readers:
                    readers[n] = AgentLogReader(log_file)
                if n in readers:
                    readers[n].update()

            # OUTPUT BUFFER
            out_buf = ["\033[H"]  # Move the cursor to the top (no flicker)

            # 1. HEADER
            title = " 🚀 MULTI-AGENT ORCHESTRATOR (CLI MONITOR) "
            header = f"{BG_BLUE}{WHITE}{BOLD}{title.center(cols)}{RESET}"
            sub_info = f" Run: {BOLD}{run_id}{RESET} │ Phase: {CYAN}{phase_name[:25]}{RESET} │ Agents: {BOLD}{len(workers_info)}{RESET} │ Keys: [1-9] View agent | [0] All | [Q] Quit "
            out_buf.append(header + "\n")
            out_buf.append(sub_info.ljust(cols)[:cols] + "\n")
            out_buf.append(f"{DIM}{'─' * cols}{RESET}\n")

            # 2. AGENT TABS
            tabs = []
            for n_str, winfo in sorted(workers_info.items(), key=lambda x: int(x[0])):
                n = int(n_str)
                role = winfo.get("role", f"Agent {n}")
                st = winfo.get("status", "running")
                icon = f"{GREEN}✔{RESET}" if st == "ok" else f"{RED}✖{RESET}" if st == "error" else f"{YELLOW}{spinner}{RESET}"
                worker_lbl = winfo.get("worker", "agy")

                is_sel = (selected_agent == n)
                style_on = f"{BG_GRAY}{BOLD}" if is_sel else ""
                style_off = f"{RESET}"
                tabs.append(f"{style_on}[{n}] {icon} {role[:12]} ({worker_lbl}){style_off}")

            tab_line = "  " + "  │  ".join(tabs) if tabs else "  (Waiting for the orchestrator to dispatch agents...)"
            out_buf.append(tab_line[:cols] + "\n")
            out_buf.append(f"{DIM}{'─' * cols}{RESET}\n")

            # 3. LOG BODY / CLI VIEWER
            usable_rows = max(5, rows - 7)

            if selected_agent == 0:
                # TILED VIEW (splits the lines among the active agents)
                num_w = max(1, len(readers))
                lines_per_w = max(2, usable_rows // num_w)
                for n, r in sorted(readers.items()):
                    winfo = workers_info.get(str(n), {})
                    r_title = f"{BOLD}--- Agent {n}: {winfo.get('role', '')} ({winfo.get('worker', '')}) ---{RESET}"
                    out_buf.append(r_title[:cols] + "\n")
                    w_lines = r.lines[-lines_per_w:] if r.lines else [f"  {DIM}(Waiting for commands...){RESET}"]
                    for l in w_lines:
                        out_buf.append(format_cli_line(l, cols) + "\n")
            else:
                # DETAILED VIEW OF THE SELECTED AGENT
                r = readers.get(selected_agent)
                winfo = workers_info.get(str(selected_agent), {})
                agent_title = f" {CYAN}● LIVE CONSOLE:{RESET} Agent {selected_agent} '{winfo.get('role', 'N/A')}' | Model: {winfo.get('model', 'auto')} "
                out_buf.append(agent_title[:cols] + "\n")

                if r and r.lines:
                    visible_lines = r.lines[-usable_rows:]
                    for l in visible_lines:
                        out_buf.append(format_cli_line(l, cols) + "\n")
                    # Pad with empty rows to avoid jumps
                    for _ in range(usable_rows - len(visible_lines)):
                        out_buf.append(" " * cols + "\n")
                else:
                    out_buf.append(f"\n   {DIM}Starting the subagent's CLI... waiting for the first execution traces.{RESET}\n")
                    for _ in range(usable_rows - 2):
                        out_buf.append(" " * cols + "\n")

            # 4. FOOTER STATUS
            footer = f"{DIM}Press 1, 2, 3... to focus an agent | Q to close the monitor{RESET}"
            out_buf.append(footer[:cols])

            sys.stdout.write("".join(out_buf))
            sys.stdout.flush()
            time.sleep(0.2)

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h")  # Restore the cursor
        clear_screen()
        print("Monitor closed.")


if __name__ == "__main__":
    run_monitor()
