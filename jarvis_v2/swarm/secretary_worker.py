"""secretary_worker.py - Bucle Ver-Pensar-Actuar visual para redes sociales.

NO usa APIs publicas (anti-baneo). Usa Chrome con perfil real + SoM + clicks
humanos. Cada ciclo:

  1. Abre/enfoca Chrome en URL de notificaciones (Twitter/Reddit/Instagram)
  2. screenshot + SoM marca botones/comentarios numerados
  3. Claude lee y decide a cual responder + texto a tipear
  4. Pide gui_mouse_lock, hace click + escribe humanamente, libera lock
  5. Marca el comentario como respondido en Mem para no duplicar

Plataformas soportadas (configurable):
  - Twitter/X: /notifications
  - Reddit: /message/messages
  - Instagram: /direct/inbox

Personality: el prompt del LLM le PROHIBE tono corporativo y le pide errores
sutiles, emojis, modismos LATAM.
"""
from __future__ import annotations

import os
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jarvis_v2.swarm.human_mouse import gui_mouse_lock, human_click, human_type

# Platforms config
PLATFORMS = {
    "twitter": {
        "url": "https://twitter.com/notifications/mentions",
        "task_for_som": "click on a reply or quote-tweet mention I haven't answered",
    },
    "reddit": {
        "url": "https://www.reddit.com/message/messages",
        "task_for_som": "click on an unread reply or comment to my posts",
    },
    "instagram": {
        "url": "https://www.instagram.com/direct/inbox/",
        "task_for_som": "click on an unread DM conversation",
    },
}

DEFAULT_PLATFORM = os.environ.get("JARVIS_SOCIAL_PLATFORM", "twitter")
MAX_REPLIES_PER_CYCLE = int(os.environ.get("JARVIS_MAX_REPLIES", "3"))

PERSONALITY_PROMPT = """Eres la secretaria personal de Emmanuel. Tienes ~25 anios, Mexicana,
escribes en chat como cualquier amigo en redes sociales:
- Sin tono corporativo NUNCA.
- Modismos LATAM ocasionales pero NO forzados ("dale", "esta padre", "ok"
  ocasional, "saludos!")
- Emojis sutiles, max 1 por mensaje. Nada de explosiones de emoji.
- Errores tipograficos MUY ocasionales (perdon por -> perdon x, etc) - sin
  abusar.
- A veces respuestas cortas de 1 linea, a veces 2 oraciones. Variabilidad.
- NUNCA digas que eres IA ni asistente ni bot. NUNCA pidas info personal.
- Si el comentario es spam/insulto: ignorar (response = "SKIP").
- Si es duda compleja sobre negocio: "uy me lo paso para responder con mas
  cabeza luego, saludos!"
"""


def open_browser_to(url: str, timeout: int = 8) -> bool:
    """Abre Chrome al URL. Usa Win+R 'chrome.exe URL' para no depender de PATH."""
    try:
        import subprocess
        # Detecta Chrome path
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        ]
        for path in chrome_paths:
            if Path(path).exists():
                subprocess.Popen([path, url])
                time.sleep(timeout)
                return True
        # Fallback: webbrowser
        import webbrowser
        webbrowser.open(url)
        time.sleep(timeout)
        return True
    except Exception as e:
        print(f"[secretary] browser open failed: {e}", flush=True)
        return False


def find_unread_via_som(task_description: str) -> dict | None:
    """SoM screen scan -> Claude elige numero -> coords. Returns None si nada."""
    try:
        from jarvis_v2.sensor.set_of_mark import generate_som, claude_pick_and_click
        mapping, img = generate_som(scope="active_window")
        if not mapping:
            return None
        res = claude_pick_and_click(task_description, img, mapping)
        if res.get("error"):
            return None
        return res
    except Exception as e:
        print(f"[secretary] SoM failed: {e}", flush=True)
        return None


def read_visible_text_via_vision(screenshot_path: str) -> str:
    """Claude vision describe el contenido del comentario que esta viendo."""
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_with_image
        return ask_claude_with_image(
            "Esto es una pantalla de notificaciones de red social. "
            "Identifica el comentario/mensaje recibido (NO mis posts) y "
            "extrae SOLO el texto del mensaje recibido. "
            "Si no hay mensajes nuevos visibles, responde 'NONE'.",
            screenshot_path, max_tokens=300,
        ) or ""
    except Exception as e:
        print(f"[secretary] vision read failed: {e}", flush=True)
        return ""


