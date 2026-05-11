"""web_server.py — UI 'Jarvis OS' tipo terminal con queue + estado en vivo.

FastAPI + WebSocket. El frontend (web/index.html) se conecta y recibe:
  - Estado actual del state machine (idle/working/...)
  - Cola de tareas pendientes
  - Última tarea completada
  - Avatar expression (color, label)

El usuario puede:
  - Escribir tareas en lenguaje natural → se agregan a queue
  - Ver historial de tareas completadas
  - Ver el avatar reaccionar matemáticamente al estado
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from jarvis_core import queue_manager                           # noqa: E402

LIVE_STATE = ROOT / "data" / "jarvis_live_state.json"
WEB_DIR = ROOT / "jarvis_core" / "web"

app = FastAPI(title="Jarvis OS")


@app.get("/")
async def root():
    dashboard = WEB_DIR / "dashboard.html"
    if dashboard.exists():
        return FileResponse(str(dashboard))
    index = WEB_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return HTMLResponse("<h1>Jarvis OS</h1><p>UI no instalada</p>")


@app.get("/events")
async def get_events(since: float = 0):
    """Pull eventos del stream + stats agregadas para el dashboard."""
    from jarvis_core.event_stream import tail_events
    events = tail_events(since_ts=float(since), max_events=80)

    # Stats agregadas
    skill_dir = ROOT / "data" / "skill_library"
    role_dir = ROOT / "data" / "role_library"
    tutorial_dir = ROOT / "data" / "tutorial_cache"

    skills_count = 0
    skills_list = []
    if skill_dir.exists():
        idx = skill_dir / "_index.jsonl"
        if idx.exists():
            for line in idx.read_text(encoding="utf-8").splitlines():
                try:
                    skills_list.append(json.loads(line))
                except Exception:
                    continue
            skills_count = len(skills_list)

    roles_count = len(list(role_dir.glob("*.json"))) if role_dir.exists() else 0

    tutorials_count = 0
    frames_count = 0
    if tutorial_dir.exists():
        for d in tutorial_dir.iterdir():
            if d.is_dir():
                tutorials_count += len(list(d.glob("*.mp4")))
                for fr_dir in d.glob("*_frames"):
                    frames_count += len(list(fr_dir.glob("*.jpg")))

    events_file = ROOT / "data" / "jarvis_events.jsonl"
    events_total = 0
    if events_file.exists():
        try:
            events_total = sum(1 for _ in events_file.open("r", encoding="utf-8"))
        except Exception:
            pass

    qstats = queue_manager.stats()

    live_state = ROOT / "data" / "jarvis_live_state.json"
    state = {}
    if live_state.exists():
        try:
            state = json.loads(live_state.read_text(encoding="utf-8"))
        except Exception:
            pass

    return {
        "events": events,
        "stats": {
            "skills": skills_count,
            "roles": roles_count,
            "tutorials": tutorials_count,
            "frames": frames_count,
            "queue_pending": qstats.get("pending", 0),
            "events_total": events_total,
        },
        "skills_list": skills_list,
        "state": state,
    }


@app.get("/state")
async def get_state():
    if LIVE_STATE.exists():
        return json.loads(LIVE_STATE.read_text(encoding="utf-8"))
    return {"state": "unknown"}


@app.get("/queue")
async def get_queue(status: str | None = None):
    return {"tasks": queue_manager.list_tasks(status), "stats": queue_manager.stats()}


class TaskIn(BaseModel):
    text: str
    priority: int = 5


@app.post("/tasks")
async def post_task(task: TaskIn):
    return queue_manager.add_task(task.text, source="user_web", priority=task.priority)


@app.delete("/tasks/completed")
async def clear_completed():
    n = queue_manager.clear_completed()
    return {"removed": n}


@app.websocket("/ws/state")
async def ws_state(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            if LIVE_STATE.exists():
                snap = json.loads(LIVE_STATE.read_text(encoding="utf-8"))
                snap["queue"] = queue_manager.list_tasks()[-30:]
                await ws.send_json(snap)
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_json({"error": str(e)})
        except Exception:
            pass


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7777, log_level="info")
