"""
sandbox.py — Modo seguro para training.

SANDBOX_MODE=1 → no ejecuta acciones reales que afecten apps del usuario.
Solo registra "habria hecho X". Permite entrenar sin que Jarvis abra/cierre
apps reales del workflow del user mientras trabaja.

Uso:
    import os
    os.environ["JARVIS_SANDBOX"] = "1"
    from sandbox import is_sandbox, sandbox_log
    if is_sandbox():
        sandbox_log("would have opened telegram")
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SANDBOX_LOG = DATA_DIR / "jarvis_sandbox.jsonl"


def is_sandbox() -> bool:
    return os.environ.get("JARVIS_SANDBOX", "0") in ("1", "true", "True", "yes")


def sandbox_log(action: str, details: dict | None = None) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now().isoformat(),
        "action": action,
        "details": details or {},
    }
    with SANDBOX_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
