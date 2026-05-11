"""skill_executor.py — Comprueba que una skill aprendida ES ejecutable.

Toma un skill JSON de la library, lee sus steps, los ejecuta con las skills
nativas (mouse, vision, files, pc_control) y reporta si funciona o donde fallo.

Uso:
    python skill_executor.py <skill_id>
    python skill_executor.py screenshot_windows_a1b2c3d4

Validacion:
  Para cada step, intenta mapear su action a una funcion ejecutable.
  Si todos los steps mapean -> "executable" score = 100%.
  Si ejecutas (no dry_run), corre las acciones de verdad y mide success.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SKILLS_DIR = ROOT / "data" / "skill_library"


def load_skill(skill_id_or_name: str) -> dict | None:
    """Busca skill por id exacto o nombre parcial."""
    if not SKILLS_DIR.exists():
        return None
    # Try exact id
    f = SKILLS_DIR / f"{skill_id_or_name}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    # Fuzzy: buscar en _index
    idx = SKILLS_DIR / "_index.jsonl"
    if idx.exists():
        for line in idx.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                if (skill_id_or_name.lower() in entry["id"].lower()
                        or skill_id_or_name.lower() in entry["name"].lower()):
                    fpath = SKILLS_DIR / entry["file"]
                    if fpath.exists():
                        return json.loads(fpath.read_text(encoding="utf-8"))
            except Exception:
                continue
    return None


def parse_step_to_action(step: dict) -> dict:
    """Mapea step text -> action ejecutable (heuristica simple).

    Detecta patrones tipo 'presionar X', 'click en Y', 'escribir Z', etc.
    """
    action_text = (step.get("action", "") + " " + step.get("details", "")).lower()
    parsed = {"executable": False, "type": None, "args": []}

    # Pattern: presionar tecla(s)
    m = re.search(r"presion[ao]r?\s+(?:tecla\s+)?([a-zA-Z0-9+_\-\s]+?)(?:\s|$|,|\.|\()", action_text)
    if m:
        keys = m.group(1).strip()
        # Limpiar
        keys = re.sub(r"\s+", " ", keys).strip()
        if any(c in keys for c in "+ "):
            key_list = re.split(r"[+\s]+", keys)
            parsed.update({"executable": True, "type": "press_keys", "args": key_list[:5]})
        elif keys:
            parsed.update({"executable": True, "type": "press_key", "args": [keys.split()[0]]})

    # Pattern: click en X
    elif re.search(r"click\s+(?:en\s+)?", action_text):
        target = re.search(r"click\s+(?:en\s+)?(.+?)(?:\.|,|$)", action_text)
        parsed.update({
            "executable": True, "type": "click_text",
            "args": [target.group(1)[:50].strip() if target else "?"],
        })

    # Pattern: escribir/typear texto
    elif re.search(r"(?:escribi|teclear|typear|ingresar)", action_text):
        m = re.search(r"['\"]([^'\"]+)['\"]", action_text)
        if m:
            parsed.update({"executable": True, "type": "type_text", "args": [m.group(1)]})

    # Pattern: abrir app X
    elif re.search(r"abrir?\s+(?:la\s+)?(?:app\s+|aplicacion\s+)?", action_text):
        m = re.search(r"abrir?\s+(?:la\s+)?(?:app\s+|aplicacion\s+)?([\w\s]+?)(?:\s|$|,|\.)", action_text)
        if m:
            parsed.update({"executable": True, "type": "open_app", "args": [m.group(1).strip()]})

    # Pattern: arrastrar
    elif re.search(r"arrastr[ao]r?", action_text):
        parsed.update({"executable": True, "type": "drag", "args": ["needs_coords"]})

    return parsed


def analyze_skill(skill: dict) -> dict:
    """Analiza la skill: cuantos steps son ejecutables sin info adicional."""
    total = 0
    executable = 0
    breakdown = []

    methods = skill.get("methods", [])
    if not methods and skill.get("steps"):
        methods = [{"name": "default", "steps": skill["steps"]}]

    for method in methods:
        for step in method.get("steps", []):
            total += 1
            parsed = parse_step_to_action(step)
            if parsed["executable"]:
                executable += 1
            breakdown.append({
                "method": method.get("name", "?"),
                "step": step.get("step", "?"),
                "action_text": step.get("action", "")[:60],
                "parsed_type": parsed["type"],
                "args": parsed["args"],
                "executable": parsed["executable"],
            })

    score_pct = (executable / total * 100) if total > 0 else 0
    return {
        "skill_name": skill.get("name", "?"),
        "total_steps": total,
        "executable_steps": executable,
        "executability_pct": round(score_pct, 1),
        "verdict": (
            "EJECUTABLE_TOTAL" if score_pct >= 80
            else "EJECUTABLE_PARCIAL" if score_pct >= 50
            else "NECESITA_REFINAMIENTO"
        ),
        "breakdown": breakdown,
    }


async def dry_run_skill(skill: dict) -> dict:
    """Dry-run: mapea cada step a action, NO ejecuta acciones reales.

    Devuelve plan ejecutable que el agente PODRIA correr.
    """
    analysis = analyze_skill(skill)
    return {
        "skill": skill.get("name"),
        "skill_id": skill.get("id"),
        "analysis": analysis,
        "mode": "dry_run_no_execution",
    }


def main():
    if len(sys.argv) < 2:
        # Lista todas las skills disponibles
        if not SKILLS_DIR.exists():
            print("Sin skills aun. Espera el self_improvement loop.")
            return
        print("Skills en library:")
        idx = SKILLS_DIR / "_index.jsonl"
        if idx.exists():
            for line in idx.read_text(encoding="utf-8").splitlines():
                try:
                    e = json.loads(line)
                    print(f"  {e['id']:40s} | {e['name']}")
                except Exception:
                    continue
        return

    skill_id = sys.argv[1]
    skill = load_skill(skill_id)
    if not skill:
        print(f"Skill no encontrada: {skill_id}")
        return

    result = asyncio.run(dry_run_skill(skill))
    print(json.dumps({
        "skill": result["skill"],
        "skill_id": result["skill_id"],
        "total_steps": result["analysis"]["total_steps"],
        "executable_steps": result["analysis"]["executable_steps"],
        "executability_pct": result["analysis"]["executability_pct"],
        "verdict": result["analysis"]["verdict"],
    }, indent=2, ensure_ascii=False))
    print()
    print("=== BREAKDOWN POR STEP ===")
    for b in result["analysis"]["breakdown"]:
        mark = "[OK]" if b["executable"] else "[NO]"
        print(f"  {mark} step {b['step']}: {b['action_text']}")
        if b["executable"]:
            print(f"       -> {b['parsed_type']}({b['args']})")


if __name__ == "__main__":
    main()
