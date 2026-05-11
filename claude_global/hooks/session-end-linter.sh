#!/usr/bin/env bash
# SessionEnd hook — ejecuta agnix linter una vez por dia y guarda reporte
# Si encuentra errores, deja una nota visible en ~/.claude/.lint-report.txt

LAST_LINT_FILE="$HOME/.claude/.last-lint-date"
REPORT_FILE="$HOME/.claude/.lint-report.txt"
TODAY=$(date +%Y-%m-%d)

# Si ya se ejecuto hoy, salir
if [ -f "$LAST_LINT_FILE" ] && [ "$(cat "$LAST_LINT_FILE")" = "$TODAY" ]; then
  exit 0
fi

# Ejecutar agnix solo en MIS archivos (no plugins externos)
{
  echo "=== Lint del setup Claude — $TODAY ==="
  echo ""
  echo "--- Skill obsidian-vault ---"
  npx -y agnix@latest "$HOME/.claude/skills/obsidian-vault" --locale es 2>/dev/null | grep -E "(error|warning|Encontrados)" || echo "OK"
  echo ""
  echo "--- Agentes ---"
  npx -y agnix@latest "$HOME/.claude/agents" --locale es 2>/dev/null | grep -E "(error|warning|Encontrados)" || echo "OK"
  echo ""
  echo "--- CLAUDE.md size ---"
  LINES=$(wc -l < "$HOME/.claude/CLAUDE.md")
  if [ "$LINES" -gt 200 ]; then
    echo "ALERTA: CLAUDE.md tiene $LINES lineas (>200, Claude empieza a ignorar)"
  else
    echo "OK: $LINES lineas (<200)"
  fi
} > "$REPORT_FILE" 2>&1

echo "$TODAY" > "$LAST_LINT_FILE"
exit 0