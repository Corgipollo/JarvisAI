"""task_failure_memory.py - Memoria persistente de fallos de tareas.

Filosofia: si Jarvis intenta una tarea y falla (endpoint 404, exception,
timeout, etc.), guarda la leccion. Antes de encolar nuevas tareas, el CEO
consulta esta memoria para EVITAR patrones que ya fallaron repetidamente.

Reusa el ChromaDB cerebro_rag + memory_manager (colleccion jarvis_experience
con tags=['task_failure', ...]).

API:
    record_failure(objective, error_msg, http_status=None, hint=None)
        Guarda como leccion con severity proporcional a # de repeticiones.
        Idempotent: el mismo (objective_hash, error_class) actualiza
        hit_count en lugar de duplicar.

    should_skip(objective, threshold=3) -> tuple[bool, str]
        Devuelve (True, reason) si esta task pattern ha fallado >= threshold
        veces consecutivas SIN ningun success entre medio.

    get_failure_patterns_for_prompt(max_chars=2000) -> str
        Devuelve resumen formateado de las top 10 lessons de fallo activas,
        listo para inyectar como context en el prompt del CEO.

    get_known_endpoints() -> list[str]
        Lista endpoints REALES de la API (cargada estaticamente, ground truth).

Schema interno (sobre memory_manager):
    insight: "Task pattern X falla con error Y (N times). Hint: Z"
    tags: ['task_failure', '<error_class>', '<endpoint_or_skill>']
    metadata: {hit_count, last_failure_at, last_success_at, http_status, ...}
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

STATE_FILE = ROOT / "data" / "task_failure_state.json"


# Ground truth: endpoints reales del FastAPI (auditado 2026-05-24).
# Si agregas un endpoint nuevo, agregalo aqui tambien.
KNOWN_ENDPOINTS = [
    "GET  /",
    "GET  /admin",
    "GET  /health",
    "GET  /status",
    "POST /execute",
    "POST /interrupt",
    "POST /queue/add",
    "GET  /queue/status",
    "GET  /tasks",
    "GET  /tasks/{task_id}",
    "GET  /tenants",
    "GET  /tenants/{tenant_id}/summary",
    "GET  /tenants/{tenant_id}/spend",
    "GET  /tenants/{tenant_id}/lessons",
    "POST /tenants/{tenant_id}/actions",
    "POST /tenants/{tenant_id}/credentials",
    "GET  /plans",
    "POST /checkout-session",
    "GET  /subscription/{tenant_id}",
    "POST /api/v1/signup",
    "POST /api/v1/signup/demo",
    "GET  /api/v1/outreach/leads",
    "POST /api/v1/outreach/leads/import",
    "POST /api/v1/outreach/send",
    "GET  /api/v1/outreach/stats",
    "GET  /api/v1/outreach/templates",
    "POST /debate",
    "POST /webhook",
    "GET  /signup",
    "GET  /track/open/{lead_id}.png",
    "GET  /track/click/{lead_id}",
]


def _state() -> dict:
    if not STATE_FILE.exists():
        return {"patterns": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"patterns": {}}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                           encoding="utf-8")


def _pattern_key(objective: str, error_msg: str) -> str:
    """Hash estable que ignora valores variables (numeros, IDs)."""
    # Normaliza: extrae verbo + endpoint del objective si parece API call
    obj_low = objective.lower()
    ep_match = re.search(r"(get|post|put|delete)\s+(/[\w/{}_-]+)", obj_low)
    if ep_match:
        normalized = f"{ep_match.group(1).upper()} {ep_match.group(2)}"
    else:
        # Fallback: primeras 60 chars del objective
        normalized = obj_low[:60]
    # Error class: primera linea + status code si hay
    err_low = (error_msg or "")[:200].lower()
    err_normalized = re.sub(r"\b\d{4,}\b", "N", err_low)[:120]
    payload = f"{normalized}::{err_normalized}"
    return hashlib.sha1(payload.encode()).hexdigest()[:16]


def _classify_error(error_msg: str) -> str:
    err = (error_msg or "").lower()
    if "404" in err or "not found" in err:
        return "endpoint_not_found"
    if "401" in err or "unauthorized" in err:
        return "auth_failed"
    if "403" in err or "forbidden" in err:
        return "forbidden"
    if "500" in err or "internal server" in err:
        return "server_error"
    if "timeout" in err or "timed out" in err:
        return "timeout"
    if "connection" in err and ("refused" in err or "reset" in err):
        return "connection_refused"
    if "rate" in err and "limit" in err:
        return "rate_limited"
    if "json" in err and ("decode" in err or "parse" in err):
        return "json_parse_error"
    return "unknown"


def record_failure(
    objective: str,
    error_msg: str,
    http_status: int | None = None,
    hint: str | None = None,
) -> dict:
    """Guarda fallo en state JSON local + lessons en memory_manager."""
    key = _pattern_key(objective, error_msg)
    err_class = _classify_error(error_msg)
    state = _state()
    p = state["patterns"].setdefault(key, {
        "objective_sample": objective[:300],
        "error_msg_sample": (error_msg or "")[:300],
        "error_class": err_class,
        "http_status": http_status,
        "fail_count": 0,
        "first_seen": datetime.utcnow().isoformat(),
        "last_failure_at": "",
        "last_success_at": "",
        "consecutive_fails": 0,
        "hint": hint or "",
    })
    p["fail_count"] += 1
    p["consecutive_fails"] += 1
    p["last_failure_at"] = datetime.utcnow().isoformat()
    if hint:
        p["hint"] = hint
    _save_state(state)

    # Tambien guarda como leccion en memory_manager si esta disponible
    try:
        from jarvis_v2.memory import memory_manager
        # Severity escala con consecutive_fails
        sev = "critical" if p["consecutive_fails"] >= 5 else \
              "high" if p["consecutive_fails"] >= 3 else "medium"
        insight = (
            f"Task pattern '{p['objective_sample'][:120]}' falla con "
            f"{err_class} ({p['consecutive_fails']} fails consecutivos). "
            f"Error: {p['error_msg_sample'][:120]}"
        )
        if p["hint"]:
            insight += f". Hint: {p['hint']}"
        memory_manager.save_lesson(
            insight=insight,
            tags=["task_failure", err_class],
            context=f"objective: {objective[:200]}",
            severity=sev,
        )
    except Exception:
        pass

    return {"key": key, "consecutive_fails": p["consecutive_fails"],
            "error_class": err_class}


def record_success(objective: str) -> dict:
    """Resetea consecutive_fails para este patron (si existe)."""
    state = _state()
    reset_count = 0
    obj_low = objective.lower()
    ep_match = re.search(r"(get|post|put|delete)\s+(/[\w/{}_-]+)", obj_low)
    normalized = (f"{ep_match.group(1).upper()} {ep_match.group(2)}"
                   if ep_match else obj_low[:60])
    for key, p in state["patterns"].items():
        if normalized in p.get("objective_sample", "").lower():
            p["consecutive_fails"] = 0
            p["last_success_at"] = datetime.utcnow().isoformat()
            reset_count += 1
    if reset_count:
        _save_state(state)
    return {"reset_count": reset_count}


def should_skip(objective: str, threshold: int = 3) -> tuple[bool, str]:
    """Si este patron ha fallado >= threshold veces consecutivas, sugerir skip."""
    state = _state()
    obj_low = objective.lower()
    ep_match = re.search(r"(get|post|put|delete)\s+(/[\w/{}_-]+)", obj_low)
    normalized = (f"{ep_match.group(1).upper()} {ep_match.group(2)}"
                   if ep_match else obj_low[:60])
    for key, p in state["patterns"].items():
        if normalized in p.get("objective_sample", "").lower():
            if p["consecutive_fails"] >= threshold:
                return True, (f"pattern fail {p['consecutive_fails']}x consecutivos "
                              f"con {p['error_class']}. last_err: "
                              f"{p['error_msg_sample'][:120]}")
    return False, ""


def get_failure_patterns_for_prompt(max_chars: int = 2000) -> str:
    """Resumen de fallos activos para inyectar al prompt del CEO."""
    state = _state()
    # Ordenar por consecutive_fails desc, tomar los 10 mas activos
    items = sorted(
        state["patterns"].values(),
        key=lambda p: -p.get("consecutive_fails", 0),
    )
    active = [p for p in items if p.get("consecutive_fails", 0) > 0][:10]
    if not active:
        return "(sin fallos activos registrados todavia)"
    lines = ["PATRONES QUE HAN FALLADO RECIENTEMENTE (EVITAR ESTOS OBJETIVOS):"]
    for p in active:
        line = (f"- {p['error_class']} ({p['consecutive_fails']}x): "
                f"{p['objective_sample'][:120]}")
        if p.get("hint"):
            line += f" | HINT: {p['hint'][:80]}"
        lines.append(line)
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars - 3] + "..."
    return text


def get_known_endpoints_for_prompt() -> str:
    """Lista endpoints reales para inyectar al prompt como ground truth."""
    return ("ENDPOINTS REALES DEL API (USA SOLO ESTOS):\n"
            + "\n".join(f"  {ep}" for ep in KNOWN_ENDPOINTS))


def stats() -> dict:
    state = _state()
    total = len(state["patterns"])
    active = sum(1 for p in state["patterns"].values()
                  if p.get("consecutive_fails", 0) > 0)
    by_class: dict[str, int] = {}
    for p in state["patterns"].values():
        cls = p.get("error_class", "unknown")
        by_class[cls] = by_class.get(cls, 0) + 1
    return {"total_patterns": total, "active_failures": active,
            "by_error_class": by_class}


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--stats", action="store_true")
    p.add_argument("--prompt", action="store_true",
                    help="muestra texto listo para inyectar al CEO")
    args = p.parse_args()

    if args.stats:
        print(json.dumps(stats(), indent=2))
    elif args.prompt:
        print(get_known_endpoints_for_prompt())
        print()
        print(get_failure_patterns_for_prompt())
    else:
        # Smoke test
        r1 = record_failure(
            "MODO INVESTIGACION: usa POST /api/v1/research/bulk_contact_research",
            "404 Not Found: endpoint /api/v1/research/bulk_contact_research",
            http_status=404,
            hint="Este endpoint no existe; usa GET /api/v1/outreach/leads",
        )
        print("record_failure:", r1)
        skip, reason = should_skip(
            "MODO INVESTIGACION: POST /api/v1/research/bulk_contact_research",
            threshold=1,
        )
        print(f"should_skip: {skip} | {reason}")
        print("\n=== Prompt injection text ===")
        print(get_failure_patterns_for_prompt())
