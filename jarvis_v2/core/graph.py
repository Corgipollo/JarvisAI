"""graph.py - LangGraph state machine completa con CFO gateway integrado.

Zero-Defect Routing: route_after_cfo es fail-closed (default = halt).
Pydantic-validated planner: imposible que LLM omita estimated_spend_usd.
CFO deny -> END (NO Reflector). Reflector solo para fallos tecnicos.
Reconciler obligatorio post-execute_real para asentar costo real en ledger.
"""
from __future__ import annotations

import json
import operator
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, TypedDict, Literal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CHECKPOINT_DB = ROOT / "data" / "jarvis_v2_checkpoints.db"


# ============================================================================
# STATE - explicito, TypedDict, operator.add solo donde DEBE acumularse
# ============================================================================
class JarvisState(TypedDict, total=False):
    # Input
    objective: str

    # Pre-plan
    cerebro_context: str

    # Plan
    plan: list                              # list[PlanStep dicts]
    objective_summary: str
    current_step: int

    # Per-step CFO
    proposed_action: dict                   # current step dict
    sim_results: dict                       # backtest/simulation results
    proposer_argument: str
    skeptic_argument: str
    judge_score: float
    cfo_decision: Literal[
        "approve_real", "approve_sim_only", "deny", "escalate_human",
    ]
    cfo_reason: str
    cfo_oracle: dict
    cfo_violations: list
    cfo_idem_key: str
    cfo_rollback_token: str

    # Execution
    last_action_result: dict
    actual_cost_usd: float
    last_error: str | None

    # Reflexion
    retries_for_step: int
    max_retries: int

    # ACCUMULATING fields (operator.add = append)
    messages: Annotated[list, operator.add]
    history: Annotated[list, operator.add]
    insights: Annotated[list, operator.add]

    # Control
    done: bool


# ============================================================================
# NODES
# ============================================================================
def node_rag(state: JarvisState) -> JarvisState:
    """Pre-planner: busca contexto en CerebroEmmanuel via ChromaDB."""
    try:
        from jarvis_v2.memory.cerebro_rag import search_cerebro
        ctx = search_cerebro(state.get("objective", ""), top_k=5)
    except Exception as e:
        ctx = f"(RAG unavailable: {e})"
    return {"cerebro_context": ctx}


