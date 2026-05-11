#!/usr/bin/env bash
# Stop hook — valida que la respuesta de Claude termino con el bloque obligatorio
# de "Skills activadas / disponibles / siguiente paso"
# Si no, registra en .stop-violations.log para que grop-supervisor lo procese

set -o pipefail

INPUT=$(cat 2>/dev/null || echo '')
LOG_FILE="$HOME/.claude/.stop-violations.log"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Extraer el transcript path y session id del input
TRANSCRIPT=$(echo "$INPUT" | python -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(d.get('transcript_path',''))
except: print('')
" 2>/dev/null || echo "")

SESSION=$(echo "$INPUT" | python -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(d.get('session_id',''))
except: print('')
" 2>/dev/null || echo "")

if [ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ]; then
  exit 0
fi

# Leer el ULTIMO mensaje del assistant del transcript
LAST_MSG=$(python << PYEOF
import json
from pathlib import Path

p = Path("$TRANSCRIPT")
if not p.exists():
    raise SystemExit(0)

last_assistant = None
try:
    for line in p.read_text(encoding='utf-8').splitlines():
        try:
            d = json.loads(line)
            if d.get('type') == 'assistant':
                msg = d.get('message', {})
                content = msg.get('content', [])
                if isinstance(content, list):
                    text = ''.join(b.get('text','') for b in content if b.get('type') == 'text')
                else:
                    text = str(content)
                if text.strip():
                    last_assistant = text
        except: pass
except: pass

print(last_assistant or "")
PYEOF
)

# Validar que el ultimo mensaje del assistant tiene el bloque de cierre
HAS_BLOCK=0
if echo "$LAST_MSG" | grep -qE "Skills activadas" && \
   echo "$LAST_MSG" | grep -qE "Skills disponibles" && \
   echo "$LAST_MSG" | grep -qE "siguiente paso|Mejor siguiente"; then
  HAS_BLOCK=1
fi

# Si no tiene el bloque, loggear violacion
if [ "$HAS_BLOCK" -eq 0 ] && [ -n "$LAST_MSG" ]; then
  # Solo loggear si la respuesta es lo suficientemente larga para esperar el bloque
  MSG_LEN=$(echo "$LAST_MSG" | wc -c)
  if [ "$MSG_LEN" -gt 200 ]; then
    PROMPT_SNIP=$(echo "$LAST_MSG" | head -c 200 | tr '\n' ' ' | python -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo "\"\"")
    echo "{\"ts\":\"$TS\",\"session\":\"$SESSION\",\"missing\":\"closing-block\",\"snippet\":$PROMPT_SNIP}" >> "$LOG_FILE"
  fi
fi

exit 0