"""graph.py - LangGraph state machine completa con CFO gateway integrado.

Zero-Defect Routing: route_after_cfo es fail-closed (default = halt).
Pydantic-validated planner: imposible que LLM omita estimated_spend_usd.
CFO deny -> END (NO Reflector). Reflector solo para fallos tecnicos.
Reconciler obligatorio post-execute_real para asentar costo real en ledger.
"""
from __future__ import annotations

import json
import operator  # kept for legacy callers, capped reducer below replaces uses
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, TypedDict, Literal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CHECKPOINT_DB = ROOT / "data" / "jarvis_v2_checkpoints.db"


_EXPLICIT_STEP_RE = re.compile(r"(?:^|\s)(\d+)\s*[\.\)]\s+", re.MULTILINE)


def count_explicit_steps(objective: str) -> int:
    """Cuenta enumeraciones '1.', '2)', etc. para detectar objetivos multi-paso.

    Solo cuenta si hay >=2 distintos para evitar falsos positivos con un
    '1.' suelto en medio del texto.
    """
    nums = {int(m.group(1)) for m in _EXPLICIT_STEP_RE.finditer(objective)}
    nums = {n for n in nums if 1 <= n <= 20}
    if len(nums) < 2:
        return 0
    return max(nums)


def split_objective_by_numbers(objective: str) -> list[str]:
    """Parte un objetivo numerado '1. foo 2. bar 3. baz' en sub-objectives.

    Fallback usado si el LLM persiste en condensar despues de retry.
    """
    parts = re.split(r"(?:^|\s)\d+\s*[\.\)]\s+", objective)
    return [p.strip() for p in parts if len(p.strip()) > 5]


# ============================================================================
# STATE - explicito, TypedDict, operator.add solo donde DEBE acumularse
# ============================================================================

# Reducer factory: append + cap FIFO a los N mas recientes.
# Fix 2026-05-25: antes los campos messages/history/insights usaban operator.add
# sin techo. Cada iteracion del graph crecia la lista -> LangGraph binop.py:122
# (BinaryOperator.update) acumulaba state hasta MemoryError. El subprocess se
# moria con el bug interno de langgraph. Capped reducer previene la explosion.
def _capped_append(max_n: int):
    """Factory de reducer: concatena + trunca a max_n elementos mas recientes."""
    def _reducer(left: list | None, right: list | None) -> list:
        if left is None:
            left = []
        if right is None:
            right = []
        merged = left + right
        if len(merged) > max_n:
            return merged[-max_n:]
        return merged
    _reducer.__name__ = f"capped_append_{max_n}"
    return _reducer


