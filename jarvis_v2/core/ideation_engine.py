"""ideation_engine.py - Generador de objetivos autonomos. ZERO HUMAN.

Flow:
  1. Pick topic seed (random from list o Mem pending topics)
  2. deep_research(topic) -> trends
  3. github_explorer(related tools)
  4. LLM ideate: micro-business o campaign
  5. Validate via cost_oracle (must fit budget)
  6. Emit JarvisState with objective + estimated_total
  7. Dispatch to run_objective()

REGLAS DE AUTONOMIA:
  - NUNCA escalate_human. Si CFO rechaza -> registra fallo en Mem, PIVOTA.
  - Si idea cuesta > $5 (max_per_call) -> rompe en sub-actions
  - Si presupuesto agotado -> hibernate hasta reconcile vea ROI > 1.2x
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# Seeds para "aburrimiento". Cada uno puede explorar dominio entero.
SEED_TOPICS = [
    "micro SaaS B2B con bajo costo de adquisicion 2026",
    "bot de Discord trending categorias rentables 2026",
    "nichos de dropshipping low-competition Mexico 2026",
    "ideas de print-on-demand virales TikTok 2026",
    "APIs de IA con freemium tier que se pueden envolver y revender",
    "open-source tools poco usadas con alta utilidad para automation",
    "tendencias de inversion crypto cuantitativa retail",
    "AI agents para small business workflows",
    "automatizacion email outreach B2B con scraping legal",
    "marketing organico via Reddit por nicho",
]

IDEATION_LOG = ROOT / "data" / "ideation_log.jsonl"
STATUS_BOARD = ROOT / "data" / "status_board.json"


def log_ideation(entry: dict):
    IDEATION_LOG.parent.mkdir(parents=True, exist_ok=True)
    with IDEATION_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def pick_topic() -> str:
    """Toma topic: 70% seed random, 30% del Mem (cosas mencionadas pero no exploradas)."""
    try:
        if random.random() < 0.3:
            from jarvis_v2.memory.memory_manager import recall_lessons
            lessons = recall_lessons("topic_known", top_k=10,
                                      tag_filter=["topic_known"])
            if lessons:
                return f"profundizar en: {lessons[0]['insight'][:100]}"
    except Exception:
        pass
    return random.choice(SEED_TOPICS)


def ideate_business(research_summary: str, tools_found: list,
                     budget_available_usd: float) -> dict:
    """LLM genera plan de micro-negocio. Output debe ser JSON estructurado."""
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_json
    except ImportError:
        return {"error": "claude_unavailable"}

    tools_summary = "\n".join(
        f"- {t.get('repo', '?')}: {t.get('reason', '')[:80]}"
        for t in (tools_found or [])[:5]
    )

    prompt = (
        f"BUDGET DISPONIBLE: ${budget_available_usd:.2f} USD (limite duro)\n\n"
        f"INVESTIGACION DE TENDENCIAS:\n{research_summary[:3000]}\n\n"
        f"HERRAMIENTAS OSS DISPONIBLES:\n{tools_summary}\n\n"
        "Disena un MICRO-NEGOCIO o CAMPANA ejecutable AHORA. "
        "Debe ser:\n"
        "- Iniciable con menos de $5 USD\n"
        "- Automatizable end-to-end (sin GUI manual)\n"
        "- Medible (ROI cuantificable en 30 dias)\n\n"
        "Responde JSON:\n"
        '{\n'
        '  "objective": "descripcion 1-linea del proyecto",\n'
        '  "rationale": "por que es rentable, 2-3 lineas",\n'
        '  "initial_steps": ["paso1", "paso2", ...],\n'
        '  "estimated_initial_cost_usd": float,\n'
        '  "estimated_monthly_cost_usd": float,\n'
        '  "expected_roi_30d": float (ej: 1.5 = 50% ROI),\n'
        '  "stack": ["herramientas y APIs"],\n'
        '  "risk_factors": ["lista"],\n'
        '  "confidence": 0-1\n'
        '}'
    )
    out = ask_claude_json(prompt, model="claude-opus-4-7", max_tokens=2000)
    return out or {"error": "no_ideation_output"}


def get_remaining_budget() -> float:
    """Cuanto queda del budget de $100."""
    try:
        from jarvis_v2.cfo.cost_oracle import ledger_snapshot
        snap = ledger_snapshot()
        return max(0, 100.00 - snap.get("lifetime_spent_usd", 0))
    except Exception:
        return 100.00


def update_status_board(payload: dict):
    """Append-only summary: el voice_daemon puede leerlo para reportar."""
    STATUS_BOARD.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if STATUS_BOARD.exists():
        try:
            existing = json.loads(STATUS_BOARD.read_text(encoding="utf-8"))
        except Exception:
            pass
    history = existing.get("history", [])
    history.append(payload)
    history = history[-50:]  # cap
    data = {
        "last_update": datetime.utcnow().isoformat(),
        "latest": payload,
        "history": history,
        "budget_remaining_usd": get_remaining_budget(),
    }
    STATUS_BOARD.write_text(json.dumps(data, ensure_ascii=False, indent=2,
                                       default=str), encoding="utf-8")


def autonomous_iteration() -> dict:
    """Una iteracion completa del Ideador. Lanza un grafo si encuentra idea viable."""
    cycle_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    print(f"\n[ideation #{cycle_id}] arrancando ciclo autonomo", flush=True)

    budget = get_remaining_budget()
    if budget < 0.50:
        update_status_board({
            "cycle_id": cycle_id, "status": "HIBERNATE",
            "reason": "budget_exhausted",
            "budget_remaining": budget,
        })
        print(f"[ideation] budget exhausted (${budget:.2f}), hibernando", flush=True)
        return {"status": "hibernate", "budget": budget}

    # 1. Pick topic
    topic = pick_topic()
    print(f"[ideation] topic: {topic[:80]}", flush=True)

    # 2. Deep research
    try:
        from jarvis_v2.skills.deep_research import deep_research, summarize
        research = deep_research(topic, max_sources=3)
        summary = summarize(research, focus="oportunidades viables con menos $5")
    except Exception as e:
        print(f"[ideation] research failed: {e}", flush=True)
        summary = ""
        research = {"sources": []}

    # 3. GitHub explorer (paralelo conceptual, pero sync aqui)
    tools = []
    try:
        from jarvis_v2.skills.github_explorer import discover_and_install
        gh_result = discover_and_install(topic, max_evaluate=3,
                                          auto_install_if_useful=False)
        tools = gh_result.get("candidates", [])
    except Exception as e:
        print(f"[ideation] gh explorer failed: {e}", flush=True)

    # 4. Ideate
    idea = ideate_business(summary, tools, budget_available_usd=budget)
    if "error" in idea:
        update_status_board({
            "cycle_id": cycle_id, "status": "IDEATION_FAILED",
            "reason": idea.get("error"),
            "topic": topic,
        })
        return {"status": "ideation_failed", "reason": idea.get("error")}

    # 5. Validate budget
    cost = float(idea.get("estimated_initial_cost_usd", 999))
    roi = float(idea.get("expected_roi_30d", 0))
    confidence = float(idea.get("confidence", 0))

    log_ideation({"cycle_id": cycle_id, "topic": topic, "idea": idea,
                  "tools_found": len(tools), "summary_chars": len(summary)})

    if cost > 5.0:
        # No puede pasar CFO en una sola accion -> pivotear a sub-fases
        idea["objective"] = (
            f"FASE 1 (de un plan mayor): {idea['objective']}. "
            f"Costo inicial fase 1: maximo $5"
        )
        idea["estimated_initial_cost_usd"] = min(5.0, cost)
        print(f"[ideation] pivot: cost ${cost} > $5, restringiendo a fase 1", flush=True)

    if roi < 1.2 or confidence < 0.4:
        # Pivot: registra fallo y prueba otra
        update_status_board({
            "cycle_id": cycle_id, "status": "PIVOT",
            "reason": f"roi_too_low or confidence_low (roi={roi}, conf={confidence})",
            "discarded_idea": idea.get("objective", ""),
            "topic": topic,
        })
        try:
            from jarvis_v2.memory.memory_manager import save_lesson
            save_lesson(
                insight=(f"Idea pivoteada: '{idea.get('objective', '')[:100]}' "
                         f"roi={roi} conf={confidence}. No vale gastar."),
                tags=["pivot", "low_roi"],
                severity="low",
            )
        except Exception:
            pass
        return {"status": "pivot", "reason": "low_roi_or_confidence"}

    # 6. Dispatch al grafo principal
    update_status_board({
        "cycle_id": cycle_id, "status": "DISPATCHED",
        "objective": idea["objective"],
        "estimated_cost": cost,
        "expected_roi": roi,
        "topic": topic,
    })

    try:
        from jarvis_v2.core.graph import run_objective
        result = run_objective(
            idea["objective"],
            thread_id=f"ideation_{cycle_id}",
        )
        update_status_board({
            "cycle_id": cycle_id, "status": "EXECUTED",
            "result_keys": list(result.keys())[:10] if result else [],
        })
        return {"status": "executed", "objective": idea["objective"],
                "cycle_id": cycle_id}
    except Exception as e:
        update_status_board({
            "cycle_id": cycle_id, "status": "EXECUTION_ERROR",
            "error": str(e)[:200],
        })
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    print(json.dumps(autonomous_iteration(), indent=2, default=str))
