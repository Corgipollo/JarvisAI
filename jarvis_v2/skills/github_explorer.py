"""github_explorer.py - Descubre, evalua, clona e instala herramientas OSS.

Flow:
  1. search_trending(query) -> top repos via GitHub API
  2. fetch_readme(repo) -> readme + descripcion
  3. evaluate_with_llm(readme, goal) -> {useful: bool, reason, install_cmd}
  4. clone_and_install(repo) -> en data/jarvis_labs/tools/<name>/

Sin token GitHub funciona (60 req/h rate limit). Con env GITHUB_TOKEN sube a 5000/h.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LABS_DIR = Path("C:/Users/Emmanuel/Documents/Jarvis_Labs/tools")
GH_TOKEN = os.environ.get("GITHUB_TOKEN", "")

UA = "Jarvis-v2 (deep-research)"


def _headers():
    h = {"User-Agent": UA, "Accept": "application/vnd.github+json"}
    if GH_TOKEN:
        h["Authorization"] = f"Bearer {GH_TOKEN}"
    return h


def search_trending(query: str, language: str | None = None,
                    min_stars: int = 100, max_results: int = 10) -> list[dict]:
    """Busca repos via GitHub search API. Sorted by stars desc."""
    qparts = [query, f"stars:>={min_stars}"]
    if language:
        qparts.append(f"language:{language}")
    q = " ".join(qparts)
    try:
        r = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": q, "sort": "stars", "order": "desc",
                    "per_page": max_results},
            headers=_headers(), timeout=20,
        )
        if r.status_code != 200:
            return []
        items = r.json().get("items", [])
        return [{
            "full_name": it["full_name"],
            "url": it["html_url"],
            "description": (it.get("description") or "")[:300],
            "stars": it.get("stargazers_count", 0),
            "forks": it.get("forks_count", 0),
            "language": it.get("language", ""),
            "topics": it.get("topics", []),
            "clone_url": it["clone_url"],
            "updated_at": it.get("updated_at", ""),
        } for it in items]
    except Exception as e:
        print(f"[gh] search error: {e}", flush=True)
        return []


def fetch_readme(full_name: str) -> str | None:
    """Descarga README.md del repo."""
    try:
        r = requests.get(
            f"https://api.github.com/repos/{full_name}/readme",
            headers=_headers(), timeout=20,
        )
        if r.status_code != 200:
            return None
        data = r.json()
        import base64
        content = data.get("content", "")
        if data.get("encoding") == "base64":
            return base64.b64decode(content).decode("utf-8", errors="replace")
        return content
    except Exception as e:
        print(f"[gh] readme fetch fail {full_name}: {e}", flush=True)
        return None


def evaluate_repo(repo: dict, goal: str) -> dict:
    """Pregunta a Claude si el repo sirve para el goal. Devuelve veredicto."""
    readme = fetch_readme(repo["full_name"]) or ""
    if not readme:
        return {"useful": False, "reason": "no_readme"}

    try:
        from jarvis_bridge.jarvis_brain import ask_claude_json
        prompt = (
            f"GOAL: {goal}\n\n"
            f"REPO: {repo['full_name']} ({repo['stars']} stars)\n"
            f"Description: {repo['description']}\n\n"
            f"README (truncado):\n{readme[:5000]}\n\n"
            "Evalua si este repo es UTIL para el goal. Responde JSON:\n"
            '{"useful": bool, "reason": "1-2 lineas", '
            '"install_strategy": "pip|npm|cargo|cmake|none", '
            '"main_entry_command": "comando para usarlo", '
            '"risk_level": "low|medium|high"}'
        )
        verdict = ask_claude_json(prompt, model="claude-sonnet-4-6",
                                   max_tokens=400)
        if not verdict:
            return {"useful": False, "reason": "claude_no_response"}
        return verdict
    except Exception as e:
        return {"useful": False, "reason": f"eval_error: {e}"}


def clone_repo(repo: dict) -> Path | None:
    """Clona repo en LABS_DIR/<name>/. Idempotent."""
    LABS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = repo["full_name"].replace("/", "__")
    target = LABS_DIR / safe_name
    if target.exists():
        print(f"[gh] {safe_name} ya existe, skip clone", flush=True)
        return target
    try:
        r = subprocess.run(
            ["git", "clone", "--depth", "1", repo["clone_url"], str(target)],
            capture_output=True, text=True, timeout=180,
        )
        if r.returncode != 0:
            print(f"[gh] clone failed: {r.stderr[-300:]}", flush=True)
            return None
        return target
    except Exception as e:
        print(f"[gh] clone exception: {e}", flush=True)
        return None


def install_deps(repo_dir: Path, strategy: str = "pip") -> dict:
    """Instala dependencias del repo segun strategy."""
    result = {"ok": False, "strategy": strategy, "out": ""}
    try:
        if strategy == "pip":
            # Find requirements.txt, pyproject.toml, setup.py
            req = repo_dir / "requirements.txt"
            pyproject = repo_dir / "pyproject.toml"
            if req.exists():
                cmd = [sys.executable, "-m", "pip", "install", "-r", str(req)]
            elif pyproject.exists():
                cmd = [sys.executable, "-m", "pip", "install", "-e", str(repo_dir)]
            else:
                return {**result, "out": "no requirements found"}
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            result["ok"] = r.returncode == 0
            result["out"] = (r.stdout + r.stderr)[-500:]
        elif strategy == "npm":
            pkg = repo_dir / "package.json"
            if not pkg.exists():
                return {**result, "out": "no package.json"}
            r = subprocess.run(["npm", "install"], cwd=str(repo_dir),
                               capture_output=True, text=True, timeout=300, shell=True)
            result["ok"] = r.returncode == 0
            result["out"] = (r.stdout + r.stderr)[-500:]
        else:
            result["out"] = f"strategy {strategy} not implemented"
    except Exception as e:
        result["out"] = str(e)
    return result


def discover_and_install(goal: str, query: str | None = None,
                         language: str = "python",
                         max_evaluate: int = 5,
                         auto_install_if_useful: bool = False) -> dict:
    """Pipeline completo: search -> evaluate -> (optional) install."""
    query = query or goal
    print(f"[gh] discovering for goal='{goal[:60]}'", flush=True)
    repos = search_trending(query, language=language, min_stars=100,
                             max_results=max_evaluate)
    print(f"[gh] found {len(repos)} candidates", flush=True)
    evaluated = []
    for repo in repos:
        v = evaluate_repo(repo, goal)
        v["repo"] = repo["full_name"]
        v["url"] = repo["url"]
        v["stars"] = repo["stars"]
        evaluated.append(v)
        if v.get("useful") and auto_install_if_useful and v.get("risk_level") == "low":
            cloned = clone_repo(repo)
            if cloned:
                inst = install_deps(cloned, v.get("install_strategy", "pip"))
                v["cloned_at"] = str(cloned)
                v["install_result"] = inst
                # Log a Mem para no reinstalar
                try:
                    from jarvis_v2.memory.memory_manager import save_lesson
                    save_lesson(
                        insight=(f"Instale {repo['full_name']} para {goal[:80]}. "
                                 f"Install: {inst['ok']}. Entry: "
                                 f"{v.get('main_entry_command', '')}"),
                        tags=["github_install", repo["full_name"].split("/")[1]],
                        severity="low",
                    )
                except Exception:
                    pass

    # Filter usefuls
    usefuls = [e for e in evaluated if e.get("useful")]
    return {
        "goal": goal, "ts": datetime.utcnow().isoformat(),
        "evaluated_count": len(evaluated),
        "useful_count": len(usefuls),
        "candidates": usefuls,
        "all_evaluated": evaluated,
    }


if __name__ == "__main__":
    goal = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "bot de Discord que rastrea precios de criptomonedas"
    )
    result = discover_and_install(goal, auto_install_if_useful=False)
    print(f"\n=== Useful repos for '{goal[:60]}' ===")
    for c in result["candidates"]:
        print(f"  - {c['repo']} ({c['stars']}*) — {c.get('reason', '')[:100]}")
    print(f"\nTotal evaluated: {result['evaluated_count']}, useful: {result['useful_count']}")
