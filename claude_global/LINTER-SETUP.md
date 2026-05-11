# Linter del Setup Claude — claude-rules-doctor

> Linter automatico para detectar problemas en `~/.claude/CLAUDE.md`, skills, agentes y reglas.

## Instalacion

```bash
npm install -g claude-rules-doctor
```

O ejecutar sin instalar:
```bash
npx claude-rules-doctor lint ~/.claude/CLAUDE.md
```

## Que detecta

- CLAUDE.md > 200 lineas (causa que Claude ignore instrucciones)
- Reglas duplicadas o contradictorias
- Imports rotos (`@archivo.md` que no existe)
- Skills sin frontmatter valido
- Agentes sin description
- Frontmatter YAML mal formado

## Cuando ejecutar

- **Mensualmente** como check de salud del setup
- **Despues de agregar >50 lineas** a cualquier archivo
- **Antes de un refactor** para tener baseline

## Comandos

```bash
# Lint del CLAUDE.md global
npx claude-rules-doctor lint ~/.claude/CLAUDE.md

# Lint de toda la carpeta .claude
npx claude-rules-doctor lint ~/.claude/

# Auto-fix de problemas simples
npx claude-rules-doctor fix ~/.claude/CLAUDE.md

# Reporte completo
npx claude-rules-doctor report ~/.claude/ --output=report.md
```

## Alternativa: agnix

`agnix` es otro linter especifico para archivos de agentes (`~/.claude/agents/*.md`).

```bash
npx agnix lint ~/.claude/agents/
```

## Schedule sugerido

Agregar a `~/.claude/hooks/` un hook `SessionEnd` que ejecute el linter una vez por dia:

```bash
# ~/.claude/hooks/lint-rules-daily.sh
LAST_LINT_FILE="$HOME/.claude/.last-lint-date"
TODAY=$(date +%Y-%m-%d)

if [ ! -f "$LAST_LINT_FILE" ] || [ "$(cat $LAST_LINT_FILE)" != "$TODAY" ]; then
  npx claude-rules-doctor lint $HOME/.claude/CLAUDE.md > /dev/null 2>&1
  echo "$TODAY" > "$LAST_LINT_FILE"
fi
```

## Referencias

- https://github.com/affaan-m/everything-claude-code (memory persistence patterns)
- https://github.com/hesreallyhim/awesome-claude-code (curated list)
- https://code.claude.com/docs/en/best-practices (regla <200 lineas)