"""debate_engine.py - Actor-Critic interno para codigo de alto riesgo.

Filosofia:
  Antes de aceptar codigo que toca payments, SQL, auth o cualquier accion
  irreversible, el sistema lo somete a un tribunal interno de 2 agentes:
    - Proposer: el codigo o diseno original
    - Critic: busca activamente fallas (inyeccion, race conditions,
              auth bypass, leak de secrets, side effects no documentados)
  Si Critic encuentra issues, Proposer refactoriza. Critic re-revisa.
  Hasta 2 rounds (4 LLM calls). Si tras 2 rounds Critic sigue inconforme,
  el verdict es REJECT y el codigo NO se aplica.

Costo: ~4 calls Haiku/Sonnet via proxy OAuth Max = $0.
Latencia: 4-8 segundos para 2 rounds.

API:
    debate(content, focus_areas, max_rounds=2, model='claude-haiku-4-5') -> dict
        {
          'approved': bool,
          'rounds': int,
          'issues_found': list[str],
          'issues_resolved': list[str],
          'final_code': str | None,        # solo si refactor exitoso
          'reasoning': str,
        }

    should_trigger_debate(text) -> bool
        Heuristica de keywords para auto-invocacion.

Keywords que disparan debate automatico:
    sql, webhook, stripe, auth, password, secret, credential, token, payment,
    delete, drop, rm -rf, irreversible, transaction, migrate, alter table

CLI:
    python -m jarvis_v2.core.debate_engine --file FILE.py --focus "SQL injection"
    python -m jarvis_v2.core.debate_engine --text "..." --focus "..."
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TRIGGER_KEYWORDS = {
    "sql", "select * from", "insert into", "update ", "delete from",
    "drop table", "alter table", "truncate", "select ",
    "webhook", "stripe", "auth", "authentication", "password",
    "secret", "credential", "token", "api_key", "payment", "billing",
    "rm -rf", "irreversible", "transaction",
    "migrate", "private key", "wallet", "binance_market_order",
    "youtube_upload", "file_delete", "subprocess", "exec(", "eval(",
    "pickle.loads", "shell=true",
}


def should_trigger_debate(text: str) -> bool:
    """Heuristica: hay keyword de riesgo en el texto?"""
    if not text:
        return False
    low = text.lower()
    return any(kw in low for kw in TRIGGER_KEYWORDS)


PROPOSER_SYSTEM = (
    "Eres ingeniero senior. Recibes una pieza de codigo o diseno y, si el "
    "Critic ha listado issues, debes REFACTORIZAR el codigo solucionando "
    "cada issue. Si no hay issues previos, solo confirma que el codigo es "
    "correcto. Responde SIEMPRE en JSON con este schema EXACTO:\n"
    '{"reasoning": "1-2 lineas", "refactored_code": "<codigo completo o null>"}'
)

CRITIC_SYSTEM = (
    "Eres auditor de seguridad senior. Recibes codigo (o diseno) y un foco "
    "de revision. Busca ACTIVAMENTE: SQL injection, command injection, "
    "race conditions, auth bypass, leak de secrets/tokens, side effects "
    "no documentados, falta de input validation, transacciones no atomicas, "
    "errores no manejados que dejen estado corrupto. Si encuentras issues, "
    "listalos en spanish con severity (critical|high|medium|low). Si el "
    "codigo es seguro responde issues=[]. JSON EXACTO:\n"
    '{"issues": [{"severity": "...", "description": "..."}],'
    ' "verdict": "approve|reject_needs_refactor"}'
)


def _ask_json(prompt: str, system: str, model: str = "claude-haiku-4-5-20251001",
               max_tokens: int = 1500) -> dict | None:
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_json
        return ask_claude_json(prompt, system=system, model=model,
                                max_tokens=max_tokens)
    except Exception as e:
        print(f"[debate] brain error: {e}", file=sys.stderr)
        return None


def debate(content: str, focus_areas: str = "",
            max_rounds: int = 2,
            model: str = "claude-haiku-4-5-20251001") -> dict:
    """Tribunal interno proposer-critic.

    Args:
      content: codigo o diseno a auditar.
      focus_areas: hint del foco del review (ej. "SQL injection en endpoint X").
      max_rounds: hard cap de iteraciones. Default 2.
      model: LLM. Haiku 4.5 default (rapido y barato).

    Returns:
      Dict con approved, rounds, issues_found, issues_resolved,
      final_code (si hubo refactor), reasoning.
    """
    if not content or len(content.strip()) < 10:
        return {"approved": False, "rounds": 0, "error": "content_too_short",
                "issues_found": [], "issues_resolved": []}

    issues_history: list[list[dict]] = []
    current_code = content
    rounds_done = 0
    last_reasoning = ""

    for r in range(1, max_rounds + 1):
        rounds_done = r
        # CRITIC review
        # Cap subido 2026-05-23 de 6000 -> 18000 tras dogfooding:
        # Haiku/Sonnet 200k tokens window aguanta bien. 6000 chars truncaba
        # archivos grandes y causaba 30-40% falsos positivos por contexto
        # incompleto.
        critic_prompt = (
            f"FOCO: {focus_areas or 'general security + correctness'}\n\n"
            f"CODIGO/DISENO:\n```\n{current_code[:18000]}\n```\n\n"
            "Audita rigurosamente. Si hay issues, listalos. Sino, verdict=approve."
        )
        critic_resp = _ask_json(critic_prompt, CRITIC_SYSTEM, model=model)
        if not critic_resp:
            return {"approved": False, "rounds": rounds_done,
                    "error": "critic_call_failed",
                    "issues_found": issues_history,
                    "issues_resolved": [],
                    "final_code": current_code if current_code != content else None}

        issues = critic_resp.get("issues") or []
        verdict = critic_resp.get("verdict", "reject_needs_refactor")
        issues_history.append(issues)

        if verdict == "approve" or not issues:
            return {
                "approved": True, "rounds": rounds_done,
                "issues_found": [i for round_issues in issues_history
                                  for i in round_issues],
                "issues_resolved": [i for round_issues in issues_history[:-1]
                                     for i in round_issues],
                "final_code": current_code if current_code != content else None,
                "reasoning": (
                    f"Critic approved en round {rounds_done}. "
                    f"{last_reasoning}"
                ).strip(),
            }

        # PROPOSER refactor
        issues_summary = "\n".join(
            f"  [{i.get('severity', '?')}] {i.get('description', '?')}"
            for i in issues
        )
        proposer_prompt = (
            f"FOCO: {focus_areas}\n\n"
            f"CODIGO ACTUAL:\n```\n{current_code[:18000]}\n```\n\n"
            f"ISSUES REPORTADOS POR CRITIC:\n{issues_summary}\n\n"
            "Refactoriza el codigo solucionando cada issue. Devuelve JSON con "
            "refactored_code (codigo completo)."
        )
        # max_tokens subido 3000 -> 8000: refactor de archivos grandes
        # se truncaba a mitad del JSON output (audit 2 reportaba JSON invalid).
        prop_resp = _ask_json(proposer_prompt, PROPOSER_SYSTEM,
                                model=model, max_tokens=8000)
        if not prop_resp:
            return {"approved": False, "rounds": rounds_done,
                    "error": "proposer_call_failed",
                    "issues_found": [i for ri in issues_history for i in ri]}

        last_reasoning = prop_resp.get("reasoning", "")
        new_code = prop_resp.get("refactored_code")
        if not new_code or new_code == current_code:
            # Proposer no produjo refactor util -> abort
            return {
                "approved": False, "rounds": rounds_done,
                "issues_found": [i for ri in issues_history for i in ri],
                "issues_resolved": [],
                "final_code": current_code,
                "reasoning": f"Proposer fallo refactor: {last_reasoning}",
            }
        current_code = new_code

    # Excedido max_rounds sin approve
    return {
        "approved": False, "rounds": rounds_done,
        "issues_found": [i for ri in issues_history for i in ri],
        "issues_resolved": [i for ri in issues_history[:-1] for i in ri],
        "final_code": current_code,
        "reasoning": (f"Max {max_rounds} rounds sin approve. "
                       f"Critic sigue reportando {len(issues_history[-1])} issues. "
                       f"{last_reasoning}"),
    }


def debate_if_risky(content: str, focus_hint: str = "",
                     **kwargs) -> dict:
    """Wrapper: solo debate si should_trigger_debate(). Si no, retorna
    approved=True instantaneo (sin LLM call)."""
    if not should_trigger_debate(content + " " + focus_hint):
        return {"approved": True, "rounds": 0,
                "skipped": "no_risk_keywords",
                "issues_found": [], "issues_resolved": [],
                "final_code": None}
    return debate(content, focus_areas=focus_hint, **kwargs)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Path a archivo .py o .sql a auditar")
    parser.add_argument("--text", help="Texto inline a auditar")
    parser.add_argument("--focus", default="general security + correctness")
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--auto", action="store_true",
                        help="Solo invoca debate si should_trigger_debate()")
    args = parser.parse_args()

    if args.file:
        content = Path(args.file).read_text(encoding="utf-8", errors="replace")
    elif args.text:
        content = args.text
    else:
        # Smoke test
        sample_vulnerable = (
            "def get_user(name):\n"
            "    q = f\"SELECT * FROM users WHERE name = '{name}'\"\n"
            "    return db.execute(q).fetchone()"
        )
        sample_safe = (
            "def get_user(name):\n"
            "    return db.execute("
            "        'SELECT * FROM users WHERE name = ?', (name,)).fetchone()"
        )
        print("=== Vulnerable sample (debe REJECT) ===")
        r1 = debate(sample_vulnerable, "SQL injection check")
        print(json.dumps({"approved": r1["approved"],
                          "rounds": r1["rounds"],
                          "issues_count": len(r1.get("issues_found", [])),
                          "has_refactor": bool(r1.get("final_code"))},
                          indent=2))
        print("\n=== Safe sample (debe APPROVE) ===")
        r2 = debate(sample_safe, "SQL injection check", max_rounds=1)
        print(json.dumps({"approved": r2["approved"],
                          "rounds": r2["rounds"],
                          "issues_count": len(r2.get("issues_found", []))},
                          indent=2))
        sys.exit(0)

    if args.auto:
        r = debate_if_risky(content, focus_hint=args.focus,
                              max_rounds=args.max_rounds)
    else:
        r = debate(content, focus_areas=args.focus,
                    max_rounds=args.max_rounds)
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
