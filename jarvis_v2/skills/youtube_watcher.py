"""youtube_watcher.py - Skill para que Jarvis 'vea' tutoriales de YouTube.

Estrategia 2-fases (rapido -> profundo):
  1. transcript-api: extrae subtitulos en 0.2s sin descargar nada (90% de los casos).
  2. fallback: descarga video baja-res + Gemini Files API (audio+video) si transcript
     no existe o si el usuario pide analisis visual explicito.

Dependencias: pip install yt-dlp google-generativeai youtube-transcript-api
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2] / "workspace" / "yt"
WORKSPACE.mkdir(parents=True, exist_ok=True)


def _extract_video_id(url: str) -> str | None:
    """Saca el video_id de cualquier formato de URL YouTube."""
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([0-9A-Za-z_-]{11})",
        r"^([0-9A-Za-z_-]{11})$",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def get_transcript(url: str, lang_preference: tuple[str, ...] = ("es", "en")) -> str | None:
    """Saca el transcript del video sin descargar. Devuelve None si no hay subs."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        print("[yt] youtube_transcript_api no instalado")
        return None
    vid = _extract_video_id(url)
    if not vid:
        return None
    api = YouTubeTranscriptApi()
    try:
        # Intenta idiomas preferidos primero
        for lang in lang_preference:
            try:
                snippets = api.fetch(vid, languages=[lang])
                return " ".join(s.text for s in snippets)
            except Exception:
                continue
        # Default: cualquier idioma disponible
        snippets = api.fetch(vid)
        return " ".join(s.text for s in snippets)
    except Exception as e:
        print(f"[yt] transcript fail {vid}: {e}")
        return None


def analyze_via_gemini_video(url: str, prompt: str,
                              model_name: str = "models/gemini-2.5-flash") -> str:
    """Fallback: descarga baja-res + Gemini Files API.
    Requiere GEMINI_API_KEY en env."""
    import google.generativeai as genai
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return "ERROR: GEMINI_API_KEY no seteado"
    genai.configure(api_key=api_key)

    vid = _extract_video_id(url) or "video"
    video_path = WORKSPACE / f"{vid}.mp4"
    if video_path.exists():
        video_path.unlink()

    print(f"[yt] descargando {url} -> {video_path}")
    cmd = (f'yt-dlp -f "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]" '
           f'-o "{video_path}" {url}')
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return f"ERROR yt-dlp: {r.stderr[-300:]}"

    print("[yt] subiendo a Gemini Files API")
    video_file = genai.upload_file(path=str(video_path))
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)
    if video_file.state.name == "FAILED":
        return "ERROR: Gemini Files API fallo"

    model = genai.GenerativeModel(model_name=model_name)
    response = model.generate_content([video_file, prompt])
    try:
        genai.delete_file(video_file.name)
    except Exception:
        pass
    try:
        video_path.unlink()
    except Exception:
        pass
    return response.text


def watch_youtube(url: str,
                   prompt: str = "Resume paso a paso lo que hace este video. Si menciona botones, comandos o pasos especificos, listalos.",
                   force_visual: bool = False) -> dict:
    """Entry point. Devuelve dict con:
        - method: 'transcript' | 'gemini_video' | 'error'
        - text: transcript o analisis LLM
        - summary: si transcript, LLM summary del transcript
    """
    if not force_visual:
        transcript = get_transcript(url)
        if transcript and len(transcript) > 100:
            # Resumir DIRECTO con Gemini API (evita loop si el proxy claude
            # esta invocando esta misma sesion del CLI claude)
            try:
                api_key = os.environ.get("GEMINI_API_KEY", "")
                if not api_key:
                    raise RuntimeError("GEMINI_API_KEY no seteado")
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("models/gemini-2.5-flash")
                resp = model.generate_content(
                    f"TRANSCRIPT TUTORIAL YOUTUBE:\n{transcript[:8000]}\n\n"
                    f"INSTRUCCION: {prompt}\n\n"
                    "Responde directo, en espanol, sin preamble.",
                    generation_config={"max_output_tokens": 1500,
                                        "temperature": 0.3},
                )
                summary = resp.text if hasattr(resp, "text") else str(resp)
                return {"method": "transcript", "text": transcript[:500] + "...",
                        "summary": summary}
            except Exception as e:
                # Fail gracioso: si LLM agotado, devolver transcript bruto
                short_err = str(e)[:120]
                preview = transcript[:1500]
                return {"method": "transcript_raw", "text": transcript,
                        "summary": (f"[LLM no disponible: {short_err}]\n\n"
                                     f"--- TRANSCRIPT (primeros 1500 chars) ---\n"
                                     f"{preview}")}

    # Fallback: video visual
    result = analyze_via_gemini_video(url, prompt)
    return {"method": "gemini_video", "text": result, "summary": result}


if __name__ == "__main__":
    # Smoke test - usa un video real corto con subs
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Resume este video en 3 puntos."
    r = watch_youtube(url, prompt)
    print(f"\n=== METHOD: {r['method']} ===")
    print(f"\n=== SUMMARY ===\n{r['summary']}\n")
