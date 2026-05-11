#!/usr/bin/env bash
# SessionEnd hook — backup semanal de ~/.claude/ a un zip
# Solo corre una vez por semana (lunes o el primer dia de la semana detectado)

LAST_BACKUP_FILE="$HOME/.claude/.last-weekly-backup"
BACKUPS_DIR="$HOME/.claude/backups"
TODAY=$(date +%Y-%m-%d)
WEEK=$(date +%Y-W%V)

# Si ya se hizo backup esta semana, salir
if [ -f "$LAST_BACKUP_FILE" ] && [ "$(cat "$LAST_BACKUP_FILE")" = "$WEEK" ]; then
  exit 0
fi

# Crear backup
mkdir -p "$BACKUPS_DIR"
ZIP_NAME="weekly-${TODAY}.zip"
ZIP_PATH="$BACKUPS_DIR/$ZIP_NAME"

# Empacar todo lo importante (excluir backups previos y telemetria pesada)
cd "$HOME/.claude" && \
  tar -czf "${ZIP_PATH%.zip}.tar.gz" \
    --exclude='backups' \
    --exclude='shell-snapshots' \
    --exclude='sessions' \
    --exclude='telemetry' \
    --exclude='projects/*/conversations' \
    --exclude='.usage.jsonl*' \
    --exclude='plugins/marketplaces' \
    CLAUDE.md \
    *.md \
    settings.json \
    skills/ \
    agents/ \
    agent-memory/ \
    hooks/ \
    evals/ \
    commands/ \
    rag-vault/ \
    2>/dev/null || true

if [ -f "${ZIP_PATH%.zip}.tar.gz" ]; then
  echo "$WEEK" > "$LAST_BACKUP_FILE"

  # Limpiar backups antiguos (>4 semanas)
  find "$BACKUPS_DIR" -name "weekly-*.tar.gz" -mtime +28 -delete 2>/dev/null || true

  # Tamano del backup
  SIZE=$(stat -c %s "${ZIP_PATH%.zip}.tar.gz" 2>/dev/null || stat -f %z "${ZIP_PATH%.zip}.tar.gz" 2>/dev/null || echo 0)
  SIZE_KB=$((SIZE / 1024))

  # Log
  echo "[$(date)] Weekly backup OK: ${ZIP_PATH%.zip}.tar.gz (${SIZE_KB}KB)" >> "$HOME/.claude/.backup.log"
fi

exit 0