"""role_learner.py — Aprende ROLES PROFESIONALES completos.

NO aprende skills atomicas (eso lo hace skill_learner). Aprende EL ROL:
qué hace un contador, qué apps usa, sus workflows típicos, entregables.

Pipeline:
  1. Recibe rol: "contador" | "secretaria" | "editor de video" | "community manager"
  2. yt-dlp busca "día en la vida de X" + "qué hace un X" + "herramientas X"
  3. faster-whisper transcribe
  4. Claude sintetiza ROLE PROFILE estructurado:
       - daily_tasks
       - tools_used (apps, software, sitios web)
       - workflows típicos
       - deliverables
       - skills_required (que despues skill_learner aprende)
  5. Guarda en role_library
  6. Coach lee role_profile y genera curriculum CONTEXTUAL al rol

Output role profile (json):
{
  "role": "contador",
  "daily_tasks": ["...", ...],
  "tools": [
    {"name": "Excel", "use": "balance, hojas", "priority": "alta"},
    {"name": "SAT app", "use": "facturacion mensual"},
    ...
  ],
  "workflows": [
    {"name": "cierre mensual", "steps": [...], "frequency": "monthly"},
    ...
  ],
  "deliverables": ["balance mensual PDF", "declaración SAT", ...],
  "skills_required": [
    "como hacer balance en Excel",
    "como descargar XML del SAT",
    ...
  ]
}
"""
from __future__ import annotations

import json
import re
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

ROLES_DIR = ROOT / "data" / "role_library"
PROXY_URL = "http://127.0.0.1:8088"


def log(msg: str):
    print(f"[role_learner {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


ROLE_SYNTHESIZE_PROMPT = """Eres un investigador laboral. Recibes transcripts de varios videos
sobre un rol profesional ('día en la vida de X', 'qué hace un X', 'herramientas X').

Tu trabajo: extraer el PERFIL COMPLETO DEL ROL como JSON estructurado.

Output (SOLO JSON):
{
  "role": "nombre del rol",
  "domain": "industria (oficina/creativo/tech/...)",
  "summary": "1 linea de qué hace en general",
  "daily_tasks": [
    {"task": "...", "frequency": "diaria/semanal/mensual", "time_pct": 0-100}
  ],
  "tools": [
    {"name": "app/sitio", "use": "para qué lo usa", "priority": "alta/media/baja"}
  ],
  "workflows": [
    {
      "name": "nombre del workflow",
      "trigger": "cuando se ejecuta",
      "frequency": "diaria/mensual/anual",
      "steps_high_level": ["paso 1", "paso 2", "..."]
    }
  ],
  "deliverables": ["entregable 1 (formato)", "entregable 2"],
  "skills_required": [
    "skill atomica que jarvis debe aprender (query buscable en YT)",
    "..."
  ],
  "common_questions_asked_to_them": ["pregunta tipica 1", "..."],
  "confidence": 0.0-1.0
}

Reglas:
- Maximo 10 daily_tasks
- Maximo 8 tools
- Maximo 5 workflows
- skills_required son queries que puedo pasar a skill_learner.learn_skill()
- Solo JSON.
"""


def search_role_content(role: str, max_videos: int = 5) -> list[dict]:
    """Busca videos de YT sobre el rol."""
    import subprocess
    queries = [
        f"que hace un {role} dia normal",
        f"dia en la vida de un {role}",
        f"herramientas software {role}",
    ]
    all_videos = []
    cache_dir = ROOT / "data" / "role_content_cache" / re.sub(r"[^a-z0-9]+", "_", role.lower())
    cache_dir.mkdir(parents=True, exist_ok=True)

    for q in queries:
        log(f"  buscando: {q}")
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "yt_dlp", "--no-warnings", "--quiet",
                 "--print-json", "--no-download",
                 "--match-filter", "duration<900",
                 f"ytsearch{max_videos // len(queries) + 1}:{q}"],
                capture_output=True, text=True, timeout=60,
                encoding="utf-8", errors="replace",
            )
            for line in proc.stdout.splitlines():
                try:
                    v = json.loads(line)
                    all_videos.append({
                        "id": v.get("id"),
                        "title": v.get("title"),
                        "url": v.get("webpage_url") or f"https://youtu.be/{v.get('id')}",
                        "duration": v.get("duration"),
                    })
                except Exception:
                    continue
        except Exception as e:
            log(f"  error: {e}")
            continue

    # Dedupe
    seen = set()
    deduped = []
    for v in all_videos:
        if v["id"] not in seen:
            seen.add(v["id"])
            deduped.append(v)

    deduped = deduped[:max_videos]
    log(f"  {len(deduped)} videos únicos. Descargando...")

    downloaded = []
    for v in deduped:
        out_tpl = cache_dir / f"{v['id']}.%(ext)s"
        try:
            import subprocess as sp
            sp.run(
                [sys.executable, "-m", "yt_dlp", "--no-warnings", "--quiet",
                 "-f", "best[height<=240]/best",
                 "-o", str(out_tpl),
                 v["url"]],
                capture_output=True, text=True, timeout=180,
                encoding="utf-8", errors="replace",
            )
            files = list(cache_dir.glob(f"{v['id']}.*"))
            video = next((f for f in files if f.suffix in (".mp4", ".webm", ".mkv")), None)
            if video:
                v["local_path"] = str(video)
                downloaded.append(v)
        except Exception:
            continue

    return downloaded


