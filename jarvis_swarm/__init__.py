"""jarvis_swarm — 21 cerebros especializados conectados via Claude central.

Cada agente:
- Tiene UN trabajo específico (mouse, apps, errores, código, edición, etc.)
- Loop independiente en background
- Habla con Claude via jarvis_brain.ask_claude (memoria compartida persistente)
- Reporta a swarm_memory.jsonl para que otros agentes lo lean
- Coordinado por orchestrator.py

Filosofía: 21 cerebros pequeños > 1 monolito. Cada agente es <300 líneas.
"""
