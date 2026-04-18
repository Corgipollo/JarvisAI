"""Sistema de memoria persistente para Jarvis AI."""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from config import settings


MEMORY_DIR = Path(settings.PROJECT_ROOT) / "data"
MEMORY_FILE = MEMORY_DIR / "memory.json"
CHAT_HISTORY_FILE = MEMORY_DIR / "chat_history.json"


def _ensure_dir():
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def load_memory() -> dict:
    """Carga toda la memoria persistente."""
    _ensure_dir()
    if MEMORY_FILE.exists():
        try:
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            return _default_memory()
    return _default_memory()


def _default_memory() -> dict:
    return {
        "user": {
            "name": "Emmanuel Pedraza",
            "city": "Queretaro",
            "country": "MX",
            "preferences": {
                "language": "es",
                "voice": "es-MX-JorgeNeural",
                "auto_tts": True,
            },
        },
        "facts": [],
        "last_session": None,
    }


def save_memory(memory: dict):
    """Guarda la memoria persistente."""
    _ensure_dir()
    memory["last_session"] = datetime.now().isoformat()
    MEMORY_FILE.write_text(
        json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_fact(fact: str):
    """Agrega un hecho a la memoria."""
    memory = load_memory()
    # No duplicar
    if fact not in memory["facts"]:
        memory["facts"].append(fact)
        # Mantener max 200 facts
        if len(memory["facts"]) > 200:
            memory["facts"] = memory["facts"][-200:]
        save_memory(memory)


def get_facts() -> list[str]:
    """Retorna todos los hechos memorizados."""
    return load_memory().get("facts", [])


def get_user_info() -> dict:
    """Retorna info del usuario."""
    return load_memory().get("user", {})


# ─── Chat History ───

def load_chat_history(limit: int = 50) -> list[dict]:
    """Carga historial de chat persistente."""
    _ensure_dir()
    if CHAT_HISTORY_FILE.exists():
        try:
            history = json.loads(CHAT_HISTORY_FILE.read_text(encoding="utf-8"))
            return history[-limit:]
        except Exception:
            return []
    return []


def save_chat_message(role: str, content: str):
    """Guarda un mensaje en el historial."""
    _ensure_dir()
    history = []
    if CHAT_HISTORY_FILE.exists():
        try:
            history = json.loads(CHAT_HISTORY_FILE.read_text(encoding="utf-8"))
        except Exception:
            history = []

    history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    })

    # Mantener max 500 mensajes
    if len(history) > 500:
        history = history[-500:]

    CHAT_HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def clear_chat_history():
    """Limpia el historial de chat."""
    _ensure_dir()
    CHAT_HISTORY_FILE.write_text("[]", encoding="utf-8")


# ─── Extraccion automatica de hechos del chat ───

FACT_TRIGGERS = [
    "me llamo", "mi nombre es", "soy de", "vivo en", "trabajo en",
    "mi telefono", "mi correo", "mi email", "me gusta", "no me gusta",
    "mi cumple", "naci en", "tengo", "mi direccion", "mi auto",
    "prefiero", "odio", "favorit", "mi empresa", "mi negocio",
]


def extract_facts_from_message(message: str) -> list[str]:
    """Extrae hechos del mensaje del usuario si contiene info personal."""
    msg_lower = message.lower()
    extracted = []
    for trigger in FACT_TRIGGERS:
        if trigger in msg_lower:
            extracted.append(message.strip())
            break
    return extracted
