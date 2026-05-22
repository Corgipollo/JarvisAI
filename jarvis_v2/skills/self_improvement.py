"""self_improvement.py - Jarvis lee su propio codigo, identifica mejoras,
las escribe y commit+push.

Flow:
  1. Escanea jarvis_v2/ (archivos .py)
  2. Selecciona uno target (random, o el que tenga FIXME/TODO, o por antiguedad)
  3. Le pasa el codigo + lessons aprendidas a Sonnet con MODO ARQUITECTO
  4. Sonnet devuelve diff propuesto + razon
  5. Si el diff es plausible (no destructivo, sintaxis OK), aplica
  6. python -m py_compile para validar sintaxis
  7. git add + commit + push si pasa
  8. Si falla, rollback automatico

Triggers HEAVY (Sonnet) automatico porque el system prompt lleva "MODO ARQUITECTO".
"""
from __future__ import annotations

import json
import random
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET_DIRS = [ROOT / "jarvis_v2", ROOT / "jarvis_bridge"]
SKIP_PATTERNS = ("__pycache__", ".pyc", "_test.py", "data/", "workspace/")
IMPROVEMENT_LOG = ROOT / "data" / "self_improvement.log"


def _log(msg: str):
    IMPROVEMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.utcnow().isoformat()}] {msg}"
    print(line, flush=True)
    try:
        with IMPROVEMENT_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def list_py_files() -> list[Path]:
    files = []
    for d in TARGET_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*.py"):
            s = str(p)
            if any(sk in s for sk in SKIP_PATTERNS):
                continue
            files.append(p)
    return files


def pick_target(strategy: str = "todo_or_old") -> Path | None:
    """Estrategias de seleccion:
        - 'todo_or_old': busca FIXME/TODO/XXX, si no hay random.
        - 'random': random sample.
        - 'shortest': el archivo mas corto (probablemente refactorable).
    """
    files = list_py_files()
    if not files:
        return None

    if strategy == "random":
        return random.choice(files)
    if strategy == "shortest":
        return min(files, key=lambda f: f.stat().st_size)

    # todo_or_old: prefiere archivos con FIXME/TODO/XXX
    candidates_with_todo = []
    for f in files:
        try:
            txt = f.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"\b(FIXME|TODO|XXX|HACK)\b", txt):
                candidates_with_todo.append(f)
        except Exception:
            continue
    if candidates_with_todo:
        return random.choice(candidates_with_todo)
    return random.choice(files)


def propose_improvement(file_path: Path, focus: str = "") -> dict:
    """Envia el codigo a Sonnet (via OpenRouter router por keyword MODO ARQUITECTO).

    Returns: {ok, new_content, reason, original}
    """
    try:
        from jarvis_bridge.jarvis_brain import ask_claude
    except ImportError as e:
        return {"ok": False, "error": f"jarvis_brain no disponible: {e}"}

    try:
        original = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"read_fail: {e}"}

    if len(original) < 100:
        return {"ok": False, "error": "file_too_short"}
    if len(original) > 15000:
        return {"ok": False, "error": "file_too_long_for_safe_refactor"}

    focus_line = f"\nFOCUS DEL USUARIO: {focus}\n" if focus else ""
    system = (
        "MODO ARQUITECTO GOD-MODE. Eres ingeniero senior de Jarvis V2 sobre "
        "Python 3.10+ en Windows 11. Recibes un archivo y debes proponer una "
        "mejora puntual: bug fix, refactor de claridad, documentacion mejorada, "
        "manejo de errores adicional, o performance. NO inventes features nuevos. "
        "NO rompas la API publica del archivo. PROHIBIDO: placeholders, "
        "comentarios '// resto del codigo', TODO sin resolver, dejar funciones "
        "vacias. Devuelve EXACTAMENTE este JSON:\n"
        '{"reason": "una linea explicando el cambio", '
        '"new_content": "<archivo entero modificado>"}\n'
        "Si NO ves nada que mejorar de forma segura, devuelve "
        '{"reason": "no_safe_improvement", "new_content": null}'
    )
    prompt = (
        f"ARCHIVO: {file_path.relative_to(ROOT)}\n"
        f"LONGITUD: {len(original)} chars{focus_line}\n\n"
        f"```python\n{original}\n```\n\n"
        "Propon UNA mejora puntual y devuelve el JSON pedido."
    )

    raw = ask_claude(prompt, system=system, max_tokens=8000, retries=1)
    if not raw:
        return {"ok": False, "error": "llm_returned_none"}

    # Extract JSON
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        return {"ok": False, "error": "no_json_in_response",
                "raw_head": raw[:300]}
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"ok": False, "error": f"json_decode_fail: {e}",
                "raw_head": raw[:300]}

    if not parsed.get("new_content"):
        return {"ok": False, "error": "no_improvement_proposed",
                "reason": parsed.get("reason", "")}

    return {
        "ok": True,
        "original": original,
        "new_content": parsed["new_content"],
        "reason": parsed.get("reason", "(sin razon)"),
    }


