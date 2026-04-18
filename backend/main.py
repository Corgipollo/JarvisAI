"""Jarvis AI — Server principal. Voice-first, siempre escuchando."""
import sys
from pathlib import Path

# CRITICO: cargar .env ANTES de cualquier otro import
from dotenv import load_dotenv
_env = Path(__file__).parent.parent / ".env"
if _env.exists():
    load_dotenv(_env, override=True)

import asyncio
import json
import os
import base64
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from core.ollama_client import ollama
from core.claude_client import claude_client
from core.free_ai_client import free_ai
from core.voice import transcribe_audio, text_to_speech
from core.camera import camera
from core.memory import (
    load_memory, save_memory, add_fact, get_facts,
    load_chat_history, save_chat_message, clear_chat_history,
    extract_facts_from_message,
)
from integrations.obsidian import brain
from integrations.weather import get_weather, get_location
from integrations.shopify_client import shopify
from integrations.code_runner import run_python
from integrations.pc_control import open_app, close_app, system_action
from integrations.spotify_client import spotify_action
from integrations.web_search import search_web, search_news
from integrations.claude_code import run_claude_task, is_code_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    health = await ollama.check_health()
    models = await ollama.get_models() if health else []
    if claude_client.is_available:
        brain_type = "Claude API"
    elif free_ai.is_available:
        brain_type = f"Free AI ({free_ai._available_providers[0]})"
    else:
        brain_type = f"Ollama ({len(models)} modelos)"
    print(f"\n  JARVIS AI | Brain: {brain_type} | Port {settings.PORT}\n")
    yield
    camera.stop()


