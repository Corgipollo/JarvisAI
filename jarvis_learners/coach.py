"""coach.py — IA coach que enseña a Jarvis en orden lógico, validando.

Filosofía Voyager + curriculum graduado:
  - El coach es OTRA IA (Claude) que mira el estado actual de Jarvis
  - Decide la SIGUIENTE mejor skill a aprender (no random, no list estática)
  - La encola en gaps.json
  - Después de que el learner la aprende, valida con skill_executor
  - Si executability < 60%, manda re-learn con prompt más específico
  - Avanza al siguiente nivel cuando current está dominado

Tick: cada 15min toma decisión coach. NO bloquea el self_improvement loop —
trabajan en paralelo.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

GAPS_FILE = ROOT / "data" / "gaps.json"
SKILLS_DIR = ROOT / "data" / "skill_library"
COACH_LOG = ROOT / "data" / "coach_decisions.jsonl"
PROXY_URL = "http://127.0.0.1:8088"


def log(msg: str):
    print(f"[coach {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


COACH_PROMPT = """Eres el COACH/TUTOR de Jarvis, un agente AI que está aprendiendo a usar
una PC Windows como una secretaria experta. Tu trabajo: decidir la PRÓXIMA
mejor skill que debe aprender, basándote en lo que ya sabe.

Filosofia curricular (de basico a complejo):
  NIVEL 1: control básico mouse, teclado, ventanas, archivos
  NIVEL 2: apps comunes (browser, explorer, calc, notepad)
  NIVEL 3: apps productividad (Excel, Word, Outlook, Teams)
  NIVEL 4: creación de contenido (CapCut, Photoshop, Canva)
  NIVEL 5: workflows multi-app (research + edit + publish)
  NIVEL 6: tareas autónomas complejas (administrar canal YT, gestión emails)

Reglas:
1. NUNCA repetir skill que ya esta dominada (executability_pct >= 80)
2. Si una skill está APRENDIDA pero baja executability (<60), pide RE-LEARN
   con query más específico
3. Priorizar SKILLS PUENTE: una habilidad nueva que UNE otras ya aprendidas
4. NO saltar niveles: completar L1 antes de L2, etc.
5. Una decisión por turno

Recibes:
  - lista de skills aprendidas con executability_pct
  - gaps pendientes en queue
  - métricas del sistema

Devuelves JSON:
{
  "decision": "new_skill" | "relearn" | "wait",
  "query": "como X paso a paso tutorial",
  "level": 1-6,
  "reasoning": "por qué esta skill ahora, qué desbloquea",
  "expected_outcome": "qué debería poder hacer Jarvis después"
}

SOLO el JSON. Sin markdown ni explicación fuera.
"""


def get_jarvis_state() -> dict:
    """Snapshot del estado actual: skills + métricas."""
    skills = []
    if SKILLS_DIR.exists():
        idx = SKILLS_DIR / "_index.jsonl"
        if idx.exists():
            for line in idx.read_text(encoding="utf-8").splitlines():
                try:
                    skills.append(json.loads(line))
                except Exception:
                    continue
    pending_gaps = []
    if GAPS_FILE.exists():
        try:
            pending_gaps = json.loads(GAPS_FILE.read_text(encoding="utf-8")).get("queries", [])
        except Exception:
            pass
    return {
        "skills_learned": skills,
        "skill_count": len(skills),
        "pending_gaps": pending_gaps,
        "pending_count": len(pending_gaps),
    }


def evaluate_skill_executability(skill_id: str) -> float:
    """Llama a skill_executor.analyze_skill para % ejecutable."""
    try:
        from jarvis_learners import skill_executor
        skill = skill_executor.load_skill(skill_id)
        if not skill:
            return 0.0
        analysis = skill_executor.analyze_skill(skill)
        return analysis["executability_pct"]
    except Exception:
        return 0.0


def call_coach(state: dict) -> dict:
    """Pregunta a Claude (via proxy) qué hacer next."""
    # Enriquecer skills con executability
    skills_summary = []
    for s in state["skills_learned"][-20:]:  # últimas 20
        exec_pct = evaluate_skill_executability(s["id"])
        skills_summary.append({
            "name": s["name"], "domain": s.get("domain"),
            "executability_pct": exec_pct,
            "confidence": s.get("confidence", 0),
        })

    user_prompt = json.dumps({
        "skills_learned": skills_summary,
        "skill_count": state["skill_count"],
        "pending_gaps": state["pending_gaps"][:10],
        "ts": datetime.now().isoformat(),
    }, ensure_ascii=False, indent=2)

    try:
        r = requests.post(
            f"{PROXY_URL}/v1/messages",
            json={
                "model": "claude-sonnet-4-6",
                "system": COACH_PROMPT,
                "messages": [{"role": "user", "content": user_prompt}],
                "max_tokens": 1500,
            },
            timeout=180,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"]
    except Exception as e:
        log(f"coach proxy fallo: {e}")
        return {"decision": "wait", "reasoning": f"proxy_error: {e}"}

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        log(f"coach respuesta sin JSON: {text[:200]}")
        return {"decision": "wait", "reasoning": "no_json"}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        log(f"coach JSON inválido: {e}")
        return {"decision": "wait", "reasoning": "json_invalid"}


def append_gap(query: str):
    """Agrega query al gaps.json (al principio = más prioritario)."""
    GAPS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if GAPS_FILE.exists():
        data = json.loads(GAPS_FILE.read_text(encoding="utf-8"))
    else:
        data = {"queries": []}
    if query not in data["queries"]:
        data["queries"].insert(0, query)
        GAPS_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def log_decision(decision: dict, state: dict):
    COACH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COACH_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now().isoformat(),
            "decision": decision,
            "state_snapshot": {
                "skill_count": state["skill_count"],
                "pending_count": state["pending_count"],
            },
        }, ensure_ascii=False) + "\n")


async def coach_loop(tick_minutes: int = 15):
    log(f"=== COACH ACTIVO (tick {tick_minutes}min) ===")
    while True:
        state = get_jarvis_state()
        log(f"estado: {state['skill_count']} skills, {state['pending_count']} pending")
        decision = call_coach(state)
        log(f"decision: {decision.get('decision')} — {decision.get('reasoning', '')[:100]}")

        if decision.get("decision") == "new_skill" and decision.get("query"):
            append_gap(decision["query"])
            log(f"+gap encolado: {decision['query']}")
        elif decision.get("decision") == "relearn" and decision.get("query"):
            append_gap(f"{decision['query']} mejor tutorial profundo")
            log(f"+re-learn encolado: {decision['query']}")

        log_decision(decision, state)
        await asyncio.sleep(tick_minutes * 60)


if __name__ == "__main__":
    try:
        asyncio.run(coach_loop(tick_minutes=15))
    except KeyboardInterrupt:
        log("coach detenido")
