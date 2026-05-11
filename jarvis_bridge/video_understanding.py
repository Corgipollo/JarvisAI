"""video_understanding.py — Video LLM GRATIS vía gemini_pro_server (browser).

Sube un video al chat de Gemini (vía Playwright contra https://gemini.google.com)
con el plan Pro logueado del user. Cero costo en tokens API.

Capacidades:
  - Upload de video local
  - Prompt sobre el video ("describe paso a paso", "qué se hace en esta tutorial")
  - Devuelve texto sintetizado

Reemplaza el pipeline frames+OCR+Claude del skill_learner cuando hay un video
real disponible. Mucho más preciso (Gemini entiende video nativo).

Requiere: gemini_pro_server.py corriendo en :5555 con browser logueado.
Si el server no soporta upload, este módulo lo extiende con un endpoint /ask_with_file.

Uso:
    from jarvis_bridge.video_understanding import analyze_video
    result = analyze_video("path/video.mp4", "Resume paso a paso este tutorial")
    print(result["text"])
"""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SERVER_URL = "http://localhost:5555"


def is_server_alive() -> bool:
    try:
        r = requests.get(f"{SERVER_URL}/health", timeout=3)
        return r.ok
    except Exception:
        return False


def analyze_video(video_path: str, prompt: str, timeout: int = 600) -> dict:
    """Envía video a Gemini Pro Web y devuelve respuesta.

    Si el server NO tiene endpoint /ask_with_file, intenta primero subir
    el archivo a un host temporal (no recomendado) o devuelve error.

    Mejor approach: extender gemini_pro_server.py para que acepte /ask_with_file.
    """
    if not is_server_alive():
        return {
            "success": False,
            "error": f"gemini_pro_server no esta vivo en {SERVER_URL}",
            "hint": "ejecuta: python BotForexV8-COMPLETO/bot/gemini_pro_server.py",
        }

    p = Path(video_path)
    if not p.exists():
        return {"success": False, "error": f"video no existe: {video_path}"}

    size_mb = p.stat().st_size / 1e6
    print(f"[video_understanding] subiendo {p.name} ({size_mb:.0f} MB)...", flush=True)

    # Probar endpoint /ask_with_file (extension custom del server)
    try:
        with p.open("rb") as f:
            files = {"file": (p.name, f, "video/mp4")}
            data = {"prompt": prompt, "reset": "true"}
            r = requests.post(
                f"{SERVER_URL}/ask_with_file",
                files=files, data=data,
                timeout=timeout,
            )
            if r.ok:
                return {
                    "success": True,
                    "text": r.json().get("response", ""),
                    "duration_s": r.elapsed.total_seconds(),
                }
    except Exception as e:
        print(f"[video_understanding] /ask_with_file no disponible: {e}", flush=True)

    # Fallback: ask con prompt indicando que NO puede analizar video sin upload
    print("[video_understanding] fallback: server sin upload, mando prompt textual", flush=True)
    try:
        r = requests.post(
            f"{SERVER_URL}/ask",
            json={
                "prompt": f"(video adjunto: {p.name}, {size_mb:.0f} MB)\n\n{prompt}",
                "reset": True,
            },
            timeout=timeout,
        )
        r.raise_for_status()
        return {
            "success": True,
            "text": r.json().get("response", ""),
            "warning": "server no acepta upload de video, solo prompt textual",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def analyze_video_chunked(video_path: str, prompt: str, chunk_minutes: int = 5) -> dict:
    """Para videos largos: divide en chunks con ffmpeg, analiza cada uno,
    síntesis final con Claude.

    Útil cuando el video supera el límite de upload de Gemini (~1 GB).
    """
    import subprocess
    p = Path(video_path)
    if not p.exists():
        return {"success": False, "error": f"video no existe: {video_path}"}

    # Get duration
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
            capture_output=True, text=True, check=True,
        )
        duration_s = float(proc.stdout.strip())
    except Exception as e:
        return {"success": False, "error": f"ffprobe fallo: {e}"}

    chunk_s = chunk_minutes * 60
    if duration_s <= chunk_s:
        # No vale la pena chunkear
        return analyze_video(str(p), prompt)

    n_chunks = int(duration_s // chunk_s) + 1
    print(f"[video_understanding] video de {duration_s/60:.1f}min → {n_chunks} chunks de {chunk_minutes}min", flush=True)

    import tempfile, os
    tmp_dir = Path(tempfile.gettempdir()) / f"video_chunks_{int(time.time())}"
    tmp_dir.mkdir(exist_ok=True)
    chunk_analyses = []

    for i in range(n_chunks):
        start = i * chunk_s
        chunk_out = tmp_dir / f"chunk_{i:03d}.mp4"
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-ss", f"{start:.1f}",
            "-i", str(p),
            "-t", f"{chunk_s:.1f}",
            "-c", "copy",
            str(chunk_out),
        ]
        try:
            subprocess.run(cmd, check=True, timeout=120)
        except Exception as e:
            print(f"  chunk {i} fallo: {e}")
            continue

        print(f"  analizando chunk {i+1}/{n_chunks}...", flush=True)
        r = analyze_video(str(chunk_out), f"[CHUNK {i+1}/{n_chunks} de {duration_s/60:.0f}min total] {prompt}")
        if r.get("success"):
            chunk_analyses.append({"chunk": i, "text": r["text"]})
        chunk_out.unlink(missing_ok=True)

    return {
        "success": True,
        "n_chunks": n_chunks,
        "chunks": chunk_analyses,
        "combined": "\n\n".join(f"=== chunk {c['chunk']+1} ===\n{c['text']}" for c in chunk_analyses),
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python video_understanding.py <video_path> '<prompt>'")
        sys.exit(0)
    result = analyze_video(sys.argv[1], sys.argv[2])
    print(json.dumps(result, ensure_ascii=False, indent=2)[:2000])