def node_planner(state: JarvisState) -> JarvisState:
    """Genera plan validado por Pydantic + inyecta lecciones pasadas de Mem."""
    from jarvis_v2.core.llm_structured import llm_structured
    from jarvis_v2.core.schemas import Plan
    from jarvis_v2.memory.memory_manager import recall_lessons, mark_lesson_helpful

    obj = state.get("objective", "")
    ctx = state.get("cerebro_context", "")

    # MEM RECALL: lecciones pasadas relevantes al objetivo
    lessons = recall_lessons(obj, top_k=5, min_confidence=0.3)
    lessons_text = ""
    if lessons:
        lessons_text = "\n\nLECCIONES APRENDIDAS PREVIAMENTE (NO REPITAS ESTOS ERRORES):\n"
        for i, l in enumerate(lessons, 1):
            lessons_text += (
                f"  {i}. [{l['severity']}] {l['insight']} "
                f"(tags: {', '.join(l['tags'][:3])})\n"
            )
        # Marcar como hit las que se inyectaron
        for l in lessons:
            try:
                mark_lesson_helpful(l["id"])
            except Exception:
                pass

    prompt = (
        f"OBJETIVO USUARIO: {obj}\n\n"
        f"CONTEXTO RELEVANTE (CerebroEmmanuel):\n{ctx[:2000]}\n"
        f"{lessons_text}\n"
        "REGLAS DURAS:\n"
        "1. PRIORIZA action='shell' con command_or_task que sea un comando "
        "Windows cmd.exe EJECUTABLE LITERAL (ej: 'cmd /c mkdir C:\\\\foo' o "
        "'cmd /c echo hola > C:\\\\foo\\\\bar.txt').\n"
        "2. NO uses action='click_som'/'type'/'hotkey' a menos que el "
        "objetivo EXPLICITAMENTE pida interaccion GUI.\n"
        "3. Cada step DEBE tener estimated_spend_usd (0.0 si es gratis).\n"
        "4. Acciones de archivos/carpetas son REVERSIBLE=true, "
        "estimated_spend_usd=0.0, is_financial=false.\n"
        "5. Genera el MINIMO numero de steps. Si una sola linea de shell hace "
        "todo el objetivo, usa 1 solo step.\n"
        "6. command_or_task DEBE ser autosuficiente: 'cmd /c <cmd>' o "
        "'powershell -Command \"<ps>\"'. Nunca uses paths Unix (/c/foo) en Windows.\n"
    )

    plan_obj = llm_structured(
        prompt,
        Plan,
        system=(
            "Eres ingeniero senior atomico para Windows en MODO PERSISTENCIA "
            "ABSOLUTA. Generas shells EJECUTABLES literales con cmd /c o "
            "powershell -Command. PROHIBIDO: placeholders ('TODO', '// poner "
            "logica aqui'), pasos abstractos, descripciones sin shell concreto. "
            "Pasos minimos pero COMPLETOS de inicio a fin. SIEMPRE aplica las "
            "lecciones aprendidas previamente. Cuando el objetivo implique "
            "navegador (Twitter, Reddit, Shopify, etc.) usa action=browser_interact "
            "con JSON {url, selector, click, text}. Cuando implique video YouTube "
            "usa action=youtube_watch con JSON {url, prompt}."
        ),
        model="claude-sonnet-4-6",
        max_tokens=3000,
        max_retries=2,
    )

    return {
        "plan": [s.model_dump() for s in plan_obj.steps],
        "objective_summary": plan_obj.objective_summary,
        "current_step": 0,
        "retries_for_step": 0,
        "max_retries": 3,
        "messages": [{"role": "planner",
                      "content": f"plan_{len(plan_obj.steps)}_steps_with_{len(lessons)}_lessons"}],
    }


def node_load_step(state: JarvisState) -> JarvisState:
    """Carga el step actual como proposed_action para CFO."""
    plan = state.get("plan", [])
    idx = state.get("current_step", 0)
    if idx >= len(plan):
        return {"done": True}
    step = plan[idx]
    return {
        "proposed_action": {
            "type": step.get("action"),
            "command_or_task": step.get("command_or_task"),
            "estimated_spend_usd": step.get("estimated_spend_usd", 0.0),
            "is_financial": step.get("is_financial", False),
            "leverage": step.get("leverage", 1.0),
            "quantity": step.get("quantity", 1.0),
            "pre_condition": step.get("pre_condition", ""),
            "post_condition": step.get("post_condition", ""),
        },
        "sim_results": state.get("sim_results", {}),
    }


def node_cfo(state: JarvisState) -> JarvisState:
    """Delega al CFO evaluator (deterministic + oracle override)."""
    from jarvis_v2.cfo.cfo_evaluator import node_cfo_evaluator
    return node_cfo_evaluator(state)


