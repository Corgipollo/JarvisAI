"""poetiq_casero.py - Harness local de auto-mejora estilo Poetiq.

Idea: en vez de confiar en una sola respuesta del LLM, generamos N candidatos
(variando temperature o provider), un juez los puntua, y nos quedamos con el
ganador. Los patrones ganadores se persisten en data/poetiq_winners.jsonl para
que futuras llamadas se sesguen hacia lo que historicamente funciono.

Costo: $0. Usa el mismo fallback chain de jarvis_brain.
NO requiere API paga.

Uso:
    from jarvis_v2.core.poetiq_casero import casero
    from jarvis_v2.core.schemas import Plan

    plan = casero("Plan: instalar requirements y correr tests",
                   Plan, n=3, system="Eres planner...")

Cuando NO usar:
    - Decisiones triviales (costo de 3x calls > beneficio)
    - Acciones con side-effects irreversibles (usar CFO, no Poetiq)
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

ROOT = Path(__file__).resolve().parents[2]
WINNERS_LOG = ROOT / "data" / "poetiq_winners.jsonl"


def _log_winner(prompt: str, schema_name: str, winner: dict, score: float,
                rationale: str):
    """Persiste ganador para feedback loop futuro."""
    WINNERS_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "schema": schema_name,
        "prompt_hash": hash(prompt) & 0xFFFFFFFF,
        "prompt_head": prompt[:200],
        "winner": winner,
        "score": score,
        "rationale": rationale[:300],
    }
    with WINNERS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def _generate_candidates(prompt: str, schema_cls: Type[T], n: int,
                          system: str, model: str,
                          max_tokens: int) -> list[T]:
    """Genera N candidatos con variacion (temperatura implicita via reintentos)."""
    from jarvis_v2.core.llm_structured import llm_structured

    candidates: list[T] = []
    for i in range(n):
        # Variacion: prompt anotado con seed para que el LLM no de la misma respuesta
        seeded = (f"{prompt}\n\n"
                  f"[Variante {i+1}/{n}: explora una aproximacion diferente "
                  f"a las anteriores si las hay]")
        try:
            cand = llm_structured(seeded, schema_cls, system=system,
                                   model=model, max_tokens=max_tokens,
                                   max_retries=1)
            candidates.append(cand)
        except Exception as e:
            print(f"[poetiq] candidate {i+1} fallo: {e}", file=sys.stderr)
    return candidates


def _judge_candidates(prompt: str, candidates: list[T],
                       schema_name: str) -> tuple[int, float, str]:
    """LLM-as-judge: puntua candidatos. Devuelve (winner_idx, score, rationale)."""
    from jarvis_bridge.jarvis_brain import ask_claude_json

    if len(candidates) == 1:
        return 0, 1.0, "unico candidato"

    cards = "\n\n".join(
        f"### Candidato {i+1}\n```json\n"
        f"{c.model_dump_json(indent=2)}\n```"
        for i, c in enumerate(candidates)
    )
    judge_prompt = (
        f"Eres juez imparcial. Tarea original:\n{prompt}\n\n"
        f"Schema objetivo: {schema_name}\n\n"
        f"Candidatos:\n{cards}\n\n"
        f"Evalua cada uno por: (1) cumple objetivo, (2) viable, "
        f"(3) eficiente, (4) sin pasos redundantes.\n"
        f"Responde JSON: {{\"winner\": <1-{len(candidates)}>, "
        f"\"score\": <0.0-1.0>, \"rationale\": \"<por que>\"}}"
    )
    raw = ask_claude_json(
        judge_prompt,
        system="Juez tecnico. Respondes solo JSON. Sin preamble.",
        schema_hint=f"{{winner: int, score: float, rationale: str}}",
        max_tokens=500,
    )
    if not raw:
        return 0, 0.5, "judge sin respuesta, default cand 1"
    winner = int(raw.get("winner", 1)) - 1
    winner = max(0, min(winner, len(candidates) - 1))
    return winner, float(raw.get("score", 0.5)), str(raw.get("rationale", ""))


def casero(
    prompt: str,
    schema_cls: Type[T],
    n: int = 3,
    system: str = "",
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 2000,
    min_score: float = 0.6,
) -> T:
    """Genera N candidatos, juez los puntua, devuelve ganador.

    Args:
        n: numero de candidatos (3 = sweet spot costo/calidad).
        min_score: si el ganador puntua bajo esto, igual lo devuelve pero
                   loggea warning. (no falla — el caller decide).

    Raises:
        ValueError: si los N candidatos fallaron.
    """
    cands = _generate_candidates(prompt, schema_cls, n, system, model,
                                  max_tokens)
    if not cands:
        raise ValueError(f"Poetiq: 0/{n} candidatos validos para "
                         f"{schema_cls.__name__}")

    if len(cands) < n:
        print(f"[poetiq] solo {len(cands)}/{n} candidatos generados",
              file=sys.stderr)

    idx, score, rationale = _judge_candidates(prompt, cands,
                                               schema_cls.__name__)
    winner = cands[idx]
    if score < min_score:
        print(f"[poetiq] WARN winner score {score:.2f} < min {min_score}: "
              f"{rationale[:100]}", file=sys.stderr)

    _log_winner(prompt, schema_cls.__name__, winner.model_dump(),
                score, rationale)
    print(f"[poetiq] winner #{idx+1}/{len(cands)} score={score:.2f}",
          file=sys.stderr)
    return winner


def winners_summary(schema_name: str | None = None,
                     limit: int = 20) -> list[dict]:
    """Lee log de ganadores para analisis. Util para sesgar futuros prompts."""
    if not WINNERS_LOG.exists():
        return []
    rows = []
    with WINNERS_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if schema_name and entry.get("schema") != schema_name:
                    continue
                rows.append(entry)
            except json.JSONDecodeError:
                continue
    return rows[-limit:]


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    from jarvis_v2.core.schemas import Plan

    print("=== Poetiq Casero — demo ===")
    plan = casero(
        "Plan: descargar un archivo .zip de github y descomprimirlo en C:/tmp",
        Plan,
        n=3,
        system="Eres planner. Pasos atomicos. Estima spend_usd realista.",
    )
    print("\n=== GANADOR ===")
    print(plan.model_dump_json(indent=2))
    print("\n=== HISTORIAL ===")
    for w in winners_summary("Plan", limit=5):
        print(f"  {w['ts']} score={w['score']:.2f} — {w['rationale'][:80]}")
