"""multi_agent_dialog.py — Multi-agent dialog para que Jarvis consulte sub-IAs.

Jarvis (agente principal) puede llamar a:
  - ANALYST (Claude Sonnet) — analiza datos/situaciones
  - CRITIC (Claude Sonnet con prompt critico) — desafia decisiones
  - RESEARCHER (Claude Sonnet con web search via Playwright) — investiga online
  - EXPERT (Claude Opus si necesario) — razonamiento profundo

Caso de uso típico:
  Jarvis: "tengo que decidir entre 3 opciones para X. Voy a consultar"
  → llama a ANALYST para pros/cons
  → llama a CRITIC para desafiar
  → decide basado en consenso
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
PROXY_URL = "http://127.0.0.1:8088"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


AGENT_PROFILES = {
    "ANALYST": {
        "model": "claude-sonnet-4-6",
        "system": """Eres ANALYST. Analizas situaciones objetivamente. Listas pros/cons,
identificas riesgos, sugieres opciones. NO decides, solo informas.
Output: JSON {pros: [...], cons: [...], options: [...], risks: [...]}
""",
    },
    "CRITIC": {
        "model": "claude-sonnet-4-6",
        "system": """Eres CRITIC. Tu trabajo es DESAFIAR la decisión propuesta. Encuentra
fallas, supuestos erroneos, casos extremos. Sé brutal pero constructivo.
Output: JSON {challenges: [...], blind_spots: [...], recommend_proceed: bool, reasoning: ""}
""",
    },
    "RESEARCHER": {
        "model": "claude-sonnet-4-6",
        "system": """Eres RESEARCHER. Investigas online. Si recibes una pregunta, primero
identificas qué información falta, después la buscas mentalmente (basado en tu
conocimiento) y devuelves hallazgos estructurados.
Output: JSON {findings: [...], sources_to_check: [...], confidence: 0.0-1.0}
""",
    },
    "EXPERT": {
        "model": "claude-sonnet-4-6",
        "system": """Eres EXPERT. Tu trabajo es razonar profundamente sobre problemas complejos.
Piensas paso a paso, consideras múltiples ángulos, y das una recomendación final
fundamentada con tu reasoning.
Output: JSON {analysis: "...", recommendation: "...", confidence: 0.0-1.0, reasoning_steps: [...]}
""",
    },
}


def call_agent(agent_name: str, user_message: str, context: dict | None = None) -> dict:
    """Llama a un sub-agente. Devuelve su response parseado."""
    profile = AGENT_PROFILES.get(agent_name.upper())
    if not profile:
        return {"error": f"agente desconocido: {agent_name}"}

    full_user = user_message
    if context:
        full_user = f"CONTEXT:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\nQUESTION:\n{user_message}"

    try:
        r = requests.post(
            f"{PROXY_URL}/v1/messages",
            json={
                "model": profile["model"],
                "system": profile["system"],
                "messages": [{"role": "user", "content": full_user}],
                "max_tokens": 2000,
            },
            timeout=180,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"]
    except Exception as e:
        return {"error": str(e)}

    # Extract JSON if present
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        try:
            parsed = json.loads(m.group(0))
            parsed["_agent"] = agent_name
            return parsed
        except json.JSONDecodeError:
            pass
    return {"_agent": agent_name, "raw_text": text}


def consult_panel(question: str, context: dict | None = None,
                  agents: list[str] = None) -> dict:
    """Consulta panel multi-agente. Devuelve dict con response de cada uno + síntesis."""
    if agents is None:
        agents = ["ANALYST", "CRITIC", "EXPERT"]

    print(f"[panel] consultando {len(agents)} agentes sobre: {question[:80]}", flush=True)
    responses = {}
    for agent in agents:
        print(f"  → {agent} pensando...", flush=True)
        responses[agent] = call_agent(agent, question, context)

    # Síntesis final con un meta-agent que reúne todo
    synthesis_prompt = (
        f"PREGUNTA ORIGINAL: {question}\n\n"
        f"RESPUESTAS DEL PANEL:\n"
        + "\n\n".join(f"=== {k} ===\n{json.dumps(v, ensure_ascii=False, indent=2)}"
                      for k, v in responses.items())
        + "\n\nSintetiza el consenso del panel. Output JSON: "
        f"{{decision: 'concrete action', confidence: 0.0-1.0, "
        f"key_points: [...], dissent: 'donde no estuvieron de acuerdo'}}"
    )
    print("  → SINTESIS final...", flush=True)
    synthesis = call_agent("EXPERT", synthesis_prompt)

    return {
        "question": question,
        "responses": responses,
        "synthesis": synthesis,
        "ts": datetime.now().isoformat(),
    }


def log_dialog(panel_result: dict):
    log_file = ROOT / "data" / "multi_agent_dialogs.jsonl"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(panel_result, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "Debo aprender CapCut o Premiere Pro primero?"
    )
    result = consult_panel(question)
    log_dialog(result)
    print("\n=== SINTESIS ===")
    print(json.dumps(result["synthesis"], ensure_ascii=False, indent=2))
