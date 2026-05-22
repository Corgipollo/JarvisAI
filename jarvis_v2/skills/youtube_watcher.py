"""youtube_watcher.py - Modo VISION TOTAL (default) + transcript fast-path opcional.

Por orden de Emmanuel 2026-05-21: por default usa Gemini Files API con video
nativo (analiza UI, clicks, audio completo). El transcript-api solo se usa si
el caller pasa fast=True explicitamente.

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

GEMINI_MODEL_DEFAULT = "models/gemini-2.5-flash"


def _extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([0-9A-Za-z_-]{11})",
        r"^([0-9A-Za-z_-]{11})$",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def get_transcript(url: str,
                    lang_preference: tuple[str, ...] = ("es", "en")) -> str | None:
    """Fast-path: solo se invoca si caller pasa fast=True a watch_youtube."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return None
    vid = _extract_video_id(url)
    if not vid:
        return None
    api = YouTubeTranscriptApi()
    try:
        for lang in lang_preference:
            try:
                snippets = api.fetch(vid, languages=[lang])
                return " ".join(s.text for s in snippets)
            except Exception:
                continue
        snippets = api.fetch(vid)
        return " ".join(s.text for s in snippets)
    except Exception as e:
        print(f"[yt] transcript fail {vid}: {e}")
        return None


def analyze_via_gemini_video(url: str, prompt: str,
                              model_name: str = GEMINI_MODEL_DEFAULT) -> dict:
    """MODO VISION TOTAL: yt-dlp -> Gemini Files API -> analisis frame+audio.

    Returns: {ok, method, summary, video_size_mb, gemini_state}
    """
    import google.generativeai as genai
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return {"ok": False, "method": "gemini_video",
                "summary": "ERROR: GEMINI_API_KEY no seteado"}
    genai.configure(api_key=api_key)

    vid = _extract_video_id(url) or f"video_{int(time.time())}"
    video_path = WORKSPACE / f"{vid}.mp4"
    if video_path.exists():
        video_path.unlink()

    print(f"[yt] descargando worst quality {url} -> {video_path}")
    cmd = (f'yt-dlp -f "worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]/worst" '
           f'--merge-output-format mp4 -o "{video_path}" {url}')
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       timeout=600)
    if r.returncode != 0:
        return {"ok": False, "method": "gemini_video",
                "summary": f"ERROR yt-dlp rc={r.returncode}: {r.stderr[-400:]}"}

    if not video_path.exists():
        return {"ok": False, "method": "gemini_video",
                "summary": "ERROR: video no se descargo"}

    size_mb = video_path.stat().st_size / (1024 * 1024)
    print(f"[yt] video={size_mb:.1f} MB - subiendo a Gemini Files API")

    try:
        video_file = genai.upload_file(path=str(video_path))
        while video_file.state.name == "PROCESSING":
            print(".", end="", flush=True)
            time.sleep(3)
            video_file = genai.get_file(video_file.name)
        if video_file.state.name == "FAILED":
            return {"ok": False, "method": "gemini_video",
                    "summary": "ERROR: Gemini Files API procesamiento FAILED",
                    "video_size_mb": size_mb,
                    "gemini_state": video_file.state.name}

        print(f"\n[yt] analizando con {model_name}")
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(
            [video_file,
             f"{prompt}\n\nIMPORTANTE: analiza TODO - cada frame visual, "
             f"cada UI, cada click visible, y el audio completo. "
             f"Devuelve pasos concretos con timestamps si los hay."],
            generation_config={"max_output_tokens": 4000, "temperature": 0.3},
        )
        summary = response.text if hasattr(response, "text") else str(response)
    except Exception as e:
        try:
            video_path.unlink()
        except Exception:
            pass
        return {"ok": False, "method": "gemini_video",
                "summary": f"ERROR Gemini analisis: {e}",
                "video_size_mb": size_mb}

    # Limpieza
    try:
        genai.delete_file(video_file.name)
    except Exception:
        pass
    try:
        video_path.unlink()
    except Exception:
        pass

    return {"ok": True, "method": "gemini_video", "summary": summary,
            "video_size_mb": round(size_mb, 1)}


def watch_youtube(url: str,
                   prompt: str = "Analiza este tutorial. Lista TODO lo que ocurre: que pantalla/app aparece, que botones se clickean, y que dice el audio. Devuelve pasos numerados con timestamps si los hay.",
                   fast: bool = False) -> dict:
    """Entry point.

    Args:
        fast: si True, intenta transcript-api primero (rapido, sin descarga).
              si False (DEFAULT), va directo a vision total via Gemini Files.

    Returns: dict con method, summary, text (si fast=True).
    """
    if fast:
        transcript = get_transcript(url)
        if transcript and len(transcript) > 100:
            return {"ok": True, "method": "transcript",
                    "text": transcript,
                    "summary": transcript[:2000]}

    # DEFAULT: vision total
    return analyze_via_gemini_video(url, prompt)


if __name__ == "__main__":
    import sys, json
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.youtube.com/watch?v=jNQXAC9IVRw"
    prompt = sys.argv[2] if len(sys.argv) > 2 else "Resume en 1 oracion."
    r = watch_youtube(url, prompt)
    out = Path(__file__).resolve().parents[2] / "data" / "yt_last_result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"=== {r.get('method')} ===")
    print(f"saved to {out}")
