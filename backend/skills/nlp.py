"""nlp.py — Vocabulario natural -> action plan.

"manda mensaje a Alejandro: reunion 5pm" -> JSON action sequence

Internamente usa ask_brain para traducir texto natural a plan ejecutable.
"""
from __future__ import annotations

import re

from backend.skills.ask_brain import jarvis_handle


# Patrones simples (regex) para tareas comunes — atajo sin LLM
QUICK_PATTERNS = [
    (r"^abrir?\s+(.+)$", lambda m: {"task": "open_app", "target": m.group(1).strip()}),
    (r"^cerrar?\s+(.+)$", lambda m: {"task": "close_app", "target": m.group(1).strip()}),
    (r"^busca\s+(.+)\s+en\s+(google|youtube|duckduckgo)", lambda m: {
        "task": "web_search", "query": m.group(1).strip(), "engine": m.group(2).lower()
    }),
    (r"^screenshot$|^captura\s+pantalla$", lambda m: {"task": "screenshot"}),
]


def parse_intent(text: str) -> dict:
    """Intenta clasificar con regex rapido. Si no matchea, devuelve None."""
    t = text.lower().strip()
    for pattern, builder in QUICK_PATTERNS:
        m = re.match(pattern, t)
        if m:
            return builder(m)
    return {"task": "unknown", "raw": text}


async def execute_natural(text: str) -> dict:
    """Pipeline: parse intent rapido -> si conocido ejecuta directo,
    si no -> jarvis_handle (LLM brain)."""
    intent = parse_intent(text)

    if intent["task"] == "open_app":
        from backend.integrations.pc_control import open_app
        return await open_app(intent["target"])

    if intent["task"] == "close_app":
        from backend.integrations.pc_control import close_app
        return await close_app(intent["target"])

    if intent["task"] == "web_search":
        from backend.skills.browser import quick_search
        return await quick_search(intent["query"], engine=intent.get("engine", "duckduckgo"))

    if intent["task"] == "screenshot":
        from backend.skills.vision import screenshot
        return screenshot()

    # Fallback: brain decide
    return await jarvis_handle(text)
