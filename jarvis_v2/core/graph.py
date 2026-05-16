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
    """Genera plan validado por Pydantic. Si LLM falla schema -> raise (LangGraph retry)."""
    from jarvis_v2.core.llm_structured import llm_structured
    from jarvis_v2.core.schemas import Plan

    obj = state.get("objective", "")
    ctx = state.get("cerebro_context", "")

    prompt = (
        f"OBJETIVO USUARIO: {obj}\n\n"
        f"CONTEXTO RELEVANTE (CerebroEmmanuel):\n{ctx[:2000]}\n\n"
        "Divide en pasos atomicos. PRIORIZA CLI/API sobre GUI.\n"
        "Cada step DEBE tener estimated_spend_usd (0.0 si es gratis).\n"
        "Si una accion implica $ real (trade/ads), marca is_financial=true.\n"
    )

    plan_obj = llm_structured(
        prompt,
        Plan,
        system="Eres planificador atomico. Pasos minimos y precisos.",
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
                      "content": f"plan_with_{len(plan_obj.steps)}_steps"}],
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
    """Verifica post_condition contra screenshot/output."""
    if state.get("last_error"):
        # Si hubo error tecnico, no verificamos - va directo a reflector
        return {}
    idx = state.get("current_step", 0)
    plan = state.get("plan", [])
    if idx >= len(plan):
        return {"done": True}
    step = plan[idx]
    post = step.get("post_condition", "")
    if not post:
        # Sin post_condition explicita -> avanzar
        return {"current_step": idx + 1, "retries_for_step": 0, "last_error": None}
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
        return {"last_error": f"verifier_error: {e}"}


def node_reflector(state: JarvisState) -> JarvisState:
    """Reflexion: si fallo TECNICO (no CFO deny), genera insight y reintenta."""
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
    try:
        from jarvis_bridge.jarvis_brain import ask_claude
        insight = ask_claude(
            f"Step que fallo: {json.dumps(step, ensure_ascii=False)}\n"
            f"Error: {err}\n"
            "Insight breve (1-2 lineas) que se inyectara al proximo intento.",
            model="claude-sonnet-4-6", max_tokens=200,
        ) or ""
    except Exception as e:
        insight = f"(reflexion fallo: {e})"
    return {
        "insights": [{"step": idx, "insight": insight,
                      "ts": datetime.utcnow().isoformat()}],
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
