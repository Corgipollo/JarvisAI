"""telegram_notifier.py — Manda notificaciones proactivas a Telegram.

Watch:
  - data/skill_library/_index.jsonl: cuando llega skill nueva, avisa
  - data/role_library/_index.jsonl: rol nuevo aprendido
  - data/jarvis_errors.jsonl: errores criticos

Es un loop separado del bot (lectura solamente, no recibe input).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CONFIG_FILE = ROOT / "config_telegram.json"
STATE_FILE = ROOT / "data" / ".telegram_notifier_state.json"


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"skills_count": 0, "roles_count": 0, "errors_count": 0}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"skills_count": 0, "roles_count": 0, "errors_count": 0}


def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(1 for _ in path.open(encoding="utf-8"))
    except Exception:
        return 0


def last_jsonl_entry(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        if not lines or not lines[-1].strip():
            return None
        return json.loads(lines[-1])
    except Exception:
        return None


def send(text: str, cfg: dict):
    token = cfg.get("bot_token")
    chat_id = cfg.get("admin_chat_id") or (cfg.get("allowed_user_ids") or [None])[0]
    if not token or not chat_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except Exception:
        pass


def loop():
    cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {}
    if not cfg.get("bot_token"):
        print("[notifier] sin bot_token configurado, saliendo")
        sys.exit(0)

    print("[notifier] watch loop iniciado", flush=True)
    skill_idx = ROOT / "data" / "skill_library" / "_index.jsonl"
    role_idx = ROOT / "data" / "role_library" / "_index.jsonl"
    errors_log = ROOT / "data" / "jarvis_errors.jsonl"

    state = load_state()
    while True:
        try:
            # Skills nuevas
            current_skills = count_lines(skill_idx)
            if current_skills > state["skills_count"]:
                diff = current_skills - state["skills_count"]
                last = last_jsonl_entry(skill_idx)
                msg = f"✨ *+{diff} skill nueva*"
                if last:
                    msg += f"\n📚 {last.get('name', '?')}\n_(confidence {last.get('confidence', '?')})_"
                send(msg, cfg)
                state["skills_count"] = current_skills

            # Roles nuevos
            current_roles = count_lines(role_idx)
            if current_roles > state["roles_count"]:
                last = last_jsonl_entry(role_idx)
                if last:
                    msg = (
                        f"🎓 *Rol nuevo aprendido*\n"
                        f"👤 {last.get('role','?')}\n"
                        f"🔧 {last.get('tools_count','?')} herramientas\n"
                        f"📌 {last.get('skills_required_count','?')} skills auto-encoladas"
                    )
                    send(msg, cfg)
                state["roles_count"] = current_roles

            # Errores criticos (cada N errores nuevos = ping)
            current_errors = count_lines(errors_log)
            if current_errors - state["errors_count"] >= 5:
                send(f"⚠️ *{current_errors - state['errors_count']} errores nuevos* — revisa logs", cfg)
                state["errors_count"] = current_errors

            save_state(state)
            time.sleep(45)  # check cada 45s
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[notifier] error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    loop()
