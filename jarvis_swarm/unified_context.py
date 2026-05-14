"""unified_context.py — Contexto GLOBAL compartido por TODOS los cerebros.

Cada 5 segundos consolida en data/unified_context.json:

  - Pantalla actual (screen_state.json)
  - Tarea activa (active_task_state.json)
  - Skills aprendidas (count + last 5)
  - Sistema (system_brain.json - resumen)
  - Mapa entorno (environment_map.json - resumen)
  - Eventos recientes swarm (swarm_memory.jsonl ultimos 30)
  - Errores recientes (jarvis_errors.jsonl ultimos 10)
  - Procesos del swarm corriendo
  - Recursos host (CPU, RAM, disco)

Cualquier agente lee este archivo y tiene TODO el contexto en 1 sola lectura.
Es la 'memoria de trabajo' del swarm - como la corteza prefrontal humana
que mantiene contexto activo.

Ningun agente toma decision importante sin consultar unified_context primero.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_swarm.base_agent import BaseAgent

DATA = ROOT / "data"
UNIFIED_FILE = DATA / "unified_context.json"


def safe_load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def tail_jsonl(path: Path, n: int = 10) -> list[dict]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-n:]
        return [json.loads(l) for l in lines if l.strip()]
    except Exception:
        return []


def count_files(path: Path, pattern: str = "*.json") -> int:
    if not path.exists():
        return 0
    return len([f for f in path.glob(pattern) if not f.name.startswith("_")])


def get_host_resources() -> dict:
    """RAM, CPU, disco del host VM."""
    try:
        import psutil
        return {
            "cpu_pct": psutil.cpu_percent(interval=0.5),
            "ram_pct": psutil.virtual_memory().percent,
            "ram_avail_gb": round(psutil.virtual_memory().available / (1024**3), 1),
            "disk_pct": psutil.disk_usage("C:/").percent,
            "disk_free_gb": round(psutil.disk_usage("C:/").free / (1024**3), 1),
        }
    except Exception as e:
        return {"error": str(e)}


def get_swarm_processes() -> list[str]:
    """Procesos python corriendo (probablemente del swarm)."""
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if p.info["name"] and "python" in p.info["name"].lower():
                    cmd = " ".join(p.info["cmdline"] or [])
                    # Solo si es de jarvis
                    for keyword in ["jarvis", "self_improve", "watchdog", "mouse",
                                    "vision", "screen", "system_brain", "meta_agent"]:
                        if keyword in cmd.lower():
                            procs.append({
                                "pid": p.info["pid"],
                                "cmd": cmd[:200],
                            })
                            break
            except Exception:
                continue
        return procs
    except Exception:
        return []


class UnifiedContext(BaseAgent):
    name = "unified_context"
    description = "Consolida estado global cada 5s para que todos los cerebros tengan contexto"
    tick_seconds = 5

    def step(self):
        ctx = {
            "ts": datetime.now().isoformat(),
            "_doc": "Contexto unificado global - cualquier agente lee esto",
        }

        # Pantalla actual (de screen_awareness)
        screen = safe_load_json(DATA / "screen_state.json")
        ctx["screen"] = {
            "active_window": screen.get("active_window", {}).get("title", ""),
            "context_desc": screen.get("context_description", ""),
            "last_update": screen.get("ts"),
            "foreground_apps": screen.get("foreground_processes", [])[:10],
        }

        # Tarea activa (de unified_executor)
        active = safe_load_json(DATA / "active_task_state.json")
        ctx["active_task"] = active

        # Skills
        skills_dir = DATA / "skill_library"
        ctx["skills"] = {
            "count": count_files(skills_dir, "*.json"),
        }

        # Eventos recientes swarm
        ctx["recent_events"] = tail_jsonl(DATA / "swarm_memory.jsonl", n=20)

        # Errores recientes
        ctx["recent_errors"] = tail_jsonl(DATA / "jarvis_errors.jsonl", n=5)

        # System brain (resumen)
        brain = safe_load_json(DATA / "system_brain.json")
        ctx["system_brain_summary"] = {
            "has_brain": bool(brain),
            "native_actions_count": len(brain.get("native_system_actions", {})),
            "apps_installed": len(brain.get("installed_apps_detailed", [])),
        }

        # Environment map (resumen)
        env = safe_load_json(DATA / "environment_map.json")
        ctx["environment_summary"] = {
            "has_map": bool(env),
            "apps_count": len(env.get("installed_apps", [])),
            "running_count": len(env.get("running_apps", [])),
            "disks": env.get("disks", []),
        }

        # Procesos swarm corriendo
        ctx["swarm_processes"] = get_swarm_processes()

        # Recursos host
        ctx["host_resources"] = get_host_resources()

        # Escribir atomico (evita race con readers)
        DATA.mkdir(parents=True, exist_ok=True)
        tmp = UNIFIED_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(ctx, ensure_ascii=False, indent=2, default=str),
                       encoding="utf-8")
        try:
            tmp.replace(UNIFIED_FILE)
        except Exception:
            # Windows: si target existe, hay que borrar primero
            if UNIFIED_FILE.exists():
                UNIFIED_FILE.unlink()
            tmp.rename(UNIFIED_FILE)

        return {"ok": True, "action": "consolidated",
                "skills": ctx["skills"]["count"],
                "events": len(ctx["recent_events"]),
                "swarm_procs": len(ctx["swarm_processes"])}


if __name__ == "__main__":
    UnifiedContext().run_loop()
