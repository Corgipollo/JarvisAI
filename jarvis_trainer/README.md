# Jarvis Trainer — Sandbox + Loop + Memoria de Errores

Sistema mínimo de entrenamiento de Jarvis. Ejecuta tareas (`tasks.yaml`),
registra qué estrategia funciona para cada una, persiste errores y
aprende cuál estrategia es mejor para cada acción.

## Arquitectura

```
jarvis_trainer/
├── tasks.yaml              # curriculum (12 tareas)
├── trainer.py              # loop principal
├── memory.py               # persistencia jsonl
├── sandbox.py              # SANDBOX_MODE wrapper
├── setup_scheduled_task.ps1  # cron Windows
└── README.md

data/
├── jarvis_errors.jsonl     # log de fallos
├── jarvis_learnings.jsonl  # log de éxitos (qué estrategia ganó)
├── jarvis_runs.jsonl       # resumen de cada corrida
└── jarvis_sandbox.jsonl    # log de acciones que se SIMULARON
```

## Modos

| Modo | Comportamiento |
|------|----------------|
| **Sandbox (default)** | `JARVIS_SANDBOX=1`. NO toca apps reales del usuario, solo registra "habría hecho X". Seguro para correr 24/7. |
| **Real** | `JARVIS_SANDBOX=0`. Ejecuta acciones de verdad (abre/cierra apps). Solo correr manualmente cuando uno quiera. |

## Uso manual

```bash
# Sandbox (default — no toca tus apps)
python jarvis_trainer/trainer.py

# Real (sí abre apps)
JARVIS_SANDBOX=0 python jarvis_trainer/trainer.py    # bash
$env:JARVIS_SANDBOX='0'; python jarvis_trainer/trainer.py  # powershell

# Ver aprendizajes acumulados
python jarvis_trainer/memory.py
```

## Always-on (Windows Scheduled Task)

```powershell
# Una vez (no requiere admin):
cd C:\Users\Emmanuel\Documents\JarvisAI\jarvis_trainer
.\setup_scheduled_task.ps1
```

Después corre cada 30 min en sandbox mode, indefinidamente.
Logs acumulan en `data/jarvis_*.jsonl` y memory.summarize_learnings()
empieza a tener stats.

## Comandos útiles

```powershell
# Ver task
Get-ScheduledTask -TaskName 'Jarvis Trainer'

# Forzar run ahora
Start-ScheduledTask -TaskName 'Jarvis Trainer'

# Eliminar
Unregister-ScheduledTask -TaskName 'Jarvis Trainer' -Confirm:$false
```

## Qué aprende

Para cada `task.id`, después de N runs, sabe:
- Cuál estrategia gana más (start_menu_search vs inventory_app_paths vs protocol)
- Tasa de éxito histórica
- Tiempo promedio de cada estrategia
- Errores recurrentes (en `jarvis_errors.jsonl`)

Después `memory.recommend_strategy(task)` puede ser usado por `pc_control`
para PRIORIZAR la estrategia históricamente ganadora — feedback loop real.

## TIER 2 (no implementado, no pedido)

- Reinforcement learning sobre la elección de estrategia
- Auto-curriculum (genera tareas nuevas a partir de fallos)
- Sandbox real Windows (Windows Sandbox `.wsb` config aislado)
- Métricas dashboard FastAPI

## Status

2026-05-09 — V1 implementado: trainer + memoria + sandbox flag + scheduled task PS1.
