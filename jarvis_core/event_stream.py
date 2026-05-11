"""event_stream.py — Stream de eventos compartido para que la UI los muestre live.

Los learners/explorers escriben aqui. El web_server lo pushea via WebSocket a la UI.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

EVENTS_FILE = Path(__file__).resolve().parents[1] / "data" / "jarvis_events.jsonl"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def emit(source: str, level: str, msg: str, **extra):
    """Emite evento a stream + stdout. level: info/warn/error/success/learning."""
    EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "ts": time.time(),
        "iso": datetime.now().isoformat(),
        "source": source,
        "level": level,
        "msg": msg,
        **extra,
    }
    try:
        with EVENTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # Also print to stdout for legacy
    icon = {"info": ".", "success": "+", "warn": "!", "error": "x",
            "learning": "L", "discover": "?"}.get(level, "-")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{icon}] [{source}] {msg}", flush=True)


def tail_events(since_ts: float = 0, max_events: int = 50) -> list[dict]:
    """Lee últimos N eventos desde un timestamp."""
    if not EVENTS_FILE.exists():
        return []
    events = []
    for line in EVENTS_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-max_events*2:]:
        try:
            e = json.loads(line)
            if e.get("ts", 0) > since_ts:
                events.append(e)
        except Exception:
            continue
    return events[-max_events:]
