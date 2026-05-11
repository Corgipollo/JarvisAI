#!/usr/bin/env bash
# PostToolUse hook — loggea uso de tools a ~/.claude/.usage.jsonl
# Para saber que skills/agentes/MCPs uso de verdad vs los que solo tengo instalados

USAGE_FILE="$HOME/.claude/.usage.jsonl"
INPUT=$(cat)

# Extraer tool_name y timestamp
TOOL=$(echo "$INPUT" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name','?'))" 2>/dev/null || echo "?")
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Si es un MCP tool, extraer el server
if [[ "$TOOL" == mcp__* ]]; then
  SERVER=$(echo "$TOOL" | sed 's/mcp__\([^_]*\)__.*/\1/')
  echo "{\"ts\":\"$TS\",\"tool\":\"$TOOL\",\"type\":\"mcp\",\"server\":\"$SERVER\"}" >> "$USAGE_FILE"
else
  echo "{\"ts\":\"$TS\",\"tool\":\"$TOOL\",\"type\":\"native\"}" >> "$USAGE_FILE"
fi

# Rotar log si pasa de 10MB
if [ -f "$USAGE_FILE" ]; then
  SIZE=$(stat -c %s "$USAGE_FILE" 2>/dev/null || stat -f %z "$USAGE_FILE" 2>/dev/null || echo 0)
  if [ "$SIZE" -gt 10485760 ]; then
    mv "$USAGE_FILE" "${USAGE_FILE}.$(date +%Y%m%d)"
  fi
fi

exit 0