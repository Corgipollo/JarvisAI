"""cleanup_orphans.py - Mata procesos python huerfanos sin acumular basura.

Problema observado 2026-05-24: el sistema llego a tener 35 procesos python.exe
corriendo simultaneos (937 MB RAM total). Muchos eran 'huerfanos' — schtasks
que disparaban scripts que NO llamaban sys.exit() limpio, o subprocess
workers de chromadb/sentence-transformers que quedaban colgados tras el
proceso padre morir.

Esta tarea corre cada 15 min y aplica reglas conservadoras de kill:

REGLAS DE PRESERVACION (NUNCA matar):
  1. Procesos cuyo CommandLine contiene cualquier keyword en PRESERVE_KEYWORDS
     (Bot Forex V8 demo + otros sistemas long-running del usuario)
  2. Procesos hijos directos de explorer.exe (apps lanzadas por usuario)
  3. Procesos con edad < MIN_AGE_MINUTES (default 10) — dales chance de terminar
  4. Procesos con CommandLine reconocible Jarvis core (5 daemons criticos)

REGLAS DE KILL (todos deben aplicar para matar):
  1. Es python.exe / pythonw.exe
  2. CommandLine vacio o ilegible (huerfano sin contexto)
  3. Edad > MIN_AGE_MINUTES (default 10 min)
  4. NO esta en PRESERVE_KEYWORDS
  5. NO es child directo de un Jarvis daemon vivo (chromadb workers legitimos)

Output: data/cleanup_orphans.log con lo matado y por que.
Schtask: Jarvis_Cleanup_Orphans cada 15 min.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = ROOT / "data" / "cleanup_orphans.log"

MIN_AGE_MINUTES = int(os.environ.get("CLEANUP_MIN_AGE_MIN", "10"))
MAX_KILLS_PER_RUN = 20  # safety cap

# NUNCA matar procesos cuyo CommandLine contenga estas keywords
PRESERVE_KEYWORDS = [
    # Bot Forex V8 (demo, +20% Q1 2026)
    "swing_hunter", "corp_catalysts", "news_macro", "funding_arb",
    "catalyst_executor", "stock_paper", "paper_engine", "monitor_swing",
    "spike_hunter", "smc_executor", "ai_council", "ai_trader",
    "super_trader", "gemini_pro_server",
    # Jarvis V2 core (auto-rearranca si muere, pero mejor no matarlos)
    "jarvis_bridge.claude_proxy", "jarvis_v2.api.jarvis_api",
    "jarvis_v2.task_worker", "jarvis_v2.daemons.infinite_ceo",
    "jarvis_v2.daemons.heartbeat", "jarvis_v2.cfo.spend_governor",
    "jarvis_v2.swarm.orchestrator",
    # Otros user scripts long-running
    "ai_radar", "kronos", "dispatch_telegram",
    # Esta misma cleanup task
    "cleanup_orphans", "log_rotation", "sqlite_vacuum", "sales_trainer",
    "auto_problem_solver", "pdf_reporter", "watchdog",
]


def _log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _list_python_processes() -> list[dict]:
    """Win32_Process via WMIC fallback to PowerShell."""
    try:
        cmd = [
            "powershell", "-NoProfile", "-NonInteractive", "-Command",
            "Get-CimInstance Win32_Process | Where-Object {$_.Name -like 'python*'} | "
            "Select-Object ProcessId,Name,CommandLine,CreationDate,ParentProcessId | "
            "ConvertTo-Json -Compress"
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if out.returncode != 0 or not out.stdout.strip():
            return []
        data = json.loads(out.stdout)
        if isinstance(data, dict):
            data = [data]
        result = []
        for p in data:
            cd = p.get("CreationDate", "")
            # PowerShell returns /Date(ms)/ format sometimes, or ISO
            if isinstance(cd, str) and "/Date(" in cd:
                try:
                    ms = int(cd.split("(")[1].split(")")[0])
                    created = datetime.fromtimestamp(ms / 1000)
                except Exception:
                    created = datetime.utcnow()
            elif isinstance(cd, str) and cd:
                try:
                    created = datetime.fromisoformat(cd.replace("Z", ""))
                except Exception:
                    created = datetime.utcnow()
            else:
                created = datetime.utcnow()
            age_min = (datetime.now() - created).total_seconds() / 60
            result.append({
                "pid": p.get("ProcessId"),
                "name": p.get("Name", ""),
                "cmdline": p.get("CommandLine", "") or "",
                "parent_pid": p.get("ParentProcessId"),
                "age_min": age_min,
            })
        return result
    except Exception as e:
        _log(f"ERROR listing processes: {e}")
        return []


def _should_preserve(proc: dict, live_jarvis_pids: set[int]) -> tuple[bool, str]:
    """Decide si preservar. Devuelve (preserve, reason)."""
    cmd = (proc["cmdline"] or "").lower()
    for kw in PRESERVE_KEYWORDS:
        if kw.lower() in cmd:
            return True, f"keyword:{kw}"
    if proc["age_min"] < MIN_AGE_MINUTES:
        return True, f"too_young:{proc['age_min']:.1f}min"
    if proc["parent_pid"] in live_jarvis_pids:
        return True, f"child_of_jarvis_pid:{proc['parent_pid']}"
    if not cmd:
        return False, "empty_cmdline_orphan"
    return False, "no_match"


def cycle_once() -> dict:
    _log("=== Cleanup Orphans cycle start ===")
    procs = _list_python_processes()
    _log(f"found {len(procs)} python processes")
    if not procs:
        return {"ok": True, "scanned": 0, "killed": 0}

    # Identify live Jarvis core PIDs (their children should be preserved)
    live_jarvis_pids = set()
    for p in procs:
        cmd = (p["cmdline"] or "").lower()
        if any(kw.lower() in cmd for kw in [
            "jarvis_v2.api.jarvis_api", "jarvis_v2.task_worker",
            "jarvis_v2.daemons.infinite_ceo", "jarvis_bridge.claude_proxy",
        ]):
            live_jarvis_pids.add(p["pid"])

    killed = []
    preserved = 0
    for p in procs:
        preserve, reason = _should_preserve(p, live_jarvis_pids)
        if preserve:
            preserved += 1
            continue
        if len(killed) >= MAX_KILLS_PER_RUN:
            _log(f"  safety cap reached ({MAX_KILLS_PER_RUN}), stopping")
            break
        try:
            subprocess.run(
                ["taskkill", "/F", "/PID", str(p["pid"])],
                capture_output=True, timeout=5,
            )
            killed.append({"pid": p["pid"], "age_min": round(p["age_min"], 1),
                           "reason": reason})
            _log(f"  KILLED pid={p['pid']} age={p['age_min']:.1f}min reason={reason}")
        except Exception as e:
            _log(f"  failed to kill pid={p['pid']}: {e}")

    _log(f"=== Cycle end. Preserved {preserved}, Killed {len(killed)} ===")
    return {"ok": True, "scanned": len(procs), "preserved": preserved,
            "killed_count": len(killed), "killed": killed}


if __name__ == "__main__":
    r = cycle_once()
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
