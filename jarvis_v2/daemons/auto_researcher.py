"""auto_researcher.py - Motor de curiosidad AGI.

Alias del omniparser_researcher con extension: si detecta upgrade significant,
invoca self_improvement.py directamente sobre el archivo relevante para
aplicar el fix de forma autonoma.

Registrado como schtask 'Jarvis_AutoResearch' cada 12h (ver
scripts/install_researcher.ps1).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jarvis_v2.daemons.omniparser_researcher import (
    main as _research_main, _log as _log,
)


# Mapeo: action recommended -> archivo del repo donde aplicar self-improvement
ACTION_TARGETS = {
    "urgent_upgrade": [
        "jarvis_v2/skills/omniparser_engine.py",
    ],
    "propose_refactor": [
        "jarvis_v2/skills/omniparser_engine.py",
    ],
    "monitor": [],  # nada que aplicar
}


def _trigger_self_improvement(action: str, summary: str) -> dict:
    """Invoca self_improvement.py con focus = summary del researcher.

    Solo se ejecuta si action in {urgent_upgrade, propose_refactor}.
    Aplica al primer target del mapeo. Push deshabilitado por seguridad
    (deja commit local; Emmanuel revisa antes de push).
    """
    targets = ACTION_TARGETS.get(action, [])
    if not targets:
        _log(f"no targets para action='{action}', skip self_improvement")
        return {"ok": False, "skipped": True}
    target = targets[0]
    _log(f"invocando self_improvement target={target} focus='{summary[:80]}'")
    try:
        from jarvis_v2.skills.self_improvement import run_one_cycle
        r = run_one_cycle(
            focus=summary,
            target_file=target,
            do_push=False,  # commit local, no push automatico
        )
        _log(f"self_improvement result: {r.get('step')}/{r.get('ok')}")
        return r
    except Exception as e:
        _log(f"self_improvement error: {e}")
        return {"ok": False, "error": str(e)}


def main() -> dict:
    _log("=== auto_researcher cycle start (curiosity engine) ===")
    research_result = _research_main()
    if not research_result.get("ok"):
        return research_result

    significant = research_result.get("significant", False)
    action = research_result.get("action", "monitor")
    new_count = research_result.get("new_count", 0)

    out = {
        "research": research_result,
        "self_improvement": None,
    }

    if significant and action in ACTION_TARGETS and ACTION_TARGETS[action]:
        # Lee el ultimo summary del report para pasarlo como focus
        report = ROOT / "data" / "reports" / "omniparser_upgrades.md"
        summary = ""
        if report.exists():
            txt = report.read_text(encoding="utf-8", errors="replace")
            # Toma la ultima entrada
            entries = txt.split("\n## ")
            if entries:
                summary = entries[-1][:600]
        out["self_improvement"] = _trigger_self_improvement(action, summary)

    _log(f"cycle done: new={new_count} significant={significant} action={action}")
    return out


if __name__ == "__main__":
    r = main()
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
