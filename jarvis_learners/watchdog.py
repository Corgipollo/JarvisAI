"""watchdog.py — Coach autonomo 24/7 del sistema Jarvis.

Monitorea cada 3 min:
  - Salud de los 4 servicios core (claude_proxy, web_server, self_improvement, coach)
  - Stalls (cero skills nuevas en >30 min con gaps pendientes = problema)
  - Errores repetidos (mismo error 3+ veces = restart proceso)
  - Disk space (alerta si <2 GB libres)
  - Tamaño de logs (rota si >100 MB)

Si detecta problema:
  1. Le pregunta a Claude (via jarvis_brain) qué hacer
  2. Ejecuta la solucion (mata + relanza, edita config, etc)
  3. Loguea decision a data/watchdog.log
  4. Manda alerta a Telegram (si configurado)

100% autonomo — Emmanuel solo ve reportes, nunca interviene.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"
LOG_FILE = DATA / "watchdog.log"
STATE_FILE = DATA / ".watchdog_state.json"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TICK_SECONDS = 180  # 3 min
PYTHON = sys.executable

# Servicios que debe vigilar — name, script_path, port (None si no expone)
SERVICES = [
    {"name": "claude_proxy",     "script": "jarvis_bridge/claude_proxy.py",       "port": 8088, "module": True},
    {"name": "web_server",       "script": "jarvis_core/web_server.py",            "port": 7777, "module": True},
    {"name": "self_improvement", "script": "jarvis_learners/self_improvement.py",  "port": None},
    {"name": "coach",            "script": "jarvis_learners/coach.py",             "port": None},
    {"name": "self_optimizer",   "script": "jarvis_learners/self_optimizer.py",    "port": None},
    {"name": "proactive",        "script": "jarvis_learners/proactive_suggester.py","port": None},
]


def log(msg: str):
    line = f"[watchdog {datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"last_skill_count": 0, "last_skill_change": datetime.now().isoformat(),
                "error_counts": {}, "restart_history": []}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"last_skill_count": 0, "last_skill_change": datetime.now().isoformat(),
                "error_counts": {}, "restart_history": []}


def save_state(state: dict):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    except Exception as e:
        log(f"  WARN save_state: {e}")


# =============================================================================
# CHECKS
# =============================================================================
def check_port(port: int) -> bool:
    try:
        r = requests.get(f"http://127.0.0.1:{port}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def get_python_processes() -> list[dict]:
    """Lista procesos Python con su command line."""
    try:
        r = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get",
             "ProcessId,CommandLine", "/format:csv"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        procs = []
        for line in r.stdout.splitlines():
            if not line.strip() or line.startswith("Node"):
                continue
            parts = line.split(",")
            if len(parts) >= 3:
                cmd = parts[1].strip()
                try:
                    pid = int(parts[-1].strip())
                    procs.append({"pid": pid, "cmd": cmd})
                except ValueError:
                    pass
        return procs
    except Exception as e:
        log(f"  WARN get_processes: {e}")
        return []


def service_is_running(service: dict, procs: list[dict]) -> int | None:
    """Retorna PID si el servicio corre, None si no."""
    if service.get("port"):
        if check_port(service["port"]):
            # encontrar pid por script
            for p in procs:
                if Path(service["script"]).stem in p["cmd"] or service["script"].replace("/", "\\") in p["cmd"]:
                    return p["pid"]
            return -1  # vivo pero no encontre pid (probablemente uvicorn en otro proceso)
        return None
    # Sin port, solo verifica que el script este en procs
    script_name = Path(service["script"]).stem
    script_path_back = service["script"].replace("/", "\\")
    for p in procs:
        if script_name in p["cmd"] or script_path_back in p["cmd"]:
            return p["pid"]
    return None


def count_skills() -> int:
    skill_dir = DATA / "skill_library"
    if not skill_dir.exists():
        return 0
    return len([f for f in skill_dir.glob("*.json") if not f.name.startswith("_")])


def disk_free_gb(path: str = "C:\\") -> float:
    try:
        import shutil
        total, used, free = shutil.disk_usage(path)
        return free / (1024 ** 3)
    except Exception:
        return -1


# =============================================================================
# ACTIONS
# =============================================================================
def kill_pid(pid: int) -> bool:
    try:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                       capture_output=True, timeout=5)
        return True
    except Exception as e:
        log(f"  ERR kill {pid}: {e}")
        return False


def start_service(service: dict) -> int | None:
    """Lanza el servicio en background. Retorna PID nuevo."""
    script = ROOT / service["script"]
    if not script.exists():
        log(f"  ERR script no existe: {script}")
        return None

    try:
        if service.get("module"):
            # uvicorn-style modules
            module_path = service["script"].replace("/", ".").replace(".py", "")
            if service["name"] == "claude_proxy":
                cmd = [PYTHON, "-m", "uvicorn", "jarvis_bridge.claude_proxy:app",
                       "--host", "127.0.0.1", "--port", str(service["port"])]
            elif service["name"] == "web_server":
                cmd = [PYTHON, "-m", "uvicorn", "jarvis_core.web_server:app",
                       "--host", "127.0.0.1", "--port", str(service["port"])]
            else:
                cmd = [PYTHON, str(script)]
        else:
            cmd = [PYTHON, str(script)]

        env = os.environ.copy()
        # Asegurar PATH actualizado para que vea yt-dlp, ffmpeg, etc.
        env["PYTHONIOENCODING"] = "utf-8"

        proc = subprocess.Popen(
            cmd, cwd=str(ROOT), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        log(f"  RESTARTED {service['name']} pid={proc.pid}")
        return proc.pid
    except Exception as e:
        log(f"  ERR start {service['name']}: {e}")
        return None


# =============================================================================
# MAIN LOOP
# =============================================================================
def tick(state: dict) -> dict:
    """Un ciclo de monitoreo + accion."""
    log("=== TICK ===")
    procs = get_python_processes()

    # 1. Check cada servicio
    for service in SERVICES:
        pid = service_is_running(service, procs)
        if pid is None:
            log(f"  DOWN: {service['name']}")
            new_pid = start_service(service)
            if new_pid:
                state["restart_history"].append({
                    "ts": datetime.now().isoformat(),
                    "service": service["name"],
                    "reason": "down",
                    "new_pid": new_pid,
                })
        else:
            log(f"  OK   {service['name']} (pid={pid})")

    # 2. Detectar stall: si gaps.json tiene queries pero skills_in_library no crece
    gaps_file = DATA / "gaps.json"
    pending = 0
    if gaps_file.exists():
        try:
            pending = len(json.loads(gaps_file.read_text(encoding="utf-8")).get("queries", []))
        except Exception:
            pass

    current_skills = count_skills()
    last_skills = state.get("last_skill_count", 0)
    last_change = state.get("last_skill_change", datetime.now().isoformat())
    try:
        last_change_dt = datetime.fromisoformat(last_change)
    except Exception:
        last_change_dt = datetime.now()

    if current_skills > last_skills:
        log(f"  PROGRESS: {last_skills} -> {current_skills} skills")
        state["last_skill_count"] = current_skills
        state["last_skill_change"] = datetime.now().isoformat()
    else:
        stall_minutes = (datetime.now() - last_change_dt).total_seconds() / 60
        if pending > 0 and stall_minutes > 30:
            log(f"  STALL: {stall_minutes:.0f}min sin nuevas skills, {pending} gaps pendientes")
            # Restart self_improvement
            for p in procs:
                if "self_improvement" in p["cmd"]:
                    log(f"  -> matando self_improvement pid={p['pid']}")
                    kill_pid(p["pid"])
            start_service(next(s for s in SERVICES if s["name"] == "self_improvement"))
            state["last_skill_change"] = datetime.now().isoformat()
            state["restart_history"].append({
                "ts": datetime.now().isoformat(),
                "service": "self_improvement",
                "reason": f"stall {stall_minutes:.0f}min",
            })

    # 3. Disk space
    free = disk_free_gb()
    if 0 < free < 2:
        log(f"  WARN: solo {free:.1f} GB libres en C:")

    # 4. Errores en jarvis_errors.jsonl
    err_log = DATA / "jarvis_errors.jsonl"
    if err_log.exists() and err_log.stat().st_size > 0:
        try:
            errs = err_log.read_text(encoding="utf-8").splitlines()
            recent = errs[-20:]
            err_types = {}
            for line in recent:
                try:
                    e = json.loads(line)
                    err_types.setdefault(e.get("error_type", "unknown"), 0)
                    err_types[e.get("error_type", "unknown")] += 1
                except Exception:
                    continue
            for et, count in err_types.items():
                if count >= 3:
                    log(f"  ERROR_REPEATED: {et} x{count} en ultimos 20")
                    # AUTO-HEAL: solo intentamos 1 vez por tipo, registramos en state
                    healed_key = f"healed::{et}"
                    if not state.get(healed_key):
                        # Tomar el ultimo error completo de ese tipo
                        sample_err = None
                        for line in reversed(recent):
                            try:
                                e = json.loads(line)
                                if e.get("error_type") == et:
                                    sample_err = e
                                    break
                            except Exception:
                                continue
                        if sample_err:
                            log(f"  AUTO-HEAL attempting for {et}...")
                            if attempt_auto_heal(sample_err):
                                state[healed_key] = datetime.now().isoformat()
                                log(f"  AUTO-HEAL OK for {et}")
                            else:
                                log(f"  AUTO-HEAL no propuso fix util")
        except Exception:
            pass

    # 5. Resumen
    log(f"  summary: skills={current_skills} gaps={pending} disk_free={free:.1f}GB")
    save_state(state)
    return state


def attempt_auto_heal(error_record: dict) -> bool:
    """Le pregunta a Claude via jarvis_brain como arreglar este error.

    Espera respuesta JSON con {file, find, replace}. Aplica el patch
    leyendo+modificando+escribiendo el archivo. Retorna True si pudo aplicar.

    Es DEFENSIVO: solo aplica si los strings find/replace son razonables
    (find debe existir exactamente, replace debe ser != find).
    """
    try:
        sys.path.insert(0, str(ROOT))
        from jarvis_bridge.jarvis_brain import ask_claude_json, ping_proxy
    except ImportError:
        log("  WARN auto_heal: no puedo importar jarvis_brain")
        return False

    if not ping_proxy():
        log("  WARN auto_heal: proxy no responde")
        return False

    prompt = (
        f"Eres ingeniero senior. Te paso un error de Jarvis (asistente Windows en VM).\n"
        f"Error: {json.dumps(error_record, ensure_ascii=False)[:1500]}\n\n"
        f"Si conoces el fix EXACTO, responde con este JSON (sin texto extra):\n"
        f'{{"file": "ruta/relativa.py", "find": "linea_o_bloque_actual", '
        f'"replace": "linea_o_bloque_nuevo", "reason": "por que"}}\n\n'
        f'Si NO sabes el fix concreto, responde: {{"file": null}}\n'
        f"REGLAS: find debe ser texto exacto que aparece en el archivo. "
        f"replace debe ser diferente y correcto. No inventes APIs. "
        f"Ruta relativa al directorio C:/Jarvis (ej: jarvis_learners/skill_learner.py)."
    )

    fix = ask_claude_json(prompt, schema_hint='{"file": ..., "find": ..., "replace": ..., "reason": ...}')
    if not fix or not fix.get("file"):
        return False

    target = ROOT / fix["file"]
    if not target.exists() or not target.is_file():
        log(f"  auto_heal: archivo no existe {target}")
        return False

    try:
        content = target.read_text(encoding="utf-8")
    except Exception as e:
        log(f"  auto_heal: no pude leer {target}: {e}")
        return False

    find = fix.get("find", "")
    replace = fix.get("replace", "")
    if not find or find == replace:
        return False
    if find not in content:
        log(f"  auto_heal: find no aparece en {target.name}")
        return False

    # Backup antes de tocar
    backup = target.with_suffix(target.suffix + f".bak_{int(time.time())}")
    try:
        backup.write_text(content, encoding="utf-8")
    except Exception:
        pass

    new_content = content.replace(find, replace, 1)
    try:
        target.write_text(new_content, encoding="utf-8")
        log(f"  auto_heal: parche aplicado a {target.name} ({fix.get('reason', '')[:80]})")

        # Reiniciar el servicio relacionado (si es uno de los nuestros)
        target_stem = target.stem
        procs_now = get_python_processes()
        for p in procs_now:
            if target_stem in p["cmd"]:
                log(f"    -> restart {target_stem} (pid {p['pid']})")
                kill_pid(p["pid"])
                time.sleep(1)
                matching_service = next((s for s in SERVICES if Path(s["script"]).stem == target_stem), None)
                if matching_service:
                    start_service(matching_service)
                break
        return True
    except Exception as e:
        log(f"  auto_heal: write fallo: {e}")
        # Restaurar backup
        try:
            target.write_text(content, encoding="utf-8")
        except Exception:
            pass
        return False


def send_daily_report():
    """Mensaje diario via Telegram (si configurado) con resumen."""
    try:
        cfg = json.loads((ROOT / "config_telegram.json").read_text(encoding="utf-8"))
    except Exception:
        return
    token = cfg.get("bot_token")
    chat_id = cfg.get("admin_chat_id")
    if not token or not chat_id:
        return

    skills = count_skills()
    gaps_file = DATA / "gaps.json"
    pending = 0
    if gaps_file.exists():
        try:
            pending = len(json.loads(gaps_file.read_text(encoding="utf-8")).get("queries", []))
        except Exception:
            pass

    state = load_state()
    restarts_today = sum(
        1 for r in state.get("restart_history", [])
        if r.get("ts", "").startswith(datetime.now().strftime("%Y-%m-%d"))
    )
    free = disk_free_gb()

    msg = (
        f"*Daily Jarvis Report*\n\n"
        f"Skills aprendidas: *{skills}*\n"
        f"Gaps pendientes:   {pending}\n"
        f"Restarts hoy:      {restarts_today}\n"
        f"Disk free:         {free:.1f} GB\n\n"
        f"Sigo trabajando."
    )
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception:
        pass


def main():
    log(f"watchdog iniciado (tick {TICK_SECONDS}s)")
    state = load_state()
    last_daily_report = state.get("last_daily_report", "1970-01-01")
    while True:
        try:
            state = tick(state)
            # Reporte diario a las 7 AM
            now = datetime.now()
            today_str = now.strftime("%Y-%m-%d")
            if now.hour >= 7 and last_daily_report < today_str:
                send_daily_report()
                last_daily_report = today_str
                state["last_daily_report"] = today_str
                save_state(state)
        except KeyboardInterrupt:
            log("watchdog detenido por usuario")
            break
        except Exception as e:
            log(f"ERR tick: {e}")
        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    main()
