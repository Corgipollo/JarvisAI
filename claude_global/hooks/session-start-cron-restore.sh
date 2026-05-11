#!/bin/bash
# session-start-cron-restore.sh
# Recuerda a Claude que debe recrear los crones del v8-claude-supervisor al inicio de cada sesion.
# Via: inyeccion de mensaje de sistema en el transcript.

set -e

# Solo dispara si el vault CerebroEmmanuel esta en la sesion actual
CWD="${CLAUDE_PROJECT_DIR:-$PWD}"
case "$CWD" in
  *CerebroEmmanuel*)
    ;;
  *)
    exit 0
    ;;
esac

# Marker file: solo dispara si los crones no estan vivos
MARKER="/c/Users/Emmanuel/.claude/.crons-v8supervisor-active"

# Si marker existe Y tiene menos de 6 dias, los crones siguen vivos
if [ -f "$MARKER" ]; then
  AGE_SEC=$(( $(date +%s) - $(stat -c %Y "$MARKER") ))
  MAX_AGE=$((6*24*60*60))  # 6 dias
  if [ "$AGE_SEC" -lt "$MAX_AGE" ]; then
    exit 0
  fi
fi

# Emitir mensaje para que Claude recree los crones
cat <<'EOF'
[SYSTEM AUTO-NOTICE] Los crones de v8-claude-supervisor pueden haber expirado (session-only limit o 7-day auto-expire). Por favor ejecuta AHORA:

CronCreate:
1. cron="17 * * * *" durable=true recurring=true prompt="Ejecuta hourly-check del v8-claude-supervisor leyendo C:/Users/Emmanuel/Documents/v8-claude-supervisor/routines/hourly-check.md"
2. cron="57 15 * * 0" durable=true recurring=true prompt="Ejecuta weekly-review del v8-claude-supervisor leyendo C:/Users/Emmanuel/Documents/v8-claude-supervisor/routines/weekly-review.md"

Despues de crearlos, toca el marker: touch "/c/Users/Emmanuel/.claude/.crons-v8supervisor-active"
EOF