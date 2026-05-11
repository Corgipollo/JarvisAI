#!/usr/bin/env bash
# UserPromptSubmit hook — captura correcciones del usuario como feedback
# Si el prompt contiene frases de correccion, las guarda en .feedback-log.jsonl
# para que grop-supervisor las revise y actualice los agentes/skills

FEEDBACK_LOG="$HOME/.claude/.feedback-log.jsonl"
INPUT=$(cat)

# Extraer el prompt del JSON
PROMPT=$(echo "$INPUT" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('prompt',''))" 2>/dev/null || echo "")
CWD=$(echo "$INPUT" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('cwd',''))" 2>/dev/null || echo "")

if [ -z "$PROMPT" ]; then
  exit 0
fi

# Patrones que indican correccion del usuario
CORRECTION_PATTERNS=(
  "no no"
  "no eso no"
  "te dije que"
  "ya te dije"
  "otra vez"
  "mal,"
  "estas mal"
  "no es asi"
  "deja de"
  "no hagas"
  "no uses"
  "mas conciso"
  "mas corto"
  "demasiado largo"
  "no expliques"
  "solo hazlo"
  "hazlo ya"
)

# Patrones que indican confirmacion (feedback positivo)
CONFIRMATION_PATTERNS=(
  "perfecto"
  "exacto"
  "asi esta bien"
  "eso es"
  "bien hecho"
  "sigue asi"
  "me gusta como"
)

CATEGORY=""
for p in "${CORRECTION_PATTERNS[@]}"; do
  if echo "$PROMPT" | grep -qi "$p"; then
    CATEGORY="correction"
    break
  fi
done

if [ -z "$CATEGORY" ]; then
  for p in "${CONFIRMATION_PATTERNS[@]}"; do
    if echo "$PROMPT" | grep -qi "$p"; then
      CATEGORY="confirmation"
      break
    fi
  done
fi

if [ -z "$CATEGORY" ]; then
  exit 0
fi

# Loggear
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
# Escapar el prompt para JSON (limitar a 500 chars)
PROMPT_ESCAPED=$(echo "$PROMPT" | head -c 500 | python -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo "\"\"")
CWD_ESCAPED=$(echo "$CWD" | python -c "import sys,json; print(json.dumps(sys.stdin.read()))" 2>/dev/null || echo "\"\"")

echo "{\"ts\":\"$TS\",\"category\":\"$CATEGORY\",\"prompt\":$PROMPT_ESCAPED,\"cwd\":$CWD_ESCAPED}" >> "$FEEDBACK_LOG"

exit 0