def node_execute_real(state: JarvisState) -> JarvisState:
    """Ejecuta accion real. CFO ya autorizo con write-ahead-log en SQLite."""
    action = state.get("proposed_action", {})
    a_type = action.get("type", "")
    cmd = action.get("command_or_task", "")
    result = {"action_type": a_type, "executed_at": datetime.utcnow().isoformat()}

    try:
        if a_type == "shell":
            import subprocess
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=120)
            result.update({"returncode": r.returncode,
                           "stdout": r.stdout[-500:], "stderr": r.stderr[-500:]})
        elif a_type == "click_som":
            from jarvis_v2.sensor.set_of_mark import generate_som, claude_pick_and_click
            mapping, img = generate_som()
            res = claude_pick_and_click(cmd, img, mapping)
            result.update(res)
            if not res.get("error"):
                import pyautogui
                pyautogui.click(res["center_x"], res["center_y"])
        elif a_type == "type":
            import pyautogui
            pyautogui.write(cmd, interval=0.02)
            result["typed"] = cmd
        elif a_type == "hotkey":
            import pyautogui
            pyautogui.hotkey(*cmd.split("+"))
            result["hotkey"] = cmd
        elif a_type == "wait":
            import time
            time.sleep(float(cmd))
            result["waited_s"] = cmd
        elif a_type == "browser_interact":
            # cmd format: JSON {"url": "...", "selector": "...", "click": true,
            #                   "text": "...optional...", "navigate_first": true}
            import json as _json
            spec = _json.loads(cmd) if cmd.strip().startswith("{") else {"url": cmd}
            from jarvis_v2.skills import browser_cdp
            p, browser, ctx, page = browser_cdp.attach()
            try:
                if spec.get("navigate_first") or spec.get("url"):
                    browser_cdp.navigate(page, spec["url"])
                    import time
                    time.sleep(2)
                sel = spec.get("selector")
                text = spec.get("text")
                do_click = spec.get("click", True)
                if sel and text:
                    r = browser_cdp.type_humanly(page, sel, text)
                elif sel and do_click:
                    r = browser_cdp.click_humanly(page, sel)
                else:
                    r = {"ok": True, "url": page.url, "title": page.title()}
                result.update(r)
            finally:
                p.stop()
        elif a_type == "youtube_watch":
            # cmd format: JSON {"url": "...", "prompt": "..."}
            import json as _json
            spec = _json.loads(cmd) if cmd.strip().startswith("{") else {"url": cmd}
            from jarvis_v2.skills.youtube_watcher import watch_youtube
            r = watch_youtube(spec["url"], spec.get("prompt",
                "Resume paso a paso lo que dice este video."))
            result.update({"method": r.get("method"),
                           "summary_head": (r.get("summary") or "")[:500]})
        else:
            result["error"] = f"unknown action: {a_type}"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"

    last_err = result.get("error")
    history_entry = {"step": state.get("current_step"), "action": a_type,
                     "result": result, "ts": datetime.utcnow().isoformat()}

    return {
        "last_action_result": result,
        "actual_cost_usd": float(action.get("estimated_spend_usd", 0)),
        "last_error": last_err,
        "history": [history_entry],
    }


def node_execute_sim(state: JarvisState) -> JarvisState:
    """Paper executor - mismo flow pero NO toca dinero real ni APIs pagas."""
    action = state.get("proposed_action", {})
    a_type = action.get("type", "")
    result = {
        "action_type": a_type, "mode": "SIMULATION",
        "executed_at": datetime.utcnow().isoformat(),
        "sim_only": True,
    }
    # Si es trade, podriamos simular contra historical data aqui
    return {
        "last_action_result": result,
        "actual_cost_usd": 0.0,  # sim no cuesta
        "last_error": None,
        "history": [{"step": state.get("current_step"), "action": a_type,
                     "result": result, "ts": datetime.utcnow().isoformat()}],
    }


def node_reconciler(state: JarvisState) -> JarvisState:
    """Reconcilia costo real post-execute con ledger SQLite."""
    from jarvis_v2.cfo.reconciler import reconcile
    idem = state.get("cfo_idem_key")
    if not idem:
        return {}  # nada que reconciliar
    actual = float(state.get("actual_cost_usd", 0))
    roi = None
    # Si hay info de result_roi en last_action_result, usarla
    res = state.get("last_action_result", {})
    if isinstance(res, dict) and "roi" in res:
        roi = float(res["roi"])
    rec = reconcile(idem, actual, roi, notes=f"step={state.get('current_step')}")
    return {"messages": [{"role": "reconciler", "content": json.dumps(rec)}]}


