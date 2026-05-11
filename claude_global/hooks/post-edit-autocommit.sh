#!/usr/bin/env bash
# PostToolUse auto-commit hook v2 — inteligente, seguro, semantico
# Se ejecuta despues de Write/Edit/NotebookEdit.
# Mejoras vs v1:
#   - Counter por-vault (no global)
#   - Valida que el file_path editado pertenece al vault
#   - Opt-out via ~/.claude/.autocommit-pause
#   - Cooldown temporal entre commits
#   - Validacion de branch permitido
#   - Skip en solo-whitespace/CRLF (git diff --numstat)
#   - ABORT si detecta archivos fantasma del bash roto
#   - Staging selectivo con exclusions (.env, *.key, credentials, .swarm/memory.db)
#   - Mensaje semantico por categoria de carpetas
#   - Auto-push opcional
#   - Logging en ~/.claude/.autocommit.log
#   - Respeta pre-commit hooks (no usa --no-verify)

set -o pipefail

# ---------- Config ----------
VAULT="/c/Users/Emmanuel/Documents/CerebroEmmanuel"
VAULT_NAME=$(basename "$VAULT")
COUNTER_FILE="$HOME/.claude/.autocommit-counter-$VAULT_NAME"
LOG_FILE="$HOME/.claude/.autocommit.log"
PAUSE_FILE="$HOME/.claude/.autocommit-pause"
LAST_COMMIT_FILE="$HOME/.claude/.autocommit-lastts-$VAULT_NAME"
THRESHOLD=20
COOLDOWN_SECONDS=300              # 5 min entre auto-commits
AUTO_PUSH=true
ALLOWED_BRANCHES="master main"

INPUT=$(cat 2>/dev/null || echo '')

log() {
  echo "[$(date +%Y-%m-%dT%H:%M:%S)] $*" >> "$LOG_FILE"
}

# ---------- 0. Opt-out ----------
if [ -f "$PAUSE_FILE" ]; then
  exit 0
fi

# ---------- 1. Validar que la edicion fue en el vault ----------
FILE_PATH=$(echo "$INPUT" | python -c "
import sys,json
try:
    d=json.load(sys.stdin)
    ti=d.get('tool_input',{})
    print(ti.get('file_path') or ti.get('notebook_path') or '')
except Exception:
    print('')
" 2>/dev/null || echo "")

# Si hay path y NO pertenece al vault, salir sin incrementar counter
if [ -n "$FILE_PATH" ]; then
  case "$FILE_PATH" in
    *CerebroEmmanuel*) : ;;  # OK, sigue
    *) exit 0 ;;
  esac
fi

# ---------- 2. Incrementar counter ----------
COUNT=$(cat "$COUNTER_FILE" 2>/dev/null || echo 0)
COUNT=$((COUNT + 1))
echo "$COUNT" > "$COUNTER_FILE"

if [ "$COUNT" -lt "$THRESHOLD" ]; then
  exit 0
fi

# ---------- 3. Cooldown temporal ----------
NOW=$(date +%s)
LAST_TS=$(cat "$LAST_COMMIT_FILE" 2>/dev/null || echo 0)
if [ "$((NOW - LAST_TS))" -lt "$COOLDOWN_SECONDS" ]; then
  # No reset del counter — se queda "cargado" hasta que pase el cooldown
  exit 0
fi

# ---------- 4. Reset counter ----------
echo 0 > "$COUNTER_FILE"

# ---------- 5. Validar repo ----------
cd "$VAULT" 2>/dev/null || { log "SKIP: no cd al vault"; exit 0; }
if ! git rev-parse --git-dir > /dev/null 2>&1; then
  log "SKIP: no es repo git"
  exit 0
fi

# ---------- 6. Validar branch permitido ----------
BRANCH=$(git branch --show-current 2>/dev/null || echo "?")
BRANCH_OK=0
for b in $ALLOWED_BRANCHES; do
  [ "$BRANCH" = "$b" ] && BRANCH_OK=1
done
if [ "$BRANCH_OK" -ne 1 ]; then
  log "SKIP: branch '$BRANCH' no esta en allowed ($ALLOWED_BRANCHES)"
  exit 0
fi

# ---------- 7. Contar cambios reales (excluye solo-whitespace) ----------
REAL_MODIFIED=$(git diff --numstat 2>/dev/null | awk '$1+$2 > 0' | wc -l | tr -d ' ')
STAGED=$(git diff --cached --numstat 2>/dev/null | wc -l | tr -d ' ')
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')
TOTAL=$((REAL_MODIFIED + STAGED + UNTRACKED))