app = FastAPI(title="Jarvis AI", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# ─── Comando router simplificado ───

async def process_command(message: str) -> dict | None:
    """Detecta intenciones y ejecuta. Retorna datos de contexto o None."""
    m = message.lower().strip()

    # Clima
    if any(w in m for w in ["clima", "temperatura", "weather", "lluvia", "hace calor", "hace frio"]):
        return {"type": "weather", "data": await get_weather()}

    # Ubicacion
    if any(w in m for w in ["ubicacion", "donde estoy", "location"]):
        return {"type": "location", "data": await get_location()}

    # Obsidian
    if any(w in m for w in ["notas", "obsidian", "cerebro", "busca en mis notas"]):
        q = m
        for w in ["busca", "en mis notas", "obsidian", "cerebro"]: q = q.replace(w, "")
        return {"type": "obsidian", "data": brain.search(q.strip() or message)}

    # Shopify
    if any(w in m for w in ["tienda", "shopify", "grop", "producto", "precio", "cuanto cuesta"]):
        q = m
        for w in ["cuanto cuesta", "precio de", "en la tienda", "shopify", "grop", "busca"]: q = q.replace(w, "")
        q = q.strip()
        if q and shopify.is_configured:
            return {"type": "shopify", "data": await shopify.search_products(q)}
        elif shopify.is_configured:
            return {"type": "shopify", "data": await shopify.get_store_stats()}

    # Abrir app
    if any(w in m for w in ["abre ", "abrir ", "open "]):
        app_name = m
        for w in ["abre", "abrir", "open", "por favor", "porfa"]: app_name = app_name.replace(w, "")
        return {"type": "pc", "data": await open_app(app_name.strip())}

    # Cerrar app
    if any(w in m for w in ["cierra ", "cerrar ", "close "]):
        app_name = m
        for w in ["cierra", "cerrar", "close"]: app_name = app_name.replace(w, "")
        return {"type": "pc", "data": await close_app(app_name.strip())}

    # Sistema
    if any(w in m for w in ["volumen", "sube el", "baja el", "silencio", "mute", "bloquea", "captura", "screenshot", "bateria", "disco", "ram", "procesos"]):
        return {"type": "pc", "data": await system_action(message)}

    # Spotify
    if any(w in m for w in ["spotify", "musica", "cancion", "reproduce", "ponme", "siguiente", "pausa", "play"]):
        return {"type": "spotify", "data": await spotify_action(message)}

    # Proyectos
    if any(w in m for w in ["proyectos", "que tengo", "mis proyectos"]):
        return {"type": "projects", "data": {"projects": brain.list_projects()}}

    # Busqueda web — para cualquier pregunta de conocimiento/actualidad
    web_triggers = ["busca", "google", "investiga", "noticias", "quien es", "que es",
        "cuanto vale", "tipo de cambio", "dolar", "como esta", "resultado",
        "marcador", "partido", "titular", "alineacion", "11 inicial",
        "precio", "cuanto cuesta", "cuando es", "donde queda",
        "internet", "en linea", "actualizado", "hoy", "barcelona", "futbol"]
    if any(w in m for w in web_triggers):
        q = m
        for w in ["busca en internet", "busca en google", "googlea", "google", "busca", "investiga", "en internet"]:
            q = q.replace(w, "")
        results = await search_web(q.strip() or message, max_results=3)
        if results and not results[0].get("error"):
            return {"type": "web", "data": results}

    return None


# ─── WebSocket principal ───

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()

    # Cargar memoria
    memory = load_memory()
    user = memory.get("user", {})
    facts = memory.get("facts", [])
    history = load_chat_history(10)

    # System prompt con memoria
    mem = [f"Usuario: {user.get('name', 'Emmanuel')}, {user.get('city', 'Queretaro')}"]
    if facts:
        mem.append("Datos: " + "; ".join(facts[-10:]))
    mem_str = "\n".join(mem)

    # Configurar cerebro (Claude > Free AI > Ollama)
    if claude_client.is_available:
        active_brain = claude_client
    elif free_ai.is_available:
        active_brain = free_ai
    else:
        active_brain = ollama

    active_brain.update_system_prompt(mem_str)
    for msg in history[-6:]:
        active_brain.conversation_history.append({"role": msg["role"], "content": msg["content"]})

    await ws.send_json({"type": "connected", "message": f"Jarvis AI conectado. Buenas tardes, {user.get('name', 'Emmanuel')}."})

    try:
        while True:
            data = await ws.receive_json()
            t = data.get("type")

            if t == "chat":
                message = data.get("message", "").strip()
                if not message:
                    continue

                save_chat_message("user", message)

                # Extraer hechos
                for fact in extract_facts_from_message(message):
                    add_fact(fact)

                # === TAREA DE CÓDIGO → Claude Code en background ===
                if is_code_task(message):
                    await ws.send_json({"type": "response_start"})
                    await ws.send_json({"type": "response_chunk", "content": "Entendido, estoy trabajando en eso. Te aviso cuando esté listo."})
                    await ws.send_json({"type": "response_end"})

                    # TTS inmediato
                    try:
                        audio = await text_to_speech("Entendido Emmanuel, estoy trabajando en eso. Te aviso cuando esté listo.")
                        await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "format": "mp3"})
                    except Exception:
                        pass

                    # Lanzar Claude Code en background
                    async def code_callback(msg):
                        try:
                            await ws.send_json({"type": "response_start"})
                            await ws.send_json({"type": "response_chunk", "content": msg})
                            await ws.send_json({"type": "response_end"})
                        except Exception:
                            pass

                    async def do_code_task():
                        result = await run_claude_task(message, callback=code_callback)
                        try:
                            if result["success"]:
                                # Detectar nombre del proyecto para el link
                                proj_name = Path(result["path"]).name
                                has_html = any(f.endswith(".html") for f in result["files"])
                                link = f"http://127.0.0.1:8765/generated/{proj_name}/" if has_html else ""

                                msg = f"Ya está listo, Emmanuel. Creé {len(result['files'])} archivos."
                                if link:
                                    msg += f" Puedes verlo en {link}"

                                # Enviar link clickeable al chat
                                chat_msg = msg
                                if link:
                                    chat_msg = f'Ya está listo. <a href="{link}" target="_blank" style="color:#00d4ff">Ver página →</a> ({len(result["files"])} archivos: {", ".join(result["files"][:5])})'
                            else:
                                msg = f"Hubo un problema: {result.get('error', 'desconocido')}"
                                chat_msg = msg

                            await ws.send_json({"type": "response_start"})
                            await ws.send_json({"type": "response_chunk", "content": chat_msg})
                            await ws.send_json({"type": "response_end"})

                            save_chat_message("assistant", msg)

                            audio = await text_to_speech(msg[:400])
                            await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "format": "mp3"})
                        except Exception as e:
                            print(f"[Code] Notification error: {e}")

                    # Ejecutar en background (no bloquea el WebSocket)
                    asyncio.create_task(do_code_task())
                    continue

                # Ejecutar comando si aplica
                ctx = await process_command(message)

                # Enviar datos de contexto si hay
                if ctx:
                    await ws.send_json({"type": "action_result", "data": ctx})

                # Generar respuesta (Claude o Ollama)
                prompt = message
                if ctx:
                    ctx_str = json.dumps(ctx["data"], default=str, ensure_ascii=False)[:500]
                    prompt = f"[DATOS: {ctx_str}]\n\nPregunta: {message}\n\nResponde en 1-2 oraciones cortas usando los datos."

                full = ""
                await ws.send_json({"type": "response_start"})

                async for chunk in active_brain.chat_stream(prompt):
                    full += chunk
                    await ws.send_json({"type": "response_chunk", "content": chunk})
                await ws.send_json({"type": "response_end"})

                save_chat_message("assistant", full)

                # === TTS SIEMPRE ===
                try:
                    tts = full[:600] if len(full) > 600 else full
                    # Limpiar markdown para TTS
                    tts = tts.replace("**", "").replace("```", "").replace("`", "").replace("#", "").replace("*", "")
                    audio = await text_to_speech(tts)
                    b64 = base64.b64encode(audio).decode()
                    await ws.send_json({"type": "audio", "data": b64, "format": "mp3"})
                except Exception as e:
                    print(f"[TTS] Error: {e}")

            elif t == "voice":
                audio_bytes = base64.b64decode(data.get("audio", ""))
                text = await transcribe_audio(audio_bytes)
                await ws.send_json({"type": "transcription", "text": text})

            elif t == "tts":
                audio = await text_to_speech(data.get("text", ""))
                await ws.send_json({"type": "audio", "data": base64.b64encode(audio).decode(), "format": "mp3"})

            elif t == "camera_start":
                await ws.send_json({"type": "camera_status", "active": camera.start()})

            elif t == "camera_stop":
                camera.stop()
                await ws.send_json({"type": "camera_status", "active": False})

            elif t == "camera_snapshot":
                frame = camera.capture_frame()
                if frame is not None:
                    await ws.send_json({"type": "camera_frame", "image": camera.frame_to_base64(frame)})

            elif t == "clear_history":
                active_brain.clear_history()
                clear_chat_history()
                await ws.send_json({"type": "history_cleared"})

            elif t == "add_fact":
                fact = data.get("fact", "")
                if fact:
                    add_fact(fact)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"[WS] Error: {e}")


