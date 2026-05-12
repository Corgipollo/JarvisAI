"""skill_learner.py — Voyager-style: aprende skills viendo YouTube.

Pipeline:
  1. Recibe gap: "no se editar video en CapCut basico"
  2. yt-dlp busca tutoriales relevantes (top 3-5)
  3. faster-whisper transcribe audio
  4. ffmpeg saca frames cada 5s
  5. Tesseract OCR en frames clave
  6. Claude (proxy local gratis) sintetiza skill estructurada
  7. Guarda en skill library (jsonl + opcional faiss embedding)

Output skill format (jsonl):
{
  "id": "edit_video_capcut_basic",
  "name": "editar video en CapCut basico",
  "domain": "video_editing",
  "steps": [
    {"action": "open_app", "target": "CapCut", "expect": "main window"},
    {"action": "click", "target": "Importar boton", "expect": "file picker"},
    ...
  ],
  "sources": ["https://youtube.com/watch?v=...", ...],
  "learned_at": "2026-05-11T...",
  "confidence": 0.85
}
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

# Force UTF-8 stdout/stderr on Windows (titles with non-ASCII chars crash cp1252)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "data" / "skill_library"
TUTORIAL_CACHE = ROOT / "data" / "tutorial_cache"
PROXY_URL = "http://127.0.0.1:8088"


def log(msg: str):
    print(f"[skill_learner {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ============================================================================
# Step 1-2: Search YouTube + download top videos
# ============================================================================
def search_and_download(query: str, max_videos: int = 3,
                        max_duration_s: int = 900) -> list[dict]:
    """Busca tutoriales en YouTube y descarga top N (audio + metadata)."""
    TUTORIAL_CACHE.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", query)[:40]
    cache_dir = TUTORIAL_CACHE / slug
    cache_dir.mkdir(parents=True, exist_ok=True)

    log(f"buscando tutoriales: '{query}' (top {max_videos})")
    search_url = f"ytsearch{max_videos}:{query} tutorial"

    cmd = [
        sys.executable, "-m", "yt_dlp", "--no-warnings", "--quiet",
        "--print-json", "--no-download",
        "--match-filter", f"duration<{max_duration_s}",
        "-f", "best[height<=480]/best",
        search_url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=60, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        log("timeout en busqueda")
        return []

    videos = []
    for line in proc.stdout.splitlines():
        try:
            v = json.loads(line)
            videos.append({
                "id": v.get("id"),
                "title": v.get("title"),
                "duration": v.get("duration"),
                "url": v.get("webpage_url") or f"https://youtu.be/{v.get('id')}",
            })
        except Exception:
            continue

    log(f"  {len(videos)} candidatos. Descargando audio+video...")

    downloaded = []
    for v in videos[:max_videos]:
        out_tpl = cache_dir / f"{v['id']}.%(ext)s"
        cmd = [
            sys.executable, "-m", "yt_dlp", "--no-warnings", "--quiet",
            "-f", "best[height<=360]/best",
            "-o", str(out_tpl),
            v["url"],
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True,
                           timeout=180, encoding="utf-8", errors="replace")
            files = list(cache_dir.glob(f"{v['id']}.*"))
            video_file = next((f for f in files if f.suffix in (".mp4", ".webm", ".mkv")), None)
            if video_file:
                v["local_path"] = str(video_file)
                downloaded.append(v)
                log(f"  OK: {v['title'][:50]} ({video_file.stat().st_size/1e6:.0f} MB)")
        except subprocess.TimeoutExpired:
            log(f"  timeout en {v['id']}")
            continue
    return downloaded


# ============================================================================
# Step 3-4: Transcribe + extract frames
# ============================================================================
def transcribe_video(video_path: str) -> str:
    """faster-whisper transcribe audio."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        log("faster-whisper no instalado, skip transcript")
        return ""
    model = WhisperModel("base", device="cpu", compute_type="int8")
    segs, info = model.transcribe(
        video_path, language=None,  # auto-detect
        vad_filter=True, condition_on_previous_text=False,
    )
    text_chunks = []
    for s in segs:
        text_chunks.append(s.text.strip())
    return " ".join(text_chunks)