if [ "$TOTAL" -eq 0 ]; then
  log "SKIP: sin cambios reales"
  exit 0
fi

# ---------- 8. Detectar archivos fantasma ----------
GHOST=$(git status --porcelain 2>/dev/null | awk '{print $NF}' | \
  grep -E '^([!{}$+,\-]|[0-9]+[),.%]?$|[a-z_]+\.(includes|stat|url|type)\()' | head -1)
if [ -n "$GHOST" ]; then
  log "ABORT: archivos fantasma detectados (ej: $GHOST) — limpiar manual"
  exit 0
fi

# ---------- 9. Generar mensaje semantico ----------
CHANGED_LIST=$(git status --porcelain 2>/dev/null | awk '{print $NF}')
CATS=""
echo "$CHANGED_LIST" | grep -q '^01-Proyectos/'   && CATS="$CATS proyectos"
echo "$CHANGED_LIST" | grep -q '^02-Tecnico/'     && CATS="$CATS tecnico"
echo "$CHANGED_LIST" | grep -q '^03-Conocimiento/' && CATS="$CATS conocimiento"
echo "$CHANGED_LIST" | grep -q '^04-Diario/'      && CATS="$CATS diario"
echo "$CHANGED_LIST" | grep -q '^07-Codigo/'      && CATS="$CATS codigo"
echo "$CHANGED_LIST" | grep -q '\.mcp\.json'      && CATS="$CATS mcp"
echo "$CHANGED_LIST" | grep -q '^CLAUDE\.md$'     && CATS="$CATS claude-md"
[ -z "$CATS" ] && CATS=" misc"

TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
MSG_TITLE="Auto-commit:$CATS — $TOTAL cambios ($TIMESTAMP)"

# ---------- 10. Staging selectivo (excluye sensibles) ----------
git add -A -- \
  ':!*.env' \
  ':!*.env.*' \
  ':!*credentials*' \
  ':!*.key' \
  ':!id_rsa*' \
  ':!**/node_modules/**' \
  ':!.swarm/memory.db' \
  ':!**/*.pid' \
  > /dev/null 2>&1

# Re-check: puede que staging quedara vacio por exclusions
STAGED_FINAL=$(git diff --cached --numstat 2>/dev/null | wc -l | tr -d ' ')
if [ "$STAGED_FINAL" -eq 0 ]; then
  log "SKIP: staging vacio despues de exclusions"
  exit 0
fi

# ---------- 11. Commit (respeta pre-commit hooks) ----------
COMMIT_OUT=$(git commit -m "$MSG_TITLE

Auto-commit hook v2 despues de $THRESHOLD ediciones significativas.
Branch: $BRANCH | Cambios staged: $STAGED_FINAL | Categorias:$CATS

Co-Authored-By: claude-flow <ruv@ruv.net>" 2>&1)
COMMIT_RC=$?

if [ "$COMMIT_RC" -eq 0 ]; then
  HASH=$(git rev-parse --short HEAD)
  log "OK: commit $HASH en $BRANCH ($STAGED_FINAL staged)$CATS"
  echo "$NOW" > "$LAST_COMMIT_FILE"

  # ---------- 12. Auto-push opcional ----------
  if [ "$AUTO_PUSH" = "true" ]; then
    if git push origin "$BRANCH" > /dev/null 2>&1; then
      log "PUSH: ok $HASH -> origin/$BRANCH"
      # Telegram notif de push exitoso (fire and forget)
      if [ -f "$HOME/.claude/.telegram-config" ]; then
        bash "$HOME/.claude/tier5/notifs/telegram-notify.sh" "Auto-commit $HASH pushed: $STAGED_FINAL archivos en$CATS" info &
      fi
    else
      log "PUSH: FAIL $HASH (commit local OK, push manual necesario)"
      if [ -f "$HOME/.claude/.telegram-config" ]; then
        bash "$HOME/.claude/tier5/notifs/telegram-notify.sh" "Auto-commit $HASH local OK pero push FALLO en $BRANCH" warn &
      fi
    fi
  fi
else
  log "COMMIT FAIL rc=$COMMIT_RC: $(echo "$COMMIT_OUT" | tail -3 | tr '\n' ' ')"
  if [ -f "$HOME/.claude/.telegram-config" ]; then
    bash "$HOME/.claude/tier5/notifs/telegram-notify.sh" "Auto-commit FALLO en $BRANCH ($STAGED_FINAL staged)" critical &
  fi
fi

exit 0