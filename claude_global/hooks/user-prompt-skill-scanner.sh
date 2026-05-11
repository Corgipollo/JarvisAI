#!/usr/bin/env bash
# UserPromptSubmit hook v3 — matching REAL contra skills-map.md con FUZZY support
# Lee el prompt, normaliza (lowercase, sin acentos, sin puntuacion),
# extrae keywords de la tabla de skills-map.md, hace match exacto + fuzzy (typos cortos),
# y devuelve las skills candidatas al context de Claude.

# Path: siempre usar path Windows para Python compatibility
SKILLS_MAP_BASH="$HOME/.claude/skills-map.md"
SKILLS_MAP_WIN="C:/Users/Emmanuel/.claude/skills-map.md"
# Usamos el Windows path para el Python block mas abajo
SKILLS_MAP="$SKILLS_MAP_WIN"
INPUT=$(cat 2>/dev/null || echo '')

# Extraer prompt del JSON
PROMPT=$(echo "$INPUT" | python -c "
import sys,json
try:
    d=json.load(sys.stdin)
    print(d.get('prompt',''))
except: print('')
" 2>/dev/null || echo "")

if [ -z "$PROMPT" ] || [ ! -f "$SKILLS_MAP" ]; then
  cat <<'EOF'
<system-reminder>
SKILL SCANNER: consulta ~/.claude/skills-map.md y usa las skills relevantes.
Auto-Prompt Enhancer: expande el mensaje antes de ejecutar.
Ruflo: avisa en cada respuesta.
</system-reminder>
EOF
  exit 0
fi

# Usamos Python para normalizar + matching fuzzy (mas robusto que bash puro)
MATCHES=$(python << PYEOF
import sys, re, unicodedata

# Normalizar prompt
prompt = """$PROMPT"""
def norm(s):
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-zA-Z0-9 ]+', ' ', s)
    return s.lower()

p_norm = norm(prompt)
p_words = set(w for w in p_norm.split() if len(w) >= 4)

# Stop words a ignorar
STOP = {'para','como','sobre','todo','todos','mas','menos','que','con','del','las','los','una','uno','esto','este','esta','muy','dale','quiero','tengo','algo','aqui','tambien'}
p_words -= STOP

# Distancia Levenshtein simple (para fuzzy)
def lev(a, b, max_dist=2):
    if abs(len(a) - len(b)) > max_dist:
        return max_dist + 1
    if a == b:
        return 0
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return max(m, n)
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a[i-1] == b[j-1] else 1
            curr[j] = min(curr[j-1] + 1, prev[j] + 1, prev[j-1] + cost)
        prev = curr
        if min(curr) > max_dist:
            return max_dist + 1
    return prev[n]

def fuzzy_match(word, prompt_words, max_dist=2):
    """Devuelve True si word matchea alguna prompt_word exacta o con typo <=2."""
    if word in prompt_words:
        return True
    for pw in prompt_words:
        if abs(len(pw) - len(word)) > max_dist:
            continue
        if lev(word, pw, max_dist) <= max_dist:
            return True
    return False

# Leer skills-map y extraer keywords de cada linea de tabla
matches = []
try:
    with open('$SKILLS_MAP', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip()
            if '|' not in line or '\`' not in line:
                continue
            cols = [c.strip() for c in line.split('|')]
            if len(cols) < 4:
                continue
            keywords_raw = cols[1] if len(cols) > 1 else ''
            # Normalizar keywords (split por coma y quitar acentos)
            kws = [norm(k.strip()) for k in keywords_raw.split(',')]
            # Tokenizar cada keyword en palabras y filtrar
            kw_words = []
            for k in kws:
                for w in k.split():
                    if len(w) >= 4 and w not in STOP:
                        kw_words.append(w)
            # Match: si alguna palabra del keyword aparece (exacta o fuzzy) en el prompt
            for w in kw_words:
                if fuzzy_match(w, p_words):
                    matches.append(line)
                    break
except Exception as e:
    print(f"# error: {e}", file=sys.stderr)

# Dedupe preservando orden
seen = set()
unique = []
for m in matches:
    if m not in seen:
        seen.add(m)
        unique.append(m)

# Limitar a 8 matches
for m in unique[:8]:
    print(m)
PYEOF
)

if [ -n "$MATCHES" ]; then
  # Detectar agentes mencionados en los matches (usando python para evitar escape hell del bash)
  AGENTS=$(echo "$MATCHES" | python -c "
import sys, re
text = sys.stdin.read()
# Match 'agente \`nombre\`' case-insensitive
agents = re.findall(r'agente\s+\x60([a-z-]+)\x60', text, re.IGNORECASE)
seen = set()
unique = []
for a in agents:
    if a not in seen:
        seen.add(a)
        unique.append(a)
for a in unique[:5]:
    print(a)
" 2>/dev/null)

  AGENT_DIRECTIVE=""
  if [ -n "$AGENTS" ]; then
    AGENT_LIST=$(echo "$AGENTS" | tr '\n' ',' | sed 's/,$//')
    AGENT_DIRECTIVE="

AUTO-LAUNCH AGENTES: Los siguientes subagentes DEBEN ser invocados via Agent tool en la PRIMERA respuesta (en paralelo si son varios, en un solo mensaje con multiples Agent calls):

$(echo "$AGENTS" | sed 's/^/  - subagent_type: \"/' | sed 's/$/\"/')

Si la tarea cruza dominios, lanzar TODOS en paralelo. Si es solo un dominio, lanzar el principal con un prompt detallado del objetivo. NO esperes que Emmanuel pida explicitamente el agente — el skill scanner ya lo identifico, ejecutalo de una."
  fi

  cat <<EOF
<system-reminder>
SKILL SCANNER MATCH (fuzzy v3) — las siguientes skills de ~/.claude/skills-map.md coinciden con tu prompt (incluye matches con typos hasta distancia 2).
OBLIGATORIO: invoca las skills principales con el Skill tool ANTES de responder, y lista las usadas en el bloque de cierre.

$MATCHES
$AGENT_DIRECTIVE

REGLAS:
- Si hay una skill PRINCIPAL que aplica, usala SIEMPRE (no esperes permiso).
- Combina con las COMPLEMENTARIAS si la tarea cruza dominios.
- Si ninguna skill del map aplica perfectamente, di por que y propon una alternativa.
- Al final de tu respuesta imprime SIEMPRE el bloque "Skills activadas / disponibles / siguiente paso".

AUTO-PROMPT ENHANCER: expande el mensaje informal a un prompt completo (OBJETIVO/CONTEXTO/ALCANCE/ENTREGABLE/CRITERIO/RESTRICCIONES) antes de ejecutar.
RUFLO: avisa en CADA respuesta con "Ruflo activo — [que esta haciendo]".
NO PERMISOS: Emmanuel tiene bypassPermissions activo. Nunca dar menus A/B/C/D ni preguntar "quieres que...". Ejecutar TODO directo.
</system-reminder>
EOF
else
  cat <<'EOF'
<system-reminder>
SKILL SCANNER: ninguna keyword del skills-map.md coincidio con este prompt (ni fuzzy).
Revisa ~/.claude/skills-map.md manualmente y considera invocar skills generales
(ej: deep-research si es investigacion, obsidian-vault si es del vault).

OBLIGATORIO al final de la respuesta: imprime "Skills activadas / disponibles / siguiente paso".
Auto-Prompt Enhancer: expande el mensaje antes de ejecutar.
Ruflo: avisa en cada respuesta.
</system-reminder>
EOF
fi

exit 0