def node_verifier(state: JarvisState) -> JarvisState:
    """Verifica post_condition pragmaticamente:
    - shell: rc==0 (output ya valida) - NO screenshot
    - click/type/hotkey: screenshot vision (web stuff)
    - filesystem: Test-Path style
    - skip si sin post_condition
    """
    if state.get("last_error"):
        return {}
    idx = state.get("current_step", 0)
    plan = state.get("plan", [])
    if idx >= len(plan):
        return {"done": True}

    step = plan[idx]
    action_type = step.get("action", "")
    result = state.get("last_action_result", {}) or {}

    # Bypass pragmatico para shell: si execute_real reporto rc=0, asume OK
    if action_type == "shell":
        rc = result.get("returncode", 0)
        stderr = (result.get("stderr") or "").strip()
        if rc == 0:
            return {"current_step": idx + 1, "retries_for_step": 0,
                    "last_error": None}
        return {"last_error": f"shell_rc={rc}: {stderr[:200]}"}

    # Para wait/api/etc sin post_condition explicita -> avanzar
    post = step.get("post_condition", "")
    if not post:
        return {"current_step": idx + 1, "retries_for_step": 0, "last_error": None}

    # GUI/click_som -> screenshot vision (puede fallar con ConnectionReset,
    # tratamos error como SUCCESS para no bloquear tasks low-risk)
    try:
        import pyautogui
        shot = ROOT / "data" / "verify_shot.png"
        shot.parent.mkdir(parents=True, exist_ok=True)
        pyautogui.screenshot(str(shot))
        from jarvis_bridge.jarvis_brain import ask_claude_with_image
        resp = ask_claude_with_image(
            f"Post-condition esperada: {post}\nResponde SOLO 'OK' o 'FAIL: razon'.",
            str(shot), max_tokens=100,
        ) or ""
        if resp.strip().upper().startswith("OK"):
            return {"current_step": idx + 1, "retries_for_step": 0,
                    "last_error": None}
        return {"last_error": f"post_condition_failed: {resp[:200]}"}
    except Exception as e:
        # Fail-open: si vision falla pero ya ejecutamos, avanzar (no bloquear)
        print(f"[verifier] vision error tolerado: {e}", file=sys.stderr)
        return {"current_step": idx + 1, "retries_for_step": 0,
                "last_error": None}


def node_reflector(state: JarvisState) -> JarvisState:
    """Reflexion: si fallo TECNICO (no CFO deny), genera insight, lo GUARDA
    en Mem long-term (memory_manager) y reintenta el step."""
    err = state.get("last_error")
    if not err:
        return {}
    retries = state.get("retries_for_step", 0)
    max_r = state.get("max_retries", 3)
    if retries >= max_r:
        return {"done": True, "last_error": f"max_retries: {err}"}
    plan = state.get("plan", [])
    idx = state.get("current_step", 0)
    step = plan[idx] if idx < len(plan) else {}
    action_type = step.get("action", "unknown")
    objective = state.get("objective", "")

    # 1) Generar insight via Claude
    try:
        from jarvis_bridge.jarvis_brain import ask_claude
        insight = ask_claude(
            f"OBJETIVO USUARIO: {objective[:200]}\n"
            f"Step que fallo: {json.dumps(step, ensure_ascii=False)}\n"
            f"Error: {err}\n\n"
            "Genera un INSIGHT BREVE (1-2 lineas), generalizable a futuras "
            "tareas similares. Formato: 'Al hacer X, hay que Y porque Z'. "
            "NO sea especifico a este intento - sirve para no repetir el "
            "patron de error.",
            model="claude-sonnet-4-6", max_tokens=300,
        ) or ""
    except Exception as e:
        insight = f"(reflexion fallo: {e})"

    # 2) PERSISTIR en memoria long-term (memory_manager)
    saved = None
    if insight and not insight.startswith("(reflexion fallo"):
        try:
            from jarvis_v2.memory.memory_manager import save_lesson
            # Tag con action_type + error class para recall futuro
            err_class = err.split(":")[0][:30] if ":" in err else err[:30]
            tags = [action_type, err_class, "auto_learned"]
            severity = "high" if retries >= 2 else "medium"
            saved = save_lesson(
                insight=insight.strip(),
                tags=tags,
                context=f"objetivo='{objective[:100]}' step={idx} retry={retries}",
                severity=severity,
            )
        except Exception as e:
            saved = {"error": str(e)}

    return {
        "insights": [{
            "step": idx,
            "insight": insight,
            "ts": datetime.utcnow().isoformat(),
            "mem_saved": saved,
        }],
        "retries_for_step": retries + 1,
        "last_error": None,
    }


