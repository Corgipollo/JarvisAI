"""proactive_suggester.py — Jarvis sugiere tareas SOLA basándose en contexto.

Cada N min mira:
  - Tiempo desde la última actividad de usuario
  - Cerebro Obsidian: proyectos activos, pendientes, último commit
  - Patrones (hora del día, día de la semana)
  - Estado emocional inferido (si user pidió X, sugerir Y relacionado)

Genera sugerencias y las manda a Telegram (o queue como prioridad baja).

Ejemplo:
  "Llevas 3h en GROP. ¿Reviso métricas de hoy y te resumo?"
  "Hace 7 días no subes a TikTok. ¿Edito uno con un clip de manhwa?"
  "Tu Manhua Narrado tiene 5 episodios pendientes. ¿Procesa el siguiente?"
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROXY = "http://127.0.0.1:8088"
SUGGESTIONS_LOG = ROOT / "data" / "proactive_suggestions.jsonl"


def log(msg: str):
    print(f"[proactive {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def get_context() -> dict:
    """Reúne contexto para que Claude proponga sugerencias."""
    ctx = {
        "now": datetime.now().isoformat(),
        "weekday": datetime.now().strftime("%A"),
        "hour": datetime.now().hour,
    }

    # Activos proyectos (de cerebro vault)
    try:
        from jarvis_bridge.cerebro_reader import list_projects, vault_stats
        ctx["active_projects"] = list_projects()
        ctx["vault_stats"] = vault_stats()
    except Exception:
        ctx["active_projects"] = []

    # Skills aprendidas (resumen)
    skill_idx = ROOT / "data" / "skill_library" / "_index.jsonl"
    if skill_idx.exists():
        try:
            skills = [json.loads(l) for l in skill_idx.read_text(encoding="utf-8").splitlines() if l.strip()]
            ctx["skills_count"] = len(skills)
            ctx["skills_sample"] = [s.get("name") for s in skills[-10:]]
        except Exception:
            ctx["skills_count"] = 0

    # Roles aprendidos
    role_idx = ROOT / "data" / "role_library" / "_index.jsonl"
    if role_idx.exists():
        try:
            roles = [json.loads(l) for l in role_idx.read_text(encoding="utf-8").splitlines() if l.strip()]
            ctx["roles"] = [r.get("role") for r in roles]
        except Exception:
            ctx["roles"] = []

    # Última actividad (tiempo desde último learning)
    learnings = ROOT / "data" / "jarvis_learnings.jsonl"
    if learnings.exists():
        try:
            last_line = learnings.read_text(encoding="utf-8").strip().split("\n")[-1]
            last = json.loads(last_line)
            ctx["last_activity_iso"] = last.get("ts")
        except Exception:
            pass

    return ctx


SUGGEST_PROMPT = """Eres Jarvis. Estás analizando el contexto actual de tu usuario Emmanuel
(mexicano, multi-emprendedor: ecommerce GROP, bots trading, manhua narrado, Jarvis AI, etc).

Recibes contexto: hora, proyectos activos, skills aprendidas, última actividad.

Tu trabajo: sugerir 1-3 acciones ÚTILES y CONCRETAS que tú podrías hacer ahora
sin que él te lo pida.

Reglas:
- Concretas, no genéricas ("revisa proyecto X" no "trabaja en algo")
- Aprovecha skills que ya sabes
- Si es hora tarde (>22h), sugiere algo ligero
- Si es horario laboral, sugiere algo de productividad
- NO sugieras cosas que requieran credenciales que no tienes

Output (SOLO JSON array, max 3 items):
[
  {
    "title": "titulo corto (max 60 chars)",
    "rationale": "por qué crees que es útil ahora",
    "action": "que harías exactamente",
    "priority": 1-5,
    "skills_used": ["skill1", "skill2"]
  }
]
"""


def call_claude(system: str, user: str, timeout: int = 120) -> str | None:
    """Llama Claude vía proxy."""
    try:
        r = requests.post(
            f"{PROXY}/v1/messages",
            json={
                "model": "claude-sonnet-4-6",
                "system": system,
                "messages": [{"role": "user", "content": user}],
                "max_tokens": 1500,
            },
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    except Exception as e:
        log(f"proxy fallo: {e}")
        return None


def generate_suggestions() -> list[dict]:
    """Genera sugerencias proactivas via Claude."""
    ctx = get_context()
    user_msg = json.dumps(ctx, ensure_ascii=False, indent=2, default=str)[:3000]
    text = call_claude(SUGGEST_PROMPT, user_msg)
    if not text:
        return []
    m = re.search(r"\[.*\]", text, flags=re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return []


def save_suggestions(suggestions: list[dict]):
    SUGGESTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SUGGESTIONS_LOG.open("a", encoding="utf-8") as f:
        for s in suggestions:
            entry = {**s, "generated_at": datetime.now().isoformat()}
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def send_to_telegram(suggestions: list[dict]):
    """Manda sugerencias al chat Telegram si configurado."""
    cfg = ROOT / "config_telegram.json"
    if not cfg.exists():
        return
    try:
        c = json.loads(cfg.read_text(encoding="utf-8"))
        token = c.get("bot_token")
        chat_id = c.get("admin_chat_id") or (c.get("allowed_user_ids") or [None])[0]
        if not token or not chat_id:
            return
        text = "💡 *Jarvis sugiere:*\n\n" + "\n\n".join(
            f"*{i+1}.* {s.get('title','?')}\n_{s.get('rationale','')}_"
            for i, s in enumerate(suggestions[:3])
        )
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception:
        pass


def loop(tick_minutes: int = 30):
    """Loop autónomo. Cada N min genera sugerencias."""
    log(f"loop iniciado, tick {tick_minutes}min")
    while True:
        try:
            suggestions = generate_suggestions()
            if suggestions:
                log(f"+ {len(suggestions)} sugerencias generadas")
                save_suggestions(suggestions)
                send_to_telegram(suggestions)
            time.sleep(tick_minutes * 60)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log(f"error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        suggestions = generate_suggestions()
        save_suggestions(suggestions)
        print(json.dumps(suggestions, ensure_ascii=False, indent=2))
    else:
        loop()
