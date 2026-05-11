#!/usr/bin/env bash
# PreToolUse hook — rechaza comandos Bash con patrones peligrosos
# Categorias: archivos fantasma, destructivos, secrets en logs
# Recibe JSON por stdin: {tool_name, tool_input: {command, ...}}

set -e

INPUT=$(cat)

# Solo validar si es Bash
TOOL_NAME=$(echo "$INPUT" | grep -oE '"tool_name"\s*:\s*"[^"]+"' | sed 's/.*"\([^"]*\)"$/\1/' || echo "")
if [ "$TOOL_NAME" != "Bash" ]; then
  exit 0
fi

# Extraer el comando
CMD=$(echo "$INPUT" | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null || echo "")

if [ -z "$CMD" ]; then
  exit 0
fi

# === PATRONES BLOQUEADOS ===

# 1. ARCHIVOS FANTASMA (brace expansion roto, redirecciones con expresiones JS/Python)
GHOST_PATTERNS=(
  '\{,\+'                                    # {,+
  '\{,\-'                                    # {,-
  '> *\$[a-zA-Z0-9]'                         # > $var sin quoting, > $50K
  '> *![a-zA-Z_]'                            # > !f.includes(...)
  '> *\{[a-zA-Z_]'                           # > {new_sl, > {p
  '> *[a-zA-Z_][a-zA-Z0-9_]*\.[a-z]*\('      # > algo.includes( / .stat( / .url( / .type(
  '> *[a-zA-Z_][a-zA-Z0-9_]*Start([^a-z])'   # > todayStart
  '> *[a-zA-Z_][a-zA-Z0-9_]*\[[0-9]'         # > array[0], > r4['trades']
  '> *Optional\['                            # > Optional[str]
  '> *[0-9]+[),.%]'                          # > 10), > 25%, > 3000.
  '> *[a-zA-Z_]+_[a-zA-Z_]+ *$'              # > test_start (palabras con _ al final sin quoting)
  '2>&1 *> *\$'                              # 2>&1 > $var (doble redireccion rota)
)

# 2. DESTRUCTIVOS sin confirmacion explicita
DESTRUCTIVE_PATTERNS=(
  'rm +-rf? +/(etc|var|usr|bin|boot|sbin|lib|root|sys|proc|home)(/|$| )'  # rm -rf /etc, /home, etc
  'rm +-rf? +/$'                 # rm -rf /
  'rm +-rf? +~ *$'               # rm -rf ~
  'rm +-rf? +\*'                 # rm -rf *
  ':\(\)\{ *:\|:& *\}'           # fork bomb
  'mkfs\.'                       # formatear disco
  'dd +if=/dev/(zero|random|urandom).*of=/dev/[sh]d' # wipe disk
  '> */dev/sd[a-z]'              # write to disk
  'chmod +-R +777 +/'            # chmod 777 root
)

# 3. FORCE PUSH a master/main
FORCE_PUSH_PATTERNS=(
  'git +push +.*--force.*\b(master|main)\b'
  'git +push +-f +.*\b(master|main)\b'
)

# 4. SECRETS EN LOGS (cat de .env a stdout)
SECRET_PATTERNS=(
  'cat +.*\.env([^a-zA-Z]|$)'
  'cat +.*\.credentials'
  'cat +.*\.aws/credentials'
  'cat +.*id_rsa([^.]|$)'
)

check_patterns() {
  local category="$1"
  shift
  local patterns=("$@")
  for pattern in "${patterns[@]}"; do
    if echo "$CMD" | grep -qE "$pattern"; then
      cat <<EOF >&2
BLOCKED [$category]: comando Bash contiene patron prohibido.
Patron: $pattern
Comando: $CMD

EOF
      case "$category" in
        GHOST)
          echo "Causa: bash brace expansion o redireccion con expresion JS/Python sin quoting." >&2
          echo "Fix: encierra esos caracteres entre comillas dobles." >&2
          ;;
        DESTRUCTIVE)
          echo "Causa: comando destructivo sin path especifico." >&2
          echo "Fix: especifica una ruta concreta y confirma con el usuario antes." >&2
          ;;
        FORCE_PUSH)
          echo "Causa: force push a rama protegida." >&2
          echo "Fix: pide confirmacion explicita antes de force push a master/main." >&2
          ;;
        SECRET)
          echo "Causa: cat de archivo con secretos a stdout (queda en logs)." >&2
          echo "Fix: usa grep para extraer solo la variable que necesitas." >&2
          ;;
      esac
      exit 2
    fi
  done
}

check_patterns "GHOST" "${GHOST_PATTERNS[@]}"
check_patterns "DESTRUCTIVE" "${DESTRUCTIVE_PATTERNS[@]}"
check_patterns "FORCE_PUSH" "${FORCE_PUSH_PATTERNS[@]}"
check_patterns "SECRET" "${SECRET_PATTERNS[@]}"

exit 0