def transcribe_videos(videos: list[dict]) -> str:
    """Concatena transcripciones de todos los videos."""
    from faster_whisper import WhisperModel
    log("  cargando whisper base...")
    model = WhisperModel("base", device="cpu", compute_type="int8")
    all_text = []
    for v in videos:
        log(f"  transcribiendo {v['title'][:50]}")
        try:
            segs, info = model.transcribe(
                v["local_path"], language=None,
                vad_filter=True, condition_on_previous_text=False,
            )
            chunks = []
            for s in segs:
                chunks.append(s.text.strip())
            all_text.append(f"=== {v['title']} ===\n{' '.join(chunks)}")
        except Exception as e:
            log(f"  transcribe fallo: {e}")
            continue
    return "\n\n".join(all_text)


def synthesize_role(role: str, transcript: str) -> dict | None:
    user_prompt = (
        f"ROL A INVESTIGAR: {role}\n\n"
        f"TRANSCRIPCIONES (mezcla de varios videos sobre el rol, truncado):\n"
        f"{transcript[:4500]}\n\n"
        f"Devuelve SOLO el JSON del role profile."
    )
    try:
        r = requests.post(
            f"{PROXY_URL}/v1/messages",
            json={
                "model": "claude-sonnet-4-6",
                "system": ROLE_SYNTHESIZE_PROMPT,
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

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        log("no JSON en respuesta")
        return None
    try:
        profile = json.loads(m.group(0))
        profile["learned_at"] = datetime.now().isoformat()
        profile["id"] = f"{role.lower().replace(' ', '_')}_{uuid.uuid4().hex[:8]}"
        return profile
    except json.JSONDecodeError:
        log("JSON inválido")
        return None


def save_role(profile: dict) -> Path:
    ROLES_DIR.mkdir(parents=True, exist_ok=True)
    f = ROLES_DIR / f"{profile['id']}.json"
    f.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    idx = ROLES_DIR / "_index.jsonl"
    with idx.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps({
            "id": profile["id"], "role": profile["role"],
            "domain": profile.get("domain"),
            "skills_required_count": len(profile.get("skills_required", [])),
            "tools_count": len(profile.get("tools", [])),
            "learned_at": profile["learned_at"], "file": f.name,
        }, ensure_ascii=False) + "\n")
    return f


def feed_skills_to_curriculum(profile: dict) -> int:
    """Toma skills_required del rol y las encola en gaps.json para el learner."""
    gaps_file = ROOT / "data" / "gaps.json"
    if gaps_file.exists():
        data = json.loads(gaps_file.read_text(encoding="utf-8"))
    else:
        data = {"queries": []}
    added = 0
    for skill_query in profile.get("skills_required", []):
        if skill_query and skill_query not in data["queries"]:
            data["queries"].append(skill_query)
            added += 1
    gaps_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return added


def learn_role(role: str, max_videos: int = 5) -> dict | None:
    log(f"=== APRENDIENDO ROL: '{role}' ===")
    videos = search_role_content(role, max_videos)
    if not videos:
        log("sin videos del rol")
        return None
    transcript = transcribe_videos(videos)
    if not transcript:
        log("transcripts vacios")
        return None
    profile = synthesize_role(role, transcript)
    if profile:
        f = save_role(profile)
        n_added = feed_skills_to_curriculum(profile)
        log(f"OK rol guardado: {f.name}")
        log(f"OK {n_added} skills nuevas encoladas en curriculum")
        return profile
    return None


if __name__ == "__main__":
    role = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "secretaria"
    profile = learn_role(role, max_videos=4)
    if profile:
        print(json.dumps({
            "role": profile["role"],
            "summary": profile.get("summary"),
            "daily_tasks": len(profile.get("daily_tasks", [])),
            "tools": len(profile.get("tools", [])),
            "workflows": len(profile.get("workflows", [])),
            "skills_to_learn": len(profile.get("skills_required", [])),
        }, indent=2, ensure_ascii=False))
