#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 alejandro-xoxo
"""
Monitor visual de terminal para workflow-orquestar.
Permite ver en vivo qué está haciendo cada subagente (comandos, herramientas,
archivos modificados, pruebas, logs) en una sola terminal dedicada.

Uso:
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

# Habilitar soporte ANSI en Windows si aplica
if os.name == "nt":
    os.system("")
    import msvcrt

# Paleta ANSI
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
UNDERLINE = "\033[4m"

# Colores de texto
BLACK = "\033[30m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

# Colores de fondo
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
    """Lee incrementalmente el log de un agente sin bloquear."""
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
    """Colorea semánticamente lo que hace el CLI como si fuera una terminal nativa."""
    clean = ANSI_CLEAN.sub("", line).rstrip()
    if not clean:
        return ""

    prefix = "  "
    c_line = clean

    # Detección de herramientas y comandos
    if re.search(r"\b(read_file|reading|leyendo)\b", clean, re.I):
        prefix = f"{CYAN}📖 LEER{RESET} "
    elif re.search(r"\b(edit_file|writing|escribiendo|modificando)\b", clean, re.I):
        prefix = f"{YELLOW}✏️  EDIT{RESET} "
    elif re.search(r"\b(run_command|bash|exec|ejecutando|mvn|pytest|python)\b", clean, re.I):
        prefix = f"{GREEN}💻 CMD {RESET} "
    elif re.search(r"\b(fail|error|exception|falló|tiempo agotado)\b", clean, re.I):
        prefix = f"{RED}❌ ERR {RESET} "
        c_line = f"{RED}{clean}{RESET}"
    elif re.search(r"\b(tests run:|build success|aprobadas|éxito|ok)\b", clean, re.I):
        prefix = f"{GREEN}✔ TEST{RESET} "
        c_line = f"{GREEN}{clean}{RESET}"
    elif re.search(r"^\[\d{2}:\d{2}:\d{2}\]", clean):
        prefix = f"{MAGENTA}⏱ {RESET} "
    elif clean.startswith("<<<") or clean.startswith(">>>"):
        prefix = f"{DIM}──{RESET} "
        c_line = f"{DIM}{clean}{RESET}"

    # Truncar visualmente para no quebrar líneas
    raw_len = len(clean) + 4
    if raw_len > max_w:
        c_line = clean[: max_w - 7] + "..."

    return f"{prefix} {c_line}"


def run_monitor():
    clear_screen()
    base_dir = get_wf_runs_dir()
    selected_agent = 1  # 1-N o 0 para vista global
    spin_idx = 0
    readers: dict[int, AgentLogReader] = {}
    current_run: Path | None = None

    sys.stdout.write("\033[?25l")  # Ocultar cursor
    try:
        while True:
            # Manejo de entrada no bloqueante por teclado
            if os.name == "nt":
                while msvcrt.kbhit():
                    ch = msvcrt.getch()
                    try:
                        k = ch.decode("utf-8").lower()
                        if k in "123456789":
                            selected_agent = int(k)
                        elif k in ("0", "a"):
                            selected_agent = 0  # Global / todos
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

            # Buscar última ejecución
            latest_run = find_latest_run(base_dir)
            if latest_run != current_run:
                current_run = latest_run
                readers.clear()

            # Leer metadata si existe
            status_file = current_run / "status.json" if current_run else None
            status_data = {}
            if status_file and status_file.exists():
                try:
                    status_data = json.loads(status_file.read_text(encoding="utf-8"))
                except Exception:
                    pass

            run_id = status_data.get("run_id", current_run.name if current_run else "Ninguno")
            phase_name = status_data.get("phase", "En espera...")
            workers_info = status_data.get("workers", {})

            # Si no hay status.json pero hay archivos agente-*.log o .json
            if current_run and not workers_info:
                for f in current_run.glob("agente-*.log"):
                    m = re.match(r"agente-(\d+)\.log", f.name)
                    if m:
                        n = int(m.group(1))
                        workers_info.setdefault(str(n), {"n": n, "role": f"Agente {n}", "status": "running"})
                for f in current_run.glob("agente-*.json"):
                    m = re.match(r"agente-(\d+)\.json", f.name)
                    if m:
                        try:
                            j = json.loads(f.read_text(encoding="utf-8"))
                            n = j.get("n", int(m.group(1)))
                            workers_info[str(n)] = {
                                "n": n,
                                "role": j.get("role", f"Agente {n}"),
                                "worker": j.get("worker", "agy"),
                                "model": j.get("model", ""),
                                "status": "ok" if j.get("exit", 0) == 0 else "error",
                                "secs": j.get("secs", 0)
                            }
                        except Exception:
                            pass

            # Actualizar lectores de log
            for n_str in workers_info.keys():
                n = int(n_str)
                log_file = current_run / f"agente-{n}.log" if current_run else None
                if log_file and n not in readers:
                    readers[n] = AgentLogReader(log_file)
                if n in readers:
                    readers[n].update()

            # BUFFER DE SALIDA
            out_buf = ["\033[H"]  # Mover cursor al inicio (sin parpadeo)

            # 1. ENCABEZADO
            title = " 🚀 ORQUESTADOR MULTI-AGENTE (CLI MONITOR) "
            header = f"{BG_BLUE}{WHITE}{BOLD}{title.center(cols)}{RESET}"
            sub_info = f" Run: {BOLD}{run_id}{RESET} │ Fase: {CYAN}{phase_name[:25]}{RESET} │ Agentes: {BOLD}{len(workers_info)}{RESET} │ Teclas: [1-9] Ver agente | [0] Todos | [Q] Salir "
            out_buf.append(header + "\n")
            out_buf.append(sub_info.ljust(cols)[:cols] + "\n")
            out_buf.append(f"{DIM}{'─' * cols}{RESET}\n")

            # 2. PESTAÑAS DE AGENTES
            tabs = []
            for n_str, winfo in sorted(workers_info.items(), key=lambda x: int(x[0])):
                n = int(n_str)
                role = winfo.get("role", f"Agente {n}")
                st = winfo.get("status", "running")
                icon = f"{GREEN}✔{RESET}" if st == "ok" else f"{RED}✖{RESET}" if st == "error" else f"{YELLOW}{spinner}{RESET}"
                worker_lbl = winfo.get("worker", "agy")
                
                is_sel = (selected_agent == n)
                style_on = f"{BG_GRAY}{BOLD}" if is_sel else ""
                style_off = f"{RESET}"
                tabs.append(f"{style_on}[{n}] {icon} {role[:12]} ({worker_lbl}){style_off}")

            tab_line = "  " + "  │  ".join(tabs) if tabs else "  (Esperando a que el orquestador despache agentes...)"
            out_buf.append(tab_line[:cols] + "\n")
            out_buf.append(f"{DIM}{'─' * cols}{RESET}\n")

            # 3. CUERPO DE LOGS / VISOR CLI
            usable_rows = max(5, rows - 7)

            if selected_agent == 0:
                # VISTA MOSAICO (Divide las líneas entre los agentes activos)
                num_w = max(1, len(readers))
                lines_per_w = max(2, usable_rows // num_w)
                for n, r in sorted(readers.items()):
                    winfo = workers_info.get(str(n), {})
                    r_title = f"{BOLD}--- Agente {n}: {winfo.get('role', '')} ({winfo.get('worker', '')}) ---{RESET}"
                    out_buf.append(r_title[:cols] + "\n")
                    w_lines = r.lines[-lines_per_w:] if r.lines else [f"  {DIM}(Esperando comandos...){RESET}"]
                    for l in w_lines:
                        out_buf.append(format_cli_line(l, cols) + "\n")
            else:
                # VISTA DETALLADA DEL AGENTE SELECCIONADO
                r = readers.get(selected_agent)
                winfo = workers_info.get(str(selected_agent), {})
                agent_title = f" {CYAN}● CONSOLA EN VIVO:{RESET} Agente {selected_agent} «{winfo.get('role', 'N/A')}» | Modelo: {winfo.get('model', 'auto')} "
                out_buf.append(agent_title[:cols] + "\n")
                
                if r and r.lines:
                    visible_lines = r.lines[-usable_rows:]
                    for l in visible_lines:
                        out_buf.append(format_cli_line(l, cols) + "\n")
                    # Rellenar filas vacías para evitar saltos
                    for _ in range(usable_rows - len(visible_lines)):
                        out_buf.append(" " * cols + "\n")
                else:
                    out_buf.append(f"\n   {DIM}Iniciando CLI del subagente... esperando primeras trazas de ejecución.{RESET}\n")
                    for _ in range(usable_rows - 2):
                        out_buf.append(" " * cols + "\n")

            # 4. FOOTER STATUS
            footer = f"{DIM}Presiona 1, 2, 3... para enfocar un agente | Q para cerrar el monitor{RESET}"
            out_buf.append(footer[:cols])

            sys.stdout.write("".join(out_buf))
            sys.stdout.flush()
            time.sleep(0.2)

    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\033[?25h")  # Restaurar cursor
        clear_screen()
        print("Monitor cerrado.")


if __name__ == "__main__":
    run_monitor()