def extract_all_frames_with_ocr(video_path: str, fps: float = 1.0,
                                 dedupe_window: int = 3) -> list[str]:
    """ffmpeg saca TODOS los frames a 1 fps + OCR cada uno + deduplica por similitud.

    Aprende viendo el video COMPLETO, no muestreando. Despues deduplica texto
    consecutivo (si 3 frames seguidos tienen el mismo OCR, solo el primero queda).
    """
    out_dir = Path(video_path).parent / f"{Path(video_path).stem}_frames"
    out_dir.mkdir(exist_ok=True)

    # Extract all frames at given fps
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", video_path,
        "-vf", f"fps={fps}",
        "-q:v", "5",
        str(out_dir / "frame_%05d.jpg"),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=300)
    except Exception as e:
        log(f"ffmpeg fallo: {e}")
        return []

    frames = sorted(out_dir.glob("frame_*.jpg"))
    log(f"  {len(frames)} frames extraidos, haciendo OCR...")

    try:
        import pytesseract
        from PIL import Image
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    except ImportError:
        return [f"[FRAME {f.stem}]" for f in frames]

    raw_ocr = []
    for i, f in enumerate(frames):
        try:
            txt = pytesseract.image_to_string(Image.open(f), lang="spa+eng").strip()
            # Compact whitespace
            txt = " ".join(txt.split())[:200]
            sec = int(i / fps)
            raw_ocr.append({"sec": sec, "frame": f.stem, "text": txt})
        except Exception:
            raw_ocr.append({"sec": int(i/fps), "frame": f.stem, "text": ""})

    # Dedupe: si frame N == frame N-1 (mismo texto), skip
    deduped = []
    last_text = None
    last_kept_sec = -100
    for entry in raw_ocr:
        if entry["text"] != last_text or entry["sec"] - last_kept_sec >= 10:
            deduped.append(entry)
            last_text = entry["text"]
            last_kept_sec = entry["sec"]

    log(f"  OCR: {len(raw_ocr)} frames → {len(deduped)} unicos (deduplicado)")

    # Format final
    return [f"[{e['sec']//60:02d}:{e['sec']%60:02d}] {e['text']}" for e in deduped if e['text']]


# Backward-compat alias
def extract_key_frames(video_path: str, n_frames: int = 8) -> list[str]:
    return extract_all_frames_with_ocr(video_path, fps=1.0)


# ============================================================================
# Step 5-6: Claude (via proxy) sintetiza skill estructurada
# ============================================================================
SYNTHESIZE_PROMPT = """Eres un sintetizador de skills para un AGENTE AUTOMATICO de PC
(no un humano lector). Recibes transcript + frames OCR de tutoriales Y debes
extraer principios + pasos ejecutables, NO copiar literal.

Reglas críticas:
1. ABSTRAE el principio operativo, no transcribas. Si 3 tutoriales hacen lo
   mismo de 3 formas, elige la mejor o documenta las variantes.
2. Pasos deben ser EJECUTABLES por agente (pyautogui+OCR+UIA tree). Usa
   acciones atomicas: "presionar Ctrl+S", "click en boton 'Exportar'",
   "escribir 'hola' en campo X", NO descripciones humanas vagas.
3. Cuando hay multiples metodos (ej. 5 formas de tomar screenshot), incluyelas
   todas en methods[]. El agente elegira segun contexto.
4. Identifica VERIFICACION post-accion: "deberia aparecer X notificacion",
   "ventana debe cerrarse", etc. Es como el agente sabe si funciono.
5. common_errors: pitfalls reales del tutorial, no genericos.

Formato (SOLO JSON, sin markdown):
{
  "name": "nombre operacional conciso",
  "domain": "video_editing/system/office/web_browsing/coding/multimedia/...",
  "intent": "que problema resuelve esta skill en 1 linea",
  "preconditions": ["estados que deben existir antes"],
  "inputs": ["que recibe la skill cuando se invoca"],
  "outputs": ["que produce al terminar"],
  "methods": [
    {
      "name": "metodo principal o alternativo",
      "when_to_use": "cuando este metodo es mejor que otros",
      "steps": [
        {"step": 1, "action": "accion atomica ejecutable", "verify": "como confirmo que funciono"},
        ...
      ]
    }
  ],
  "common_errors": ["pitfall real con su workaround"],
  "confidence": 0.0-1.0,
  "notes": "patrones generalizables que pueden aplicar a otras skills similares"
}

Maximo 3 methods. Maximo 10 steps por method. Solo JSON.
"""