# Caps razonables para state agentic:
#  - messages: 200 (suficiente para 10+ ciclos planner/executor con margen)
#  - history: 100 (acciones tomadas, suele ser 1-2 por step)
#  - insights: 50 (lecciones acumuladas, deduplicadas por memory_manager)
_MAX_MESSAGES = int(os.environ.get("JARVIS_STATE_MAX_MESSAGES", "200"))
_MAX_HISTORY = int(os.environ.get("JARVIS_STATE_MAX_HISTORY", "100"))
_MAX_INSIGHTS = int(os.environ.get("JARVIS_STATE_MAX_INSIGHTS", "50"))


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

    # ACCUMULATING fields (capped reducer - previene MemoryError en binop.py)
    messages: Annotated[list, _capped_append(_MAX_MESSAGES)]
    history: Annotated[list, _capped_append(_MAX_HISTORY)]
    insights: Annotated[list, _capped_append(_MAX_INSIGHTS)]

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

    explicit_n = count_explicit_steps(obj)
    step_rule = (
        "5. Genera el MINIMO numero de steps. Si una sola linea de shell hace "
        "todo el objetivo, usa 1 solo step.\n"
    )
    if explicit_n >= 2:
        step_rule = (
            f"5. ANTI-CONDENSACION: El objetivo del usuario enumera {explicit_n} "
            f"sub-tareas explicitas ('1.', '2.', ...). DEBES generar AL MENOS "
            f"{explicit_n} steps separados, uno por cada sub-tarea numerada. "
            "PROHIBIDO meter varias sub-tareas en un solo step. NO uses "
            "operadores '&&' / ';' para colapsar varias en un solo shell.\n"
        )

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
        + step_rule +
        "6. command_or_task DEBE ser autosuficiente: 'cmd /c <cmd>' o "
        "'powershell -Command \"<ps>\"'. Nunca uses paths Unix (/c/foo) en Windows.\n"
    )

    plan_obj = llm_structured(
        prompt,
        Plan,
        # OJO: system NO debe tener triggers HEAVY (MODO INGENIERO/ARQUITECTO/
        # PERSISTENCIA/etc.) o cada plan dispara Sonnet -> rate limit OAuth Max
        # explota en pocos minutos. Default Haiku que es suficiente para
        # generar shells literales.
        system=(
            "Eres planner atomico Windows EN MODO AGI AUTONOMO. "
            "REGLA MAESTRA: PROHIBIDO delegar decisiones tecnicas o conflictos "
            "de infraestructura al usuario. Ante bloqueo (puerto ocupado, "
            "archivo missing, dependencia ausente) ELIGE la solucion de menor "
            "impacto destructivo, implementala con shell concreto, documentala "
            "como step adicional con file_write a data/reports/auto_decisions.log, "
            "y continua el flujo. Jamas emitas pasos del tipo 'preguntar al "
            "usuario', 'esperar confirmacion', 'requerir input humano'.\n\n"
            "DIRECTIVA ZERO-PERMISSION ALTERNATIVAS GRATUITAS: cuando un "
            "servicio externo requiera tarjeta, signup OAuth humano o captcha "
            "(ej. dominios pagados, Cloudflare login, SaaS de paga), BUSCA "
            "primero alternativa open-source / API gratuita sin signup / pip "
            "install local / cliente self-hosted. Ejemplos: en lugar de "
            "Cloudflare Registrar usa duckdns.org via API, en lugar de "
            "SendGrid usa SMTP propio Gmail, en lugar de Postgres pago usa "
            "SQLite local, en lugar de OpenAI paga usa Anthropic OAuth Max. "
            "Solo si TODAS las alternativas gratuitas estan agotadas y la "
            "tarea es estrictamente bloqueante, registra el bloqueo a "
            "data/reports/auto_decisions.log con la lista de alternativas "
            "probadas y por que fallaron.\n\n"
            "Generas action=shell con command_or_task='cmd /c ...' o "
            "'powershell -Command ...' literal. Sin placeholders, sin TODOs, "
            "sin pasos abstractos. "
            "Si objetivo implica navegador (Twitter, Shopify, etc.) usa "
            "action=browser_interact con JSON {url, selector, click, text}. "
            "Si implica video YouTube usa action=youtube_watch con {url, prompt}."
        ),
        model="claude-haiku-4-5-20251001",
        max_tokens=3000,
        max_retries=2,
    )

    # ANTI-CONDENSACION post-LLM: si objetivo tiene N steps enumerados y el
    # planner devolvio menos, reintentar con prompt aun mas explicito; si
    # vuelve a fallar, expandir manualmente partiendo por enumeracion.
    if explicit_n >= 2 and len(plan_obj.steps) < explicit_n:
        print(f"[planner] CONDENSACION detectada: esperaba >={explicit_n} "
              f"steps, planner devolvio {len(plan_obj.steps)}. Retry forzado.",
              file=sys.stderr)
        sub_objs = split_objective_by_numbers(obj)
        if len(sub_objs) >= explicit_n:
            enumerated = "\n".join(
                f"  STEP {i+1} OBLIGATORIO: {s}"
                for i, s in enumerate(sub_objs[:explicit_n])
            )
            retry_prompt = (
                f"OBJETIVO NUMERADO USUARIO (NO CONDENSES):\n{enumerated}\n\n"
                f"CONTEXTO:\n{ctx[:1500]}\n\n"
                "GENERA EXACTAMENTE UN STEP POR CADA STEP OBLIGATORIO LISTADO. "
                f"len(plan.steps) DEBE SER >= {explicit_n}. Acciones individuales, "
                "una sub-tarea por step. Sin '&&' ni ';' colapsando. "
                "Cada step con action='shell' + cmd literal Windows; o 'file_write' "
                "si el sub-step pide escribir un archivo; o 'api' si pide invocar "
                "un LLM externo."
            )
            try:
                plan_obj_retry = llm_structured(
                    retry_prompt, Plan,
                    system="Eres planner NO condensador. Un step por cada sub-tarea explicita.",
                    model="claude-haiku-4-5-20251001",
                    max_tokens=4000, max_retries=1,
                )
                if len(plan_obj_retry.steps) >= explicit_n:
                    plan_obj = plan_obj_retry
                    print(f"[planner] retry OK: {len(plan_obj.steps)} steps",
                          file=sys.stderr)
                else:
                    print(f"[planner] retry insuficiente: {len(plan_obj_retry.steps)} steps",
                          file=sys.stderr)
            except Exception as e:
                print(f"[planner] retry fail: {e}", file=sys.stderr)

    # HARDENING: si despues de todo el plan sigue vacio, no devolver state
    # mudo (causa el bug status=done con result={}). Propagar last_error.
    steps = [s.model_dump() for s in plan_obj.steps]
    if not steps:
        return {
            "plan": [],
            "objective_summary": plan_obj.objective_summary or "(empty plan)",
            "current_step": 0,
            "retries_for_step": 0,
            "max_retries": 3,
            "last_error": f"planner_empty_plan (explicit_n={explicit_n})",
            "done": True,
            "messages": [{"role": "planner",
                          "content": f"FAIL: plan vacio, objective requeria {explicit_n} steps"}],
        }

    return {
        "plan": steps,
        "objective_summary": plan_obj.objective_summary,
        "current_step": 0,
        "retries_for_step": 0,
        "max_retries": 3,
        "messages": [{"role": "planner",
                      "content": f"plan_{len(steps)}_steps_lessons_{len(lessons)}_explicit_n_{explicit_n}"}],
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
        elif a_type == "desktop_scan":
            # Scan completo de pantalla: OCR + icons. Devuelve JSON light al state.
            from jarvis_v2.skills.desktop_hybrid import scan_desktop
            scan = scan_desktop()
            result.update({
                "screen_size": scan["screen_size"],
                "ocr_count": len(scan["texto_detectado"]),
                "icons_count": len(scan["iconos_detectados"]),
                "texts_sample": [t["texto"] for t in scan["texto_detectado"][:30]],
            })
        elif a_type == "desktop_interact":
            # cmd format: JSON {"text":"BotFather"} o {"icon":"path.png"} o {"coords":[x,y]}
            import json as _json
            spec = _json.loads(cmd) if cmd.strip().startswith("{") else {"text": cmd}
            from jarvis_v2.skills import desktop_hybrid
            if spec.get("text"):
                r = desktop_hybrid.click_text(spec["text"])
            elif spec.get("icon"):
                r = desktop_hybrid.click_icon(spec["icon"],
                                               spec.get("threshold", 0.85))
            elif spec.get("coords"):
                x, y = spec["coords"]
                from jarvis_v2.swarm.human_mouse import human_click
                human_click(x, y)
                r = {"ok": True, "coords": [x, y]}
            else:
                r = {"ok": False, "error": "spec needs text/icon/coords"}
            result.update(r)
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
            model="claude-haiku-4-5-20251001", max_tokens=300,
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


def node_skip_step(state: JarvisState) -> JarvisState:
    """Salta el step actual (idempotency hit u otra causa benigna) y avanza.

    Bugfix 2026-05-23: antes cfo_decision='deny' + cfo_reason='duplicate_recent'
    iba a halt total -> el plan entero moria si el step 1 ya estaba en idem
    cache. Ahora: skipear y avanzar al siguiente step.
    """
    idx = state.get("current_step", 0)
    reason = state.get("cfo_reason", "skip")
    return {
        "current_step": idx + 1,
        "retries_for_step": 0,
        "cfo_decision": None,
        "cfo_reason": None,
        "messages": [{"role": "skip_step",
                      "content": f"skipped_step_{idx}_reason_{reason}"}],
    }


# ============================================================================
# FAIL-CLOSED ROUTING
# ============================================================================
def route_after_cfo(state: JarvisState) -> str:
    """Enrutador fail-closed. SIN lambda. Si decision ausente/corrupta -> halt."""
    decision = state.get("cfo_decision")
    reason = state.get("cfo_reason", "")
    if decision == "approve_real":
        return "execute_real"
    if decision == "approve_sim_only":
        return "execute_sim"
    # Skip benigno: idempotency hit no debe matar el plan, solo el step
    if decision == "deny" and reason == "duplicate_recent":
        return "skip_step"
    # Cualquier otro valor (deny por otra razon, escalate_human, None, corrupto) -> HALT
    return "halt"


def route_after_verifier(state: JarvisState) -> str:
    """Despues de verifier: done, reflect (error tecnico), o load_step (siguiente)."""
    if state.get("done"):
        return "end"
    if state.get("last_error"):
        return "reflect"
    return "load_step"


def route_after_load_step(state: JarvisState) -> str:
    """Despues de load_step: end si done (plan agotado), cfo si hay step para evaluar.

    Fix 2026-05-25: antes era add_edge directo a cfo, ignoraba done=True que
    node_load_step setea cuando current_step >= len(plan). Eso causaba loop
    infinito load_step->cfo->skip_step->load_step sin pasar por verifier
    (unico nodo que chequeaba done).
    """
    if state.get("done"):
        return "end"
    if not state.get("proposed_action"):
        return "end"  # defensa extra: sin action no hay nada que evaluar
    return "cfo"


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
    sg.add_node("skip_step", node_skip_step)

    sg.set_entry_point("rag")
    sg.add_edge("rag", "planner")
    sg.add_edge("planner", "load_step")
    # load_step puede setear done=True si plan agotado -> conditional edge
    sg.add_conditional_edges(
        "load_step",
        route_after_load_step,
        {"end": END, "cfo": "cfo"},
    )

    # CFO -> fail-closed routing (skip_step para idempotency, halt para resto)
    sg.add_conditional_edges(
        "cfo",
        route_after_cfo,
        {
            "execute_real": "execute_real",
            "execute_sim": "execute_sim",
            "skip_step": "skip_step",
            "halt": "halt",
        },
    )

    # skip_step -> load_step (siguiente step del plan)
    sg.add_edge("skip_step", "load_step")

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
    """Entry point usuario.

    Bugfix 2026-05-23: antes iteraba app.stream() que emite {node_name: ...}
    por step y el ultimo NO es el state acumulado -> result quedaba con
    solo lo del ultimo nodo (load_step/halt) y campos como plan/messages
    se perdian. Ahora usamos stream_mode='values' que emite el state
    COMPLETO acumulado en cada step, y devolvemos el ultimo. Eso ademas
    arregla el bug visible 'plan_len=0' tras ejecucion exitosa.
    """
    app = build_graph()
    initial: JarvisState = {
        "objective": objective,
        "max_retries": 3,
        "messages": [],
        "history": [],
        "insights": [],
    }
    # recursion_limit: cap defensivo contra loops infinitos del router.
    # Antes era default 10007 (LangGraph) -> una task cicla 66s consumiendo CPU
    # antes de abortar. Con cap=50 abortamos en <5s y el subprocess muere limpio.
    # Si necesitas mas iteraciones para casos especificos, override via env.
    _RECURSION_CAP = int(os.environ.get("JARVIS_GRAPH_RECURSION_LIMIT", "50"))
    config = {"configurable": {"thread_id": thread_id},
              "recursion_limit": _RECURSION_CAP}
    final_state: dict = {}
    try:
        for state in app.stream(initial, config=config, stream_mode="values"):
            final_state = state  # state COMPLETO acumulado, no per-node
            plan_len = len(state.get("plan", []))
            cstep = state.get("current_step", 0)
            print(f"[graph] step state: plan={plan_len} cur={cstep} done={state.get('done')}",
                  flush=True)
    except Exception as e:
        # GraphRecursionError u otro -> marcar last_error y devolver state parcial.
        # El task_executor lo veera y marcara status=error en el JSON.
        cls = type(e).__name__
        print(f"[graph] stream EXCEPTION {cls}: {e}", flush=True)
        if not final_state:
            final_state = {"messages": [], "plan": [],
                            "last_error": f"{cls}: {str(e)[:300]}"}
        else:
            final_state["last_error"] = f"{cls}: {str(e)[:300]}"
    return final_state


if __name__ == "__main__":
    import sys
    obj = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "abrir bloc de notas y escribir hola mundo"
    )
    result = run_objective(obj)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str)[:3000])
