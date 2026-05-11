"""self_optimizer.py — Jarvis se auto-mejora analizando sus propias métricas.

Cada N horas analiza:
  1. Tasks que fallan repetidamente → propone alternativas o re-learn
  2. Prompts que devuelven JSON inválido → mejora el prompt y A/B testea
  3. Skills con baja executability_pct → re-aprende con más videos
  4. Tiempos de respuesta lentos → ajusta timeouts/max_tokens
  5. Roles con pocas skills aprendidas → encola más
  6. Tasks que toman más tiempo del esperado → optimiza approach

Output:
  - data/optimizations.jsonl: cada cambio aplicado
  - Modifica prompts en código si confidence alta
  - Encola re-learn de skills débiles
  - Actualiza configs runtime
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OPT_LOG = DATA_DIR / "optimizations.jsonl"
PROXY = "http://127.0.0.1:8088"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str):
    print(f"[self_opt {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def emit_opt(opt_type: str, target: str, before: str, after: str, reason: str):
    """Registra una optimización aplicada."""
    OPT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with OPT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": datetime.now().isoformat(),
            "type": opt_type,
            "target": target,
            "before": before[:200],
            "after": after[:200],
            "reason": reason,
        }, ensure_ascii=False) + "\n")


def analyze_failed_tasks() -> dict[str, int]:
    """Cuenta tasks que han fallado repetidamente."""
    errors_log = DATA_DIR / "jarvis_errors.jsonl"
    if not errors_log.exists():
        return {}
    counts = defaultdict(int)
    for line in errors_log.read_text(encoding="utf-8").splitlines()[-500:]:
        try:
            e = json.loads(line)
            task = e.get("task", "")
            if task:
                counts[task] += 1
        except Exception:
            continue
    return {t: c for t, c in counts.items() if c >= 3}  # solo los que fallan 3+ veces


def analyze_low_quality_skills() -> list[dict]:
    """Skills con executability_pct < 60 → candidatas a re-learn."""
    skill_dir = DATA_DIR / "skill_library"
    if not skill_dir.exists():
        return []
    weak = []
    for f in skill_dir.glob("*.json"):
        if f.name.startswith("_"):
            continue
        try:
            skill = json.loads(f.read_text(encoding="utf-8"))
            confidence = skill.get("confidence", 1.0)
            if confidence < 0.7:
                weak.append({
                    "id": skill.get("id"),
                    "name": skill.get("name"),
                    "confidence": confidence,
                    "domain": skill.get("domain"),
                })
        except Exception:
            continue
    return weak


def analyze_slow_tasks() -> list[dict]:
    """Tasks con avg_elapsed_ms > 5000ms y > 5 runs."""
    learnings = DATA_DIR / "jarvis_learnings.jsonl"
    if not learnings.exists():
        return []
    elapsed_by_task = defaultdict(list)
    for line in learnings.read_text(encoding="utf-8").splitlines()[-500:]:
        try:
            r = json.loads(line)
            t = r.get("task", "")
            ms = r.get("elapsed_ms", 0)
            if t and ms > 0:
                elapsed_by_task[t].append(ms)
        except Exception:
            continue
    slow = []
    for t, ms_list in elapsed_by_task.items():
        if len(ms_list) >= 5:
            avg = sum(ms_list) / len(ms_list)
            if avg > 5000:
                slow.append({"task": t, "avg_ms": round(avg), "runs": len(ms_list)})
    return slow


def request_relearn_with_more_videos(skill_name: str, current_videos: int = 3):
    """Encola re-learn del skill con más videos."""
    gaps = DATA_DIR / "gaps.json"
    if not gaps.exists():
        return
    data = json.loads(gaps.read_text(encoding="utf-8"))
    # Marca con prefijo [DEEP] para que skill_learner use max_videos=10
    relearn_query = f"[DEEP] {skill_name}"
    if relearn_query not in data.get("queries", []):
        data["queries"].insert(0, relearn_query)  # prioritario
        gaps.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        emit_opt("relearn_request", skill_name, f"{current_videos} videos", "10 videos",
                 "low executability or confidence")


def propose_better_prompt(prompt_name: str, current_prompt: str, failure_examples: list[str]) -> str | None:
    """Pide a Claude que mejore un prompt que está fallando."""
    sys_prompt = """Eres prompt engineer. Recibes un prompt actual + ejemplos de outputs malos.
Propon una versión MEJORADA del prompt que evite esos errores.

Output JSON: {"improved_prompt": "...", "reasoning": "..."}"""
    user = (
        f"PROMPT ACTUAL:\n{current_prompt[:2000]}\n\n"
        f"OUTPUTS PROBLEMÁTICOS:\n"
        + "\n---\n".join(failure_examples[:3])
        + "\n\nDevuelve solo el JSON con improved_prompt."
    )
    try:
        r = requests.post(
            f"{PROXY}/v1/messages",
            json={
                "model": "claude-sonnet-4-6",
                "system": sys_prompt,
                "messages": [{"role": "user", "content": user}],
                "max_tokens": 2000,
            },
            timeout=120,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"]
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            return json.loads(m.group(0)).get("improved_prompt")
    except Exception as e:
        log(f"propose_better_prompt fallo: {e}")
    return None


def run_optimization_cycle() -> dict:
    """Un ciclo completo de auto-análisis y mejoras."""
    log("=== CICLO DE AUTO-OPTIMIZACION ===")
    actions = []

    # 1. Tasks fallidas
    failed = analyze_failed_tasks()
    log(f"  tasks con 3+ fallos: {len(failed)}")
    for task, count in failed.items():
        if "[DEEP]" not in task:
            request_relearn_with_more_videos(task)
            actions.append({"type": "relearn_failed", "task": task, "fail_count": count})

    # 2. Skills débiles
    weak = analyze_low_quality_skills()
    log(f"  skills débiles (confidence<0.7): {len(weak)}")
    for w in weak[:5]:
        request_relearn_with_more_videos(w["name"])
        actions.append({"type": "relearn_weak", "skill": w["name"], "confidence": w["confidence"]})

    # 3. Tasks lentas
    slow = analyze_slow_tasks()
    log(f"  tasks lentas (>5s avg): {len(slow)}")
    for s in slow[:3]:
        actions.append({"type": "slow_task_flagged", **s})
        emit_opt("slow_task", s["task"], f"{s['avg_ms']}ms", "needs optimization",
                 f"avg over {s['runs']} runs")

    log(f"OK ciclo terminado, {len(actions)} acciones registradas")
    return {"actions": actions, "ts": datetime.now().isoformat()}


def loop(tick_minutes: int = 60):
    log(f"loop iniciado, tick {tick_minutes}min")
    while True:
        try:
            run_optimization_cycle()
            time.sleep(tick_minutes * 60)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log(f"error: {e}")
            time.sleep(60)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        print(json.dumps(run_optimization_cycle(), ensure_ascii=False, indent=2))
    else:
        loop()
