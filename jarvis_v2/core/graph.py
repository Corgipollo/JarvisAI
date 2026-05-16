"""graph.py - LangGraph state machine: Plan -> Execute -> Verify -> Reflect -> Loop.

Reemplaza el polling de 24 brains por un grafo deterministico con state explicito.
SQLite checkpointing built-in para recuperar de crashes.

Nodos:
  - planner: dado objetivo del usuario, divide en pasos concretos
  - executor: ejecuta el paso actual (CLI > GUI con SoM > vision fallback)
  - verifier: compara screenshot/output con post_condition
  - reflector: si fallo, genera insight (Reflexion) y reintenta o aborta
  - rag: query CerebroEmmanuel para contexto antes de planner

Estado:
  - objective: lo que el user pidio
  - plan: list[step] con pre/post conditions
  - current_step: indice
  - history: list de ejecuciones
  - insights: list de Reflexion notes
  - max_retries: 3 por step
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Annotated, TypedDict

ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT_DB = ROOT / "data" / "jarvis_v2_checkpoints.db"


class JarvisState(TypedDict, total=False):
    objective: str
    plan: list
    current_step: int
    history: list
    insights: list
    last_error: str | None
    retries_for_step: int
    max_retries: int
    cerebro_context: str
    done: bool


def node_rag(state: JarvisState) -> JarvisState:
    """Pre-planner: busca contexto en CerebroEmmanuel."""
    from jarvis_v2.memory.cerebro_rag import search_cerebro
    obj = state.get("objective", "")
    ctx = ""
    try:
        ctx = search_cerebro(obj, top_k=5)
    except Exception as e:
        ctx = f"(RAG no disponible: {e})"
    return {**state, "cerebro_context": ctx}


def node_planner(state: JarvisState) -> JarvisState:
    """Divide objective en steps concretos via Claude."""
    obj = state.get("objective", "")
    ctx = state.get("cerebro_context", "")
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_json
        prompt = (
            f"OBJETIVO USUARIO: {obj}\n\n"
            f"CONTEXTO RELEVANTE DEL VAULT:\n{ctx}\n\n"
            "Divide en PASOS CONCRETOS y EJECUTABLES. Prioriza CLI/API sobre GUI.\n"
            "Cada paso JSON: {action, command_or_task, pre_condition, post_condition}\n"
            "action ∈ {shell, api, click_som, type, hotkey, wait, custom_skill}\n\n"
            "Responde JSON: {steps: [...]}"
        )
        result = ask_claude_json(prompt, system="Eres planificador. Pasos atomicos.",
                                 model="claude-sonnet-4-6", max_tokens=2000)
        steps = result.get("steps", []) if result else []
    except Exception as e:
        steps = [{"action": "wait", "command_or_task": str(e), "pre_condition": "",
                  "post_condition": ""}]
    return {**state, "plan": steps, "current_step": 0, "retries_for_step": 0,
            "history": [], "insights": [], "max_retries": 3}


def node_executor(state: JarvisState) -> JarvisState:
    """Ejecuta paso actual."""
    plan = state.get("plan", [])
    idx = state.get("current_step", 0)
    if idx >= len(plan):
        return {**state, "done": True}
    step = plan[idx]
    action = step.get("action", "")
    history = state.get("history", []) + [{"step": idx, "action": action,
                                            "ts": datetime.now().isoformat()}]
    err = None

    try:
        if action == "shell":
            import subprocess
            subprocess.run(step.get("command_or_task", ""),
                           shell=True, capture_output=True, text=True, timeout=120)
        elif action == "click_som":
            from jarvis_v2.sensor.set_of_mark import generate_som, claude_pick_and_click
            mapping, img = generate_som()
            res = claude_pick_and_click(step.get("command_or_task", ""), img, mapping)
            if res.get("error"):
                err = res["error"]
            else:
                import pyautogui
                pyautogui.click(res["center_x"], res["center_y"])
        elif action == "type":
            import pyautogui
            pyautogui.write(step.get("command_or_task", ""), interval=0.02)
        elif action == "hotkey":
            import pyautogui
            keys = step.get("command_or_task", "").split("+")
            pyautogui.hotkey(*keys)
        elif action == "wait":
            import time
            time.sleep(float(step.get("command_or_task", "1")))
        elif action == "api":
            err = "api action requires custom handler"
        elif action == "custom_skill":
            err = "custom_skill not implemented yet"
        else:
            err = f"unknown action: {action}"
    except Exception as e:
        err = f"{type(e).__name__}: {e}"

    return {**state, "history": history, "last_error": err}


def node_verifier(state: JarvisState) -> JarvisState:
    """Verifica que el paso paso cumple post_condition."""
    plan = state.get("plan", [])
    idx = state.get("current_step", 0)
    err = state.get("last_error")
    if err:
        return {**state}
    if idx >= len(plan):
        return {**state, "done": True}
    step = plan[idx]
    post = step.get("post_condition", "")
    if not post:
        # No verificable -> advance
        return {**state, "current_step": idx + 1, "retries_for_step": 0}
    # Verify via Claude vision on screenshot
    try:
        import pyautogui
        shot = ROOT / "data" / "verify_shot.png"
        shot.parent.mkdir(parents=True, exist_ok=True)
        pyautogui.screenshot(str(shot))
        from jarvis_bridge.jarvis_brain import ask_claude_with_image
        prompt = f"Post-condition esperada: {post}\nResponde SOLO 'OK' o 'FAIL: razon'."
        resp = ask_claude_with_image(prompt, str(shot), max_tokens=100) or ""
        if resp.strip().upper().startswith("OK"):
            return {**state, "current_step": idx + 1, "retries_for_step": 0,
                    "last_error": None}
        return {**state, "last_error": f"post_condition_failed: {resp[:200]}"}
    except Exception as e:
        return {**state, "last_error": f"verifier_error: {e}"}


def node_reflector(state: JarvisState) -> JarvisState:
    """Si paso fallo, genera insight via Claude critico y reintenta o aborta."""
    err = state.get("last_error")
    if not err:
        return state
    retries = state.get("retries_for_step", 0)
    max_r = state.get("max_retries", 3)
    if retries >= max_r:
        return {**state, "done": True, "last_error": f"max_retries_exceeded: {err}"}
    # Reflexion: generate insight
    plan = state.get("plan", [])
    idx = state.get("current_step", 0)
    step = plan[idx] if idx < len(plan) else {}
    try:
        from jarvis_bridge.jarvis_brain import ask_claude
        prompt = (
            f"Step que fallo: {json.dumps(step, ensure_ascii=False)}\n"
            f"Error: {err}\n"
            "Genera un INSIGHT breve (1-2 lineas) que se inyectara como prevencion "
            "en el proximo intento. Formato: 'Al hacer X, hay que Y porque Z'."
        )
        insight = ask_claude(prompt, model="claude-sonnet-4-6", max_tokens=200) or ""
    except Exception as e:
        insight = f"(reflexion failed: {e})"
    insights = state.get("insights", []) + [{"step": idx, "insight": insight,
                                              "ts": datetime.now().isoformat()}]
    # Persist insight to mem0/skills (Day 5)
    return {**state, "insights": insights, "retries_for_step": retries + 1,
            "last_error": None}


def should_continue(state: JarvisState) -> str:
    if state.get("done"):
        return "end"
    if state.get("last_error"):
        return "reflect"
    return "execute"


def build_graph():
    """Construye el grafo LangGraph con SQLite checkpoint."""
    from langgraph.graph import StateGraph, END
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver
    except ImportError:
        SqliteSaver = None

    sg = StateGraph(JarvisState)
    sg.add_node("rag", node_rag)
    sg.add_node("planner", node_planner)
    sg.add_node("executor", node_executor)
    sg.add_node("verifier", node_verifier)
    sg.add_node("reflector", node_reflector)

    sg.set_entry_point("rag")
    sg.add_edge("rag", "planner")
    sg.add_edge("planner", "executor")
    sg.add_edge("executor", "verifier")
    sg.add_conditional_edges(
        "verifier",
        lambda s: "end" if s.get("done") else ("reflect" if s.get("last_error") else "execute"),
        {"end": END, "reflect": "reflector", "execute": "executor"},
    )
    sg.add_edge("reflector", "executor")

    if SqliteSaver:
        CHECKPOINT_DB.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(CHECKPOINT_DB), check_same_thread=False)
        checkpointer = SqliteSaver(conn)
        return sg.compile(checkpointer=checkpointer)
    return sg.compile()


def run_objective(objective: str, thread_id: str = "default") -> dict:
    """Entry point: ejecuta un objetivo end-to-end con state persistente."""
    graph = build_graph()
    initial = {"objective": objective, "max_retries": 3}
    config = {"configurable": {"thread_id": thread_id}}
    final = None
    for state in graph.stream(initial, config=config):
        final = state
        print(f"[graph] step: {list(state.keys())}", flush=True)
    return final or {}


if __name__ == "__main__":
    import sys
    obj = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "abrir Bloc de Notas y escribir hola"
    result = run_objective(obj)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str)[:3000])
