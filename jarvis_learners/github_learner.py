"""github_learner.py — Aprende skills leyendo repositorios de GitHub.

Pipeline:
  1. Recibe gap: "como hacer X"
  2. gh search repos + topics relacionados
  3. Clona top N repos (depth 1, files only)
  4. Lee README + extrae snippets de codigo relevantes
  5. Claude (proxy) sintetiza skill ejecutable
  6. Guarda en skill library (mismo formato que skill_learner)

Complementa skill_learner.py: YouTube enseña UI, GitHub enseña código.
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

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "data" / "skill_library"
REPO_CACHE = ROOT / "data" / "github_cache"
PROXY_URL = "http://127.0.0.1:8088"


def log(msg: str):
    print(f"[github_learner {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def search_repos(query: str, limit: int = 5) -> list[dict]:
    """Usa gh CLI para buscar repos."""
    log(f"buscando repos: '{query}' (top {limit})")
    try:
        proc = subprocess.run(
            ["gh", "search", "repos", query, "--limit", str(limit), "--json",
             "fullName,description,url,stargazersCount,language"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            log(f"gh fallo: {proc.stderr[:200]}")
            return []
        return json.loads(proc.stdout)
    except Exception as e:
        log(f"search error: {e}")
        return []


def fetch_readme(full_name: str) -> str:
    """Obtiene README del repo via gh api."""
    try:
        proc = subprocess.run(
            ["gh", "api", f"repos/{full_name}/readme", "--jq", ".content"],
            capture_output=True, text=True, timeout=20,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            return ""
        import base64
        return base64.b64decode(proc.stdout.strip()).decode("utf-8", errors="replace")[:10000]
    except Exception:
        return ""


def extract_code_snippets(readme: str, max_snippets: int = 5) -> list[str]:
    """Extrae bloques de codigo del README."""
    snippets = re.findall(r"```[\w]*\n(.*?)\n```", readme, flags=re.DOTALL)
    return [s.strip()[:1000] for s in snippets[:max_snippets]]


SYNTHESIZE_PROMPT = """Eres sintetizador de conocimiento desde repositorios. Recibes:
- query del user
- N repositorios con README y snippets de codigo

Tu trabajo: extraer una SKILL ESTRUCTURADA en JSON que un agente PC pueda usar.
Si hay codigo, prioriza pasos programaticos. Si es UI, pasos manuales.

Formato output (SOLO JSON):
{
  "name": "nombre conciso",
  "domain": "categoria",
  "preconditions": ["lo que debe existir antes"],
  "steps": [
    {"step": 1, "action": "...", "details": "...", "code": "snippet opcional", "expect": "..."},
    ...
  ],
  "common_errors": [...],
  "confidence": 0.7,
  "notes": "..."
}

Maximo 12 steps. Solo JSON.
"""


def synthesize_skill(query: str, repos_data: list[dict]) -> dict | None:
    if not repos_data:
        return None
    body_parts = []
    for r in repos_data:
        body_parts.append(
            f"### {r['full_name']} ({r['stars']}⭐ {r.get('language','?')})\n"
            f"Descripción: {r.get('description','')}\n"
            f"README (truncado):\n{r['readme'][:3000]}\n\n"
            f"Snippets código:\n" + "\n---\n".join(r.get("snippets", [])[:3])
        )

    user_prompt = (
        f"OBJETIVO: '{query}'\n\n"
        f"REPOS encontrados:\n" + "\n\n".join(body_parts)
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
            timeout=120,
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
        skill = json.loads(m.group(0))
        skill["sources"] = [r["url"] for r in repos_data]
        skill["learned_at"] = datetime.now().isoformat()
        skill["source_type"] = "github"
        skill["id"] = f"{skill.get('name','').lower().replace(' ','_')[:40]}_{uuid.uuid4().hex[:8]}"
        return skill
    except json.JSONDecodeError as e:
        log(f"JSON inválido: {e}")
        return None


def save_skill(skill: dict) -> Path:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    f = SKILLS_DIR / f"{skill['id']}.json"
    f.write_text(json.dumps(skill, ensure_ascii=False, indent=2), encoding="utf-8")
    idx = SKILLS_DIR / "_index.jsonl"
    with idx.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps({
            "id": skill["id"], "name": skill["name"],
            "domain": skill.get("domain"), "confidence": skill.get("confidence"),
            "learned_at": skill["learned_at"], "file": f.name,
            "source_type": "github",
        }, ensure_ascii=False) + "\n")
    return f


def learn_from_github(query: str, max_repos: int = 4) -> dict | None:
    log(f"=== APRENDIENDO de GitHub: '{query}' ===")
    repos = search_repos(query, limit=max_repos)
    if not repos:
        log("sin repos relevantes")
        return None

    enriched = []
    for r in repos[:max_repos]:
        fname = r.get("fullName") or r.get("name", "")
        if not fname:
            continue
        log(f"  fetch {fname} ({r.get('stargazersCount',0)}⭐)")
        readme = fetch_readme(fname)
        if not readme:
            continue
        enriched.append({
            "full_name": fname,
            "url": r.get("url", ""),
            "description": r.get("description", ""),
            "language": r.get("language", ""),
            "stars": r.get("stargazersCount", 0),
            "readme": readme,
            "snippets": extract_code_snippets(readme),
        })

    skill = synthesize_skill(query, enriched)
    if skill:
        f = save_skill(skill)
        log(f"OK guardado: {f.name}")
        return skill
    return None


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "windows automation pyautogui drag and drop"
    skill = learn_from_github(query)
    if skill:
        print(json.dumps({"id": skill["id"], "name": skill["name"], "steps": len(skill.get("steps", []))}, indent=2))