def generate_reply(received_text: str, context: str = "") -> str:
    """Genera respuesta con personality Mexicana 25-anios. SKIP si spam."""
    try:
        from jarvis_bridge.jarvis_brain import ask_claude
        prompt = (
            f"COMENTARIO RECIBIDO: {received_text[:500]}\n"
            f"CONTEXTO PREVIO: {context[:200]}\n\n"
            "Genera una respuesta corta (1-2 lineas) segun tu personality. "
            "Si es spam, insulto o vacio, responde literalmente 'SKIP'."
        )
        resp = ask_claude(prompt, system=PERSONALITY_PROMPT,
                          model="claude-haiku-4-5-20251001",
                          max_tokens=200) or ""
        return resp.strip().strip('"').strip("'")
    except Exception as e:
        print(f"[secretary] reply gen failed: {e}", flush=True)
        return "SKIP"


def mark_replied_in_mem(message_text: str, reply_text: str):
    """Guarda en Mem para evitar duplicate replies."""
    try:
        from jarvis_v2.memory.memory_manager import save_lesson
        save_lesson(
            insight=f"Respondi al comentario: '{message_text[:100]}' con '{reply_text[:80]}'",
            tags=["secretary", "replied", "social_media"],
            context=f"ts={datetime.utcnow().isoformat()}",
            severity="low",
        )
    except Exception:
        pass


def already_replied(message_text: str) -> bool:
    """Check Mem si ya respondi a algo muy similar (semantic)."""
    try:
        from jarvis_v2.memory.memory_manager import recall_lessons
        recent = recall_lessons(
            f"Respondi al comentario: {message_text[:80]}",
            top_k=3,
            tag_filter=["replied"],
        )
        # Si similarity > 0.85, probablemente ya respondi
        return any(l.get("similarity", 0) > 0.85 for l in recent)
    except Exception:
        return False


def scan_and_reply(platform: str | None = None) -> dict:
    """Una iteracion completa: open browser -> find replies -> respond."""
    platform = platform or DEFAULT_PLATFORM
    if platform not in PLATFORMS:
        return {"error": f"unknown_platform: {platform}",
                "replied_count": 0, "platform": platform}

    cfg = PLATFORMS[platform]
    print(f"[secretary] starting cycle: {platform}", flush=True)

    if not open_browser_to(cfg["url"], timeout=10):
        return {"error": "browser_open_failed",
                "replied_count": 0, "platform": platform}

    replied_count = 0
    errors = []

    for attempt in range(MAX_REPLIES_PER_CYCLE):
        try:
            # 1. SoM scan + Claude pick
            with gui_mouse_lock:
                target = find_unread_via_som(cfg["task_for_som"])
            if not target:
                break

            # 2. Read what we're about to reply to
            from pathlib import Path as P
            shot_path = ROOT / "data" / f"secretary_shot_{int(time.time())}.png"
            try:
                import pyautogui
                pyautogui.screenshot(str(shot_path))
            except Exception:
                pass
            received = read_visible_text_via_vision(str(shot_path))
            if not received or received.strip().upper() == "NONE":
                break
            if already_replied(received):
                # Skip + scroll a bit para ver otra cosa
                print(f"[secretary] already replied to: {received[:60]}",
                      flush=True)
                continue

            # 3. Click on it
            with gui_mouse_lock:
                human_click(target["center_x"], target["center_y"])
                time.sleep(random.uniform(1.5, 3.0))

            # 4. Generate reply
            reply = generate_reply(received)
            if reply.strip().upper() == "SKIP" or not reply:
                print(f"[secretary] SKIP: {received[:60]}", flush=True)
                continue

            # 5. Find reply textarea (SoM again)
            with gui_mouse_lock:
                ta = find_unread_via_som(
                    "click on the reply text area (input field where I would type)"
                )
                if not ta:
                    errors.append("no_textarea_found")
                    continue
                human_click(ta["center_x"], ta["center_y"])
                time.sleep(random.uniform(0.5, 1.2))
                human_type(reply, base_wpm=70 + random.randint(-10, 10))
                time.sleep(random.uniform(0.8, 2.0))

                # 6. Find & click "Reply"/"Send" button
                send_btn = find_unread_via_som(
                    "click on the Reply, Send, Post or submit button"
                )
                if send_btn:
                    human_click(send_btn["center_x"], send_btn["center_y"])
                    time.sleep(random.uniform(2.0, 4.0))
                    mark_replied_in_mem(received, reply)
                    replied_count += 1
                    print(f"[secretary] REPLIED: '{received[:50]}' -> '{reply[:50]}'",
                          flush=True)
                else:
                    errors.append("no_send_btn")
        except Exception as e:
            errors.append(f"attempt_{attempt}: {type(e).__name__}: {e}")
            print(f"[secretary] error attempt {attempt}: {e}", flush=True)
        # Pause humano entre comentarios
        await_time = random.uniform(60, 180)
        print(f"[secretary] esperando {await_time:.0f}s antes del proximo",
              flush=True)
        time.sleep(await_time)

    return {
        "platform": platform,
        "replied_count": replied_count,
        "errors": errors,
        "ts": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    import json as J
    res = scan_and_reply()
    print(J.dumps(res, indent=2, ensure_ascii=False))