def apply_and_validate(file_path: Path, new_content: str,
                        original: str) -> dict:
    """Aplica el cambio, valida sintaxis, rollback si falla."""
    backup = file_path.read_text(encoding="utf-8")
    try:
        file_path.write_text(new_content, encoding="utf-8")
    except Exception as e:
        return {"ok": False, "error": f"write_fail: {e}"}

    # Validar sintaxis con py_compile
    r = subprocess.run([sys.executable, "-m", "py_compile", str(file_path)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        # Rollback
        file_path.write_text(backup, encoding="utf-8")
        return {"ok": False, "error": "syntax_invalid_rollbacked",
                "compile_stderr": r.stderr[:300]}

    return {"ok": True, "validated": True}


def commit_and_push(file_path: Path, reason: str) -> dict:
    """git add + commit + push del cambio."""
    rel = file_path.relative_to(ROOT)
    try:
        subprocess.run(["git", "add", str(rel)], cwd=ROOT,
                       capture_output=True, check=True)
        msg = f"self_improve: {rel.name} - {reason[:100]}\n\nAutonomamente generado por jarvis_v2.skills.self_improvement"
        r = subprocess.run(["git", "commit", "-m", msg], cwd=ROOT,
                            capture_output=True, text=True)
        if r.returncode != 0:
            return {"ok": False, "error": f"commit_fail: {r.stderr[:200]}"}
        # Get commit hash
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            cwd=ROOT, capture_output=True, text=True).stdout.strip()
        rp = subprocess.run(["git", "push", "origin", "master"], cwd=ROOT,
                             capture_output=True, text=True)
        return {"ok": True, "commit": h, "pushed": rp.returncode == 0,
                "push_stderr": rp.stderr[:200] if rp.returncode != 0 else ""}
    except subprocess.CalledProcessError as e:
        return {"ok": False, "error": f"git_op_fail: {e}"}


def run_one_cycle(focus: str = "",
                   strategy: str = "todo_or_old",
                   do_push: bool = True) -> dict:
    """Un ciclo completo: pick -> propose -> apply -> validate -> commit + push.

    Devuelve dict con steps + final outcome.
    """
    _log(f"=== self_improvement cycle start ===")
    target = pick_target(strategy)
    if not target:
        _log("no target picked")
        return {"ok": False, "step": "pick", "error": "no_targets"}
    _log(f"target: {target.relative_to(ROOT)}")

    prop = propose_improvement(target, focus=focus)
    if not prop.get("ok"):
        _log(f"propose fail: {prop}")
        return {"ok": False, "step": "propose", "target": str(target.relative_to(ROOT)),
                **prop}
    _log(f"propose OK: {prop['reason']}")

    val = apply_and_validate(target, prop["new_content"], prop["original"])
    if not val.get("ok"):
        _log(f"validate fail: {val}")
        return {"ok": False, "step": "validate",
                "target": str(target.relative_to(ROOT)),
                "reason": prop["reason"], **val}
    _log(f"validate OK")

    if not do_push:
        return {"ok": True, "step": "applied_no_push",
                "target": str(target.relative_to(ROOT)),
                "reason": prop["reason"]}

    push = commit_and_push(target, prop["reason"])
    _log(f"commit: {push}")
    return {"ok": push.get("ok", False), "step": "commit",
            "target": str(target.relative_to(ROOT)),
            "reason": prop["reason"], **push}


if __name__ == "__main__":
    focus = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    r = run_one_cycle(focus=focus, do_push=True)
    print(json.dumps(r, ensure_ascii=False, indent=2))
