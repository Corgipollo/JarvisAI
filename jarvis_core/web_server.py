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
    index = WEB_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return HTMLResponse("<h1>Jarvis OS</h1><p>UI no instalada</p>")


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
