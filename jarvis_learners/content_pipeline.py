"""content_pipeline.py — Pipeline E2E para creación de contenido.

Orquesta: idea → research → script → assets → edición → upload.

Flujo típico:
  1. Recibe brief: "video TikTok sobre como hacer drop shipping con shopify"
  2. research → busca en YT/web + sintetiza con Claude
  3. script_writer → genera guion 60s con hook, body, CTA
  4. asset_gatherer → descarga clips/imágenes Pexels/Pixabay
  5. video_editor → corta + concat + subtítulos via ffmpeg
  6. thumbnail_gen → imagen vertical con texto
  7. upload → YouTube/TikTok con título+desc+tags optimizados SEO

Cada step es independiente — si falla, retry o skip.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROXY = "http://127.0.0.1:8088"
WORKSPACE = ROOT / "data" / "content_workspace"


def log(msg: str):
    print(f"[content_pipeline {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def call_claude(system: str, user: str, max_tokens: int = 2000, timeout: int = 180) -> str | None:
    try:
        r = requests.post(
            f"{PROXY}/v1/messages",
            json={
                "model": "claude-sonnet-4-6",
                "system": system,
                "messages": [{"role": "user", "content": user}],
                "max_tokens": max_tokens,
            },
            timeout=timeout,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    except Exception as e:
        log(f"claude proxy fallo: {e}")
        return None


# ============================================================================
# STEP 1: RESEARCH
# ============================================================================
def research_topic(topic: str, depth: int = 3) -> dict:
    """Busca info del tema en YT (titulos populares) + Wikipedia + sintetiza."""
    log(f"researching: {topic}")
    findings = {"topic": topic, "sources": [], "synthesis": ""}

    # YouTube search (sin descarga, solo metadata)
    try:
        proc = subprocess.run(
            ["yt-dlp", "--no-warnings", "--quiet",
             "--print-json", "--no-download",
             "--match-filter", "duration<600",
             f"ytsearch{depth*2}:{topic}"],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
        for line in proc.stdout.splitlines()[:depth*2]:
            try:
                v = json.loads(line)
                findings["sources"].append({
                    "type": "youtube",
                    "title": v.get("title"),
                    "views": v.get("view_count"),
                    "description": (v.get("description") or "")[:300],
                })
            except Exception:
                continue
    except Exception:
        pass

    # Síntesis con Claude
    sys_prompt = """Eres researcher. Recibes el tema + lista de videos populares sobre eso.
Sintetiza en JSON: {key_points: [...], audience_pain: "...", proven_angles: [...]}"""
    user = f"TEMA: {topic}\n\nFUENTES:\n{json.dumps(findings['sources'][:5], ensure_ascii=False, indent=2)[:3000]}"
    text = call_claude(sys_prompt, user)
    if text:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            try:
                findings["synthesis"] = json.loads(m.group(0))
            except Exception:
                pass
    return findings


# ============================================================================
# STEP 2: SCRIPT
# ============================================================================
def write_script(topic: str, research: dict, duration_s: int = 60,
                 format_hint: str = "tiktok_viral") -> dict:
    """Genera script estructurado: hook, body, CTA."""
    log(f"writing script for: {topic} ({format_hint}, {duration_s}s)")
    sys_prompt = f"""Eres script writer especialista en {format_hint}. Genera un guion de
{duration_s} segundos.

Output JSON estricto:
{{
  "hook": "primeros 3s — frase que detenga scroll",
  "body": [
    {{"timestamp_s": 3, "text": "...", "visual_cue": "qué se debe ver"}},
    ...
  ],
  "cta": "ultima frase",
  "voice_style": "energico/calmado/dramatico",
  "music_mood": "epic/chill/upbeat",
  "title_options": ["3 títulos para A/B test"],
  "hashtags": ["#tag1", ...]
}}"""
    user = f"TEMA: {topic}\n\nRESEARCH:\n{json.dumps(research, ensure_ascii=False)[:3000]}"
    text = call_claude(sys_prompt, user, max_tokens=2500)
    if text:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {}


# ============================================================================
# STEP 3: VOICE OVER (TTS)
# ============================================================================
def generate_voiceover(script: dict, out_dir: Path, voice: str = "es-MX-DaliaNeural") -> Path | None:
    """Genera audio TTS por cada segmento del body."""
    try:
        from backend.skills.voice_io import speak
    except ImportError:
        return None
    log("generando voiceover...")
    audio_files = []
    full_text = script.get("hook", "")
    for seg in script.get("body", []):
        full_text += " " + seg.get("text", "")
    full_text += " " + script.get("cta", "")
    out = out_dir / "voiceover.mp3"
    audio = speak(full_text, voice=voice, play=False)
    if audio:
        import shutil
        shutil.copy(audio, out)
        return out
    return None


# ============================================================================
# STEP 4: PIPELINE COMPLETO
# ============================================================================
def create_content(topic: str, duration_s: int = 60,
                   format_hint: str = "tiktok_viral") -> dict:
    """Pipeline E2E. Devuelve dict con todos los artifacts."""
    log(f"=== CONTENT PIPELINE: {topic} ===")
    job_id = uuid.uuid4().hex[:8]
    job_dir = WORKSPACE / f"job_{job_id}_{re.sub(r'[^a-z0-9]+', '_', topic.lower())[:30]}"
    job_dir.mkdir(parents=True, exist_ok=True)
    log(f"workspace: {job_dir}")

    result = {"job_id": job_id, "topic": topic, "workspace": str(job_dir)}

    # 1. Research
    research = research_topic(topic, depth=3)
    (job_dir / "1_research.json").write_text(json.dumps(research, ensure_ascii=False, indent=2), encoding="utf-8")
    result["research"] = research.get("synthesis", {})

    # 2. Script
    script = write_script(topic, research, duration_s, format_hint)
    (job_dir / "2_script.json").write_text(json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8")
    result["script"] = script

    # 3. Voiceover (TTS)
    audio = generate_voiceover(script, job_dir)
    result["voiceover"] = str(audio) if audio else None

    # 4. (TODO) Video editing — requiere assets (clips Pexels) + ffmpeg compose
    # 5. (TODO) Thumbnail generation
    # 6. (TODO) Upload via youtube_api connector

    log(f"DONE: {job_dir}")
    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python content_pipeline.py 'topic'")
        sys.exit(0)
    topic = " ".join(sys.argv[1:])
    result = create_content(topic)
    print(json.dumps({k: v for k, v in result.items() if k != "research"}, ensure_ascii=False, indent=2)[:3000])
