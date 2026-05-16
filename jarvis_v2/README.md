# Jarvis v2 - Rewrite limpio

Reemplaza el enjambre v1 (24+ procesos polling) por una arquitectura event-driven con LangGraph state machine.

## Estructura

```
jarvis_v2/
  core/
    graph.py            LangGraph state machine: Plan -> Execute -> Verify -> Reflect
  sensor/
    set_of_mark.py      Set-of-Mark prompting (yellow labels + UIA tree)
  executor/             # FastAPI microservice en VM (futuro)
  memory/
    cerebro_rag.py      ChromaDB + sentence-transformers para vault Obsidian
  skills/               # Skills CLI-first (FFmpeg, YouTube API, etc)
  scripts/              # Indexers, migration tools
```

## Stack

- LangGraph + SqliteSaver (state + checkpoint en SQLite local)
- ChromaDB + all-MiniLM-L6-v2 (RAG sobre CerebroEmmanuel)
- pywinauto + Pillow (Set-of-Mark)
- Claude API via local proxy
- Porcupine (wake word, Day 6)

## Comandos

```bash
# Indexar vault
python -m jarvis_v2.memory.cerebro_rag index "C:/Users/Emmanuel/Documents/CerebroEmmanuel"

# Search semantico
python -m jarvis_v2.memory.cerebro_rag "Bot Forex spike catcher"

# Test SoM
python -m jarvis_v2.sensor.set_of_mark

# Ejecutar objetivo
python -m jarvis_v2.core.graph "abrir Bloc de Notas y escribir hola mundo"
```

## Roadmap

- [x] Day 1: Set-of-Mark + skeleton
- [x] Day 2: LangGraph state machine (Plan->Execute->Verify->Reflect)
- [x] Day 3: ChromaDB RAG indexer
- [ ] Day 4: YouTube API + FFmpeg/Remotion CLI skills
- [ ] Day 5: Reflexion pattern + Mem0
- [ ] Day 6: Porcupine wake word

## Diferencias con v1

| Aspecto | v1 (enjambre) | v2 (graph) |
|---------|---------------|------------|
| Procesos | 24+ python polling | 1 graph + 1 executor microservice |
| Estado | unified_context.json | SQLite checkpoint |
| Clicks | Claude vision % screen | Set-of-Mark numerados |
| Skills | JSON plano | DAG con pre/post conditions |
| Memoria | swarm_memory.jsonl | ChromaDB vector + Mem0 |
| Multi-step | hardcoded loops | LangGraph state machine |
| Voice | escribir prompt | Porcupine wake word |
| Aprendizaje | tutoriales YT | Reflexion sobre errores reales |
