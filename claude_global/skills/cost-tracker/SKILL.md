---
name: cost-tracker
description: Use when the user asks cuanto gaste, cuanto llevo de API, cost tracking, budget, tokens used, o cuando quiere saber el gasto de Claude/Anthropic API por sesion o acumulado. Reads session telemetry and transcripts to calculate token usage and estimated cost, alerts when approaching monthly budget.
---

# Cost Tracker — Claude API spend

> Skill para trackear cuanto gasta Emmanuel en API de Claude/Anthropic.

## Cuando activar

- "cuanto llevo gastado"
- "cost tracker", "cuanto he pagado de tokens"
- "budget", "presupuesto mensual"
- "que modelo es mas caro"
- "estoy cerca del limite"

## Datos disponibles

1. **Session transcripts** en `~/.claude/projects/*/*.jsonl`
2. **Telemetria** en `~/.claude/.usage.jsonl` (si el hook post-tool-telemetry esta activo)
3. **Telemetria oficial** en `~/.claude/telemetry/*.json`

## Precios Claude (Nov 2025 — actualizar si cambia)

| Modelo | Input /1M | Output /1M |
|--------|-----------|------------|
| Opus 4.6 | $15 | $75 |
| Sonnet 4.6 | $3 | $15 |
| Haiku 4.5 | $0.80 | $4 |

## Workflow

### "cuanto llevo gastado hoy"
1. Read session files con timestamp de hoy
2. Parsear `usage.input_tokens` y `usage.output_tokens` de cada mensaje
3. Multiplicar por precio del modelo
4. Reportar: **total del dia** + **breakdown por modelo**

### "cuanto llevo este mes"
1. Iterar sobre session files desde dia 1 del mes
2. Agregar tokens por modelo
3. Reportar total + alerta si supera budget

### "que modelo uso mas"
1. Contar frecuencia de cada modelo en transcripts
2. Reportar distribucion con tokens asociados
3. Sugerir optimizaciones (ej: si Opus domina pero la tarea era simple, recomendar Sonnet)

## Budget por default

```
Budget mensual: $200 USD
Alerta: 75% ($150)
Critico: 90% ($180)
```

Configurable en `~/.claude/.budget.json`:
```json
{
  "monthly_usd": 200,
  "alert_pct": 75,
  "critical_pct": 90
}
```

## Formato de reporte

```
Claude API — costo acumulado

Dia 2026-04-07:
  Opus 4.6    input:  125,340 tokens  $1.88
              output:  18,200 tokens  $1.37
  Sonnet 4.6  input:   80,100 tokens  $0.24
              output:  12,500 tokens  $0.19
  ---
  Total dia: $3.68

Mes (acumulado): $47.23 / $200 (24%) OK
```

## Bash snippet (para invocacion directa)

```bash
# Script helper (~/.claude/scripts/cost-today.py) — generar bajo demanda
python - <<'EOF'
import json, glob, os
from pathlib import Path
from datetime import date

PRICES = {
    "claude-opus-4-6": (15, 75),
    "claude-sonnet-4-6": (3, 15),
    "claude-haiku-4-5": (0.80, 4),
}

today = date.today().isoformat()
sessions = Path.home() / ".claude" / "projects"
total_in, total_out = 0, 0
breakdown = {}

for f in sessions.rglob("*.jsonl"):
    try:
        for line in f.read_text(encoding="utf-8").splitlines():
            d = json.loads(line)
            ts = d.get("timestamp", "")
            if not ts.startswith(today):
                continue
            usage = d.get("message", {}).get("usage", {})
            model = d.get("message", {}).get("model", "?")
            in_t = usage.get("input_tokens", 0)
            out_t = usage.get("output_tokens", 0)
            if model not in breakdown:
                breakdown[model] = [0, 0]
            breakdown[model][0] += in_t
            breakdown[model][1] += out_t
    except Exception:
        continue

print(f"Dia {today}:")
total = 0
for model, (inp, out) in breakdown.items():
    for key, prices in PRICES.items():
        if key in model:
            cost = (inp / 1_000_000 * prices[0]) + (out / 1_000_000 * prices[1])
            total += cost
            print(f"  {model}: in={inp:,} out={out:,} = ${cost:.2f}")
print(f"Total dia: ${total:.2f}")
EOF
```