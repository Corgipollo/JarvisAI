"""self_improvement.py — Loop autonomo de auto-mejora de Jarvis.

Filosofia Voyager: la IA detecta sus gaps y los llena SOLA, sin que Emmanuel
le diga.

Cada ciclo:
  1. Lee estadisticas: tasks fallidas, skills missing, areas debiles
  2. Identifica TOP 3 gaps prioritarios
  3. Decide tool: YouTube (skill_learner) o GitHub (github_learner) por tipo de gap
  4. Ejecuta learn → guarda skill nueva
  5. Marca el gap como "addressed"
  6. Reporta progreso

Corre en loop continuo (cada 10 min por default) cuando Jarvis esta IDLE.

Gaps detection:
  - tasks_failed.jsonl: tareas que fallaron en trainer
  - skills_requested.jsonl: skills que se pidieron pero no existen en library
  - explicit: archivo gaps.json con queries manuales que el user agrego
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_learners import skill_learner, github_learner       # noqa: E402

DATA_DIR = ROOT / "data"
GAPS_FILE = DATA_DIR / "gaps.json"
ADDRESSED_FILE = DATA_DIR / "gaps_addressed.jsonl"
SKILLS_DIR = DATA_DIR / "skill_library"


def log(msg: str):
    print(f"[self_improve {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_gaps() -> list[dict]:
    """Combina gaps de varias fuentes."""
    gaps = []

    # 1. Gaps explicitos del user
    if GAPS_FILE.exists():
        try:
            data = json.loads(GAPS_FILE.read_text(encoding="utf-8"))
            for g in data.get("queries", []):
                gaps.append({"query": g, "source": "user_explicit", "priority": 9})
        except Exception:
            pass

    # 2. Tasks fallidas del trainer (errors_log)
    errors_log = DATA_DIR / "jarvis_errors.jsonl"
    if errors_log.exists():
        recent_errors = []
        for line in errors_log.read_text(encoding="utf-8").splitlines()[-200:]:
            try:
                recent_errors.append(json.loads(line))
            except Exception:
                continue
        # Cuenta tasks fallidas repetidamente
        task_fail_counts = Counter(e.get("task", "") for e in recent_errors)
        for task, count in task_fail_counts.most_common(5):
            if count >= 2 and task:
                gaps.append({
                    "query": f"como hacer {task} en Windows",
                    "source": "trainer_errors",
                    "priority": 7,
                    "fail_count": count,
                })

    # 3. Skills requested pero ausentes
    requested = DATA_DIR / "skills_requested.jsonl"
    if requested.exists():
        for line in requested.read_text(encoding="utf-8").splitlines()[-50:]:
            try:
                req = json.loads(line)
                gaps.append({
                    "query": req.get("query", ""),
                    "source": "requested",
                    "priority": 8,
                })
            except Exception:
                continue

    return gaps


def load_addressed() -> set:
    if not ADDRESSED_FILE.exists():
        return set()
    queries = set()
    for line in ADDRESSED_FILE.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
            queries.add(d.get("query", ""))
        except Exception:
            continue
    return queries


def mark_addressed(gap: dict, skill_id: str, source_type: str):
    ADDRESSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ADDRESSED_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "query": gap["query"],
            "source": gap["source"],
            "skill_id": skill_id,
            "learn_source": source_type,
            "addressed_at": datetime.now().isoformat(),
        }, ensure_ascii=False) + "\n")


def pick_learner(query: str) -> str:
    """Decide YouTube vs GitHub basado en heuristicas simples."""
    q = query.lower()
    code_keywords = ["python", "javascript", "api", "github", "library",
                     "script", "framework", "sdk", "cli", "package"]
    if any(k in q for k in code_keywords):
        return "github"
    return "youtube"


async def process_gap(gap: dict) -> dict | None:
    """Procesa 1 gap: learner apropiado → skill nueva."""
    learner_type = pick_learner(gap["query"])
    log(f"[{learner_type}] {gap['query']}")
    try:
        if learner_type == "github":
            skill = github_learner.learn_from_github(gap["query"])
        else:
            skill = skill_learner.learn_skill(gap["query"], max_videos=6)
        if skill:
            mark_addressed(gap, skill["id"], learner_type)
            return skill
    except Exception as e:
        log(f"learner fallo: {e}")
    return None


def stats() -> dict:
    skills_count = 0
    if SKILLS_DIR.exists():
        skills_count = len(list(SKILLS_DIR.glob("*.json")))
    addressed = load_addressed()
    return {
        "skills_in_library": skills_count,
        "gaps_addressed_total": len(addressed),
        "last_check": datetime.now().isoformat(),
    }


def generate_new_gaps_from_coach() -> list[str]:
    """Pide al coach (Claude) que sugiera NUEVAS skills a aprender
    basado en lo que ya tiene en skill_library. Cierra el loop autonomo:
    cuando se acaban los gaps, el coach genera mas. Nunca termina.
    """
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_json, ping_proxy
    except ImportError:
        log("  coach: jarvis_brain no disponible, no puedo generar gaps")
        return []
    if not ping_proxy():
        log("  coach: proxy no responde, skip")
        return []

    # Lista de skills actuales
    existing = []
    if SKILLS_DIR.exists():
        for f in SKILLS_DIR.glob("*.json"):
            if f.name.startswith("_"):
                continue
            try:
                existing.append(json.loads(f.read_text(encoding="utf-8")).get("name", f.stem))
            except Exception:
                continue

    prompt = (
        f"Eres el COACH de Jarvis (asistente Windows en VM). "
        f"Jarvis ya aprendio estas {len(existing)} skills:\n"
        + "\n".join(f"- {s}" for s in existing[:30])
        + f"\n\nSugiere 10 NUEVAS skills que Jarvis deberia aprender ahora "
        f"para ser un secretario/asistente personal mas util. Que sean POPULARES en YouTube "
        f"(asegura que yt-dlp encuentre tutoriales). Mezclar: apps comunes (Excel, Photoshop), "
        f"comandos Windows, productividad, comunicacion, automatizacion. "
        f"Cada query debe ser una busqueda corta tipo 'tutorial X' o 'como hacer Y'. "
        f"Responde JSON estricto:\n"
        f'{{"queries": ["tutorial X", "como Y", "Z basics"...]}}'
    )
    res = ask_claude_json(prompt, schema_hint='{"queries": [...]}')
    if res and "queries" in res and isinstance(res["queries"], list):
        log(f"  coach genero {len(res['queries'])} nuevos gaps")
        return [str(q) for q in res["queries"] if q]
    return []


def append_gaps_to_file(new_queries: list[str]):
    """Agrega queries nuevas a gaps.json sin perder las existentes."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = []
    if GAPS_FILE.exists():
        try:
            existing = json.loads(GAPS_FILE.read_text(encoding="utf-8")).get("queries", [])
        except Exception:
            existing = []
    # Dedup
    seen = set(existing)
    for q in new_queries:
        if q not in seen:
            existing.append(q)
            seen.add(q)
    GAPS_FILE.write_text(
        json.dumps({"queries": existing, "priority": "high",
                    "last_coach_refill": datetime.now().isoformat()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def improvement_loop(tick_minutes: int = 10, max_gaps_per_tick: int = 1):
    """Loop autonomo PERPETUO. Cuando gaps se acaba, el coach genera mas."""
    log(f"=== AUTO-MEJORA INICIADA (tick {tick_minutes}min, modo perpetuo) ===")
    log(f"Stats: {stats()}")

    empty_ticks = 0

    while True:
        gaps = load_gaps()
        addressed = load_addressed()
        pending = [g for g in gaps if g["query"] not in addressed]
        pending.sort(key=lambda g: -g.get("priority", 0))

        if not pending:
            empty_ticks += 1
            # Despues de 2 ticks sin gaps, pedir al coach mas (cada 20min)
            if empty_ticks >= 2:
                log("sin gaps pendientes 20min, consultando coach para generar nuevos...")
                new_queries = generate_new_gaps_from_coach()
                if new_queries:
                    append_gaps_to_file(new_queries)
                    log(f"  +{len(new_queries)} nuevos gaps agregados a gaps.json")
                    empty_ticks = 0
                else:
                    log("  coach no devolvio queries, esperando otro tick")
            else:
                log(f"sin gaps pendientes, durmiendo {tick_minutes}min (empty_ticks={empty_ticks})")
        else:
            empty_ticks = 0
            log(f"{len(pending)} gaps pendientes, procesando top {max_gaps_per_tick}")
            for gap in pending[:max_gaps_per_tick]:
                skill = await process_gap(gap)
                if skill:
                    log(f"  +skill: {skill['name']} ({len(skill.get('steps',[]))} steps)")
                else:
                    log(f"  no pude aprender: {gap['query']}")
                    # Marcar como addressed para no quedarse colgado en queries imposibles
                    mark_addressed(gap, skill_id="(failed)", source_type="failed")

        await asyncio.sleep(tick_minutes * 60)


def request_skill(query: str, priority: int = 5):
    """API publica: agrega un gap explicito que se procesara en el proximo tick."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    requested = DATA_DIR / "skills_requested.jsonl"
    with requested.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "query": query, "priority": priority,
            "requested_at": datetime.now().isoformat(),
        }, ensure_ascii=False) + "\n")
    log(f"+gap requested: {query}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(json.dumps(stats(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "request":
        request_skill(" ".join(sys.argv[2:]))
    else:
        try:
            asyncio.run(improvement_loop(tick_minutes=10, max_gaps_per_tick=1))
        except KeyboardInterrupt:
            log("loop detenido")