# ─── REST ───

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "ollama": await ollama.check_health(),
        "free_ai": free_ai.is_available,
        "claude": claude_client.is_available,
    }

@app.get("/api/weather")
async def weather():
    return await get_weather()

@app.get("/api/location")
async def location():
    return await get_location()

@app.get("/api/obsidian/projects")
async def projects():
    return {"projects": brain.list_projects()}

@app.get("/api/memory")
async def mem():
    return load_memory()


# ─── Servir proyectos generados ───
generated_dir = Path(__file__).parent.parent / "generated"
generated_dir.mkdir(parents=True, exist_ok=True)
app.mount("/generated", StaticFiles(directory=str(generated_dir), html=True), name="generated")

# ─── Servir frontend ───
frontend_dir = Path(__file__).parent.parent / "frontend" / "src"
if frontend_dir.exists():
    app.mount("/styles", StaticFiles(directory=str(frontend_dir / "styles")), name="styles")
    assets_dir = frontend_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/")
    async def index():
        return FileResponse(str(frontend_dir / "index.html"))

    @app.get("/app.js")
    async def js():
        return FileResponse(str(frontend_dir / "app.js"))


if __name__ == "__main__":
    import uvicorn

    # Si se pasa --no-browser, no abre navegador (Electron se encarga)
    if "--no-browser" not in sys.argv:
        import webbrowser, threading
        def open_browser():
            import time; time.sleep(2)
            webbrowser.open(f"http://{settings.HOST}:{settings.PORT}")
        threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(app, host=settings.HOST, port=settings.PORT, reload=False, log_level="info")