def synthesize_skill(query: str, transcript: str, frames_ocr: list[str],
                     sources: list[str]) -> dict | None:
    """Llama a Claude (vía proxy) para sintetizar skill estructurada."""
    # Limit frames OCR to top 60 most informative (skip very short)
    informative_frames = [f for f in frames_ocr if len(f) > 30][:60]

    user_prompt = (
        f"OBJETIVO: aprender '{query}'\n\n"
        f"TRANSCRIPT (mezcla de {len(sources)} tutoriales):\n"
        f"{transcript[:3500]}\n\n"
        f"FRAMES OCR (timeline visual):\n"
        + "\n".join(informative_frames)
        + "\n\nDevuelve SOLO el JSON de la skill."
    )

    try:
        r = requests.post(
            f"{PROXY_URL}/v1/messages",
            json={
                "model": "claude-sonnet-4-6",
                "system": SYNTHESIZE_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
                "max_tokens": 4096,
            },
            timeout=300,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"]
    except Exception as e:
        log(f"proxy fallo: {e}")
        return None

    # Extract JSON
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        log(f"no JSON en respuesta: {text[:200]}")
        return None
    try:
        skill = json.loads(m.group(0))
        skill["sources"] = sources
        skill["learned_at"] = datetime.now().isoformat()
        skill["id"] = f"{skill.get('name','').lower().replace(' ','_')[:40]}_{uuid.uuid4().hex[:8]}"
        return skill
    except json.JSONDecodeError as e:
        log(f"JSON inválido: {e}")
        return None


# ============================================================================
# Step 7: Save to skill library
# ============================================================================
def save_skill(skill: dict) -> Path:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    f = SKILLS_DIR / f"{skill['id']}.json"
    f.write_text(json.dumps(skill, ensure_ascii=False, indent=2), encoding="utf-8")
    # Also append to index
    idx = SKILLS_DIR / "_index.jsonl"
    with idx.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps({
            "id": skill["id"], "name": skill["name"],
            "domain": skill.get("domain"), "confidence": skill.get("confidence"),
            "learned_at": skill["learned_at"], "file": f.name,
        }, ensure_ascii=False) + "\n")
    return f


# ============================================================================
# Main pipeline
# ============================================================================
def learn_skill(query: str, max_videos: int = 6) -> dict | None:
    """Pipeline E2E: query → skill aprendida en biblioteca."""
    log(f"=== APRENDIENDO: '{query}' ===")
    videos = search_and_download(query, max_videos=max_videos)
    if not videos:
        log("no encontré tutoriales")
        return None

    transcripts = []
    all_frames = []
    sources = []
    for v in videos:
        log(f"procesando: {v['title'][:60]}")
        try:
            t = transcribe_video(v["local_path"])
            transcripts.append(f"--- {v['title']} ---\n{t}")
            all_frames.extend(extract_key_frames(v["local_path"], n_frames=5))
            sources.append(v["url"])
        except Exception as e:
            log(f"fallo procesar {v['id']}: {e}")
            continue

    combined_transcript = "\n\n".join(transcripts)
    skill = synthesize_skill(query, combined_transcript, all_frames, sources)
    if skill:
        f = save_skill(skill)
        log(f"OK skill guardada: {f.name}")
        return skill
    return None


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "abrir notepad y escribir texto en Windows"
    skill = learn_skill(query, max_videos=2)
    if skill:
        print(json.dumps({"id": skill["id"], "name": skill["name"], "steps": len(skill.get("steps", []))}, indent=2))