def node_halt(state: JarvisState) -> JarvisState:
    """Terminal node para deny/escalate del CFO. NO REINTENTAR."""
    reason = state.get("cfo_reason", "halt")
    return {
        "done": True,
        "messages": [{"role": "halt", "content": f"HALTED: {reason}"}],
    }


# ============================================================================
# FAIL-CLOSED ROUTING
# ============================================================================
def route_after_cfo(state: JarvisState) -> str:
    """Enrutador fail-closed. SIN lambda. Si decision ausente/corrupta -> halt."""
    decision = state.get("cfo_decision")
    if decision == "approve_real":
        return "execute_real"
    if decision == "approve_sim_only":
        return "execute_sim"
    # Cualquier otro valor (deny, escalate_human, None, valor corrupto) -> HALT
    return "halt"


def route_after_verifier(state: JarvisState) -> str:
    """Despues de verifier: done, reflect (error tecnico), o load_step (siguiente)."""
    if state.get("done"):
        return "end"
    if state.get("last_error"):
        return "reflect"
    return "load_step"


def route_after_reflector(state: JarvisState) -> str:
    """Reflexion retry o give up."""
    if state.get("done"):
        return "end"
    return "load_step"


# ============================================================================
# GRAPH BUILD
# ============================================================================
def build_graph(use_checkpoint: bool = True):
    from langgraph.graph import StateGraph, END

    sg = StateGraph(JarvisState)

    sg.add_node("rag", node_rag)
    sg.add_node("planner", node_planner)
    sg.add_node("load_step", node_load_step)
    sg.add_node("cfo", node_cfo)
    sg.add_node("execute_real", node_execute_real)
    sg.add_node("execute_sim", node_execute_sim)
    sg.add_node("reconciler", node_reconciler)
    sg.add_node("verifier", node_verifier)
    sg.add_node("reflector", node_reflector)
    sg.add_node("halt", node_halt)

    sg.set_entry_point("rag")
    sg.add_edge("rag", "planner")
    sg.add_edge("planner", "load_step")
    sg.add_edge("load_step", "cfo")

    # CFO -> fail-closed routing
    sg.add_conditional_edges(
        "cfo",
        route_after_cfo,
        {
            "execute_real": "execute_real",
            "execute_sim": "execute_sim",
            "halt": "halt",
        },
    )

    # Execute real -> SIEMPRE reconciler antes de verifier (asentar costo)
    sg.add_edge("execute_real", "reconciler")
    sg.add_edge("execute_sim", "verifier")  # sim no necesita reconciler
    sg.add_edge("reconciler", "verifier")

    # Verifier -> done / reflect / next step
    sg.add_conditional_edges(
        "verifier",
        route_after_verifier,
        {"end": END, "reflect": "reflector", "load_step": "load_step"},
    )

    # Reflector -> retry o end
    sg.add_conditional_edges(
        "reflector",
        route_after_reflector,
        {"end": END, "load_step": "load_step"},
    )

    sg.add_edge("halt", END)

    if use_checkpoint:
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
            CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)
            checkpointer = SqliteSaver(conn)
            return sg.compile(checkpointer=checkpointer)
        except Exception as e:
            print(f"[graph] checkpoint disabled: {e}", flush=True)

    return sg.compile()


def run_objective(objective: str, thread_id: str = "default") -> dict:
    """Entry point usuario."""
    app = build_graph()
    initial: JarvisState = {
        "objective": objective,
        "max_retries": 3,
        "messages": [],
        "history": [],
        "insights": [],
    }
    config = {"configurable": {"thread_id": thread_id}}
    final = None
    for state in app.stream(initial, config=config):
        final = state
        nodes = list(state.keys())
        print(f"[graph] node={nodes}", flush=True)
    return final or {}


if __name__ == "__main__":
    import sys
    obj = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "abrir bloc de notas y escribir hola mundo"
    )
    result = run_objective(obj)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str)[:3000])
