---
name: obsidian-vault
description: Use when the user mentions Obsidian, vault, MOC, cerebro, or any project from CerebroEmmanuel (GROP, Bot Forex, Jarvis, Manhwa, NeuroGrain, Dispatch Telegram, Antigravity Canvas, etc.). Provides search, MOC navigation, frontmatter parsing, backlink discovery, and auto-guardado in the right folder. Triggers automatically when working inside C:/Users/Emmanuel/Documents/CerebroEmmanuel.
---

# Obsidian Vault — CerebroEmmanuel

> Skill especializada para navegar y extender el vault Obsidian de Emmanuel Pedraza.
> Vault path: `C:/Users/Emmanuel/Documents/CerebroEmmanuel/`

## Cuando activar

- Usuario menciona: obsidian, vault, MOC, cerebro, nota, backlink, frontmatter
- Usuario menciona cualquier proyecto activo: GROP, Bot Forex, Jarvis, Manhwa, NeuroGrain, Dispatch, Antigravity, AutomatonClone, POD, Amazon FBM, Agencia Websites, Video Dubbing
- Cwd es CerebroEmmanuel (auto-trigger)

## Estructura del vault

```
00-Inbox/              ← capturas rapidas, sin clasificar
01-Proyectos/          ← cada proyecto activo con su MOC
02-Tecnico/            ← hardware, devops, infra
03-Conocimiento/       ← desarrollo web, IA, negocio
04-Diario/             ← sesiones, historial-preguntas.md
07-Codigo/             ← snippets de codigo por proyecto
```

## MOCs principales (memorizar)

| Proyecto | MOC |
|----------|-----|
| GROP Ecommerce | `01-Proyectos/GROP-Ecommerce/MOC - GROP Ecommerce.md` |
| Bot Forex V8 | `01-Proyectos/Bot-Forex-V8/00 - INDEX Bot Forex V8.md` |
| Jarvis AI | `01-Proyectos/Jarvis-AI/MOC - Jarvis AI.md` |
| Jarvis Cobranza | `01-Proyectos/Jarvis-Cobranza/MOC - Jarvis Cobranza.md` |
| Manhua Narrado | `01-Proyectos/Manhua-Narrado/MOC - Manhua Narrado.md` |
| Video Dubbing | `01-Proyectos/Video-Dubbing/MOC - Video Dubbing Pipeline.md` |
| Dispatch Telegram | `01-Proyectos/Dispatch-Telegram/MOC - Dispatch Telegram.md` |
| NeuroGrain SAP | `01-Proyectos/NeuroGrain-SAP/MOC - NeuroGrain SAP.md` |
| Dropshipping Testing | `01-Proyectos/Dropshipping-Testing/MOC - Dropshipping Testing AI.md` |
| Amazon FBM | `01-Proyectos/Amazon-FBM/MOC - Amazon FBM Dropshipping.md` |
| Agencia Websites | `01-Proyectos/Agencia-Websites/MOC - Agencia Websites AI.md` |
| POD Streetwear | `01-Proyectos/POD-Streetwear/MOC - POD Streetwear.md` |
| Antigravity Canvas | `01-Proyectos/Antigravity-Canvas/00 - INDEX Antigravity Canvas.md` |
| Hardware | `02-Tecnico/Hardware/MOC - Hardware y Diagnostico.md` |
| DevOps | `02-Tecnico/DevOps/MOC - DevOps.md` |
| Desarrollo Web | `03-Conocimiento/Desarrollo-Web/MOC - Desarrollo Web.md` |
| IA y Automatizacion | `03-Conocimiento/IA-Automatizacion/MOC - IA y Automatizacion.md` |

## Workflow estandar (con MCPs preferidos)

### Tools MCP a usar SIEMPRE que esten disponibles

| Operacion | MCP preferido | Fallback |
|---|---|---|
| Buscar texto en notas | `mcp__obsidian-vault__search_notes` | `Grep` |
| Leer una nota | `mcp__obsidian-vault__read_note` | `Read` |
| Leer N notas en batch | `mcp__obsidian-vault__read_multiple_notes` | loops `Read` |
| Listar carpeta | `mcp__obsidian-vault__list_directory` | `Glob` |
| Crear nota | `mcp__obsidian-vault__write_note` | `Write` |
| Editar nota (parche) | `mcp__obsidian-vault__patch_note` | `Edit` |
| Mover nota | `mcp__obsidian-vault__move_note` | `Bash mv` |
| Frontmatter ops | `mcp__obsidian-vault__get_frontmatter`, `update_frontmatter` | edicion manual |
| Tags ops | `mcp__obsidian-vault__list_all_tags`, `manage_tags` | `Grep tags:` |
| Stats vault | `mcp__obsidian-vault__get_vault_stats` | `find . -name *.md \| wc -l` |
| Borrar nota | `mcp__obsidian-vault__delete_note` | `rm` |

### Consulta sobre un proyecto
1. Identificar el proyecto del query
2. Leer su MOC primero con `mcp__obsidian-vault__read_note`
3. `mcp__obsidian-vault__search_notes` para detalles adicionales (mas rapido que Grep)
4. Responder con contexto + backlinks

### Crear nota nueva
1. Detectar tipo (proyecto/tecnico/conocimiento/diario/codigo)
2. Elegir carpeta destino segun `@auto-guardado.md`
3. Generar frontmatter con tags + tipo + sesion_origen
4. Agregar backlinks al MOC del proyecto
5. Si es proyecto activo, actualizar el MOC tambien

### Buscar across vault
- Por keyword: `Grep -path "01-Proyectos/" "{keyword}"`
- Por tag: `Grep -r "tags:.*{tag}" --include="*.md"`
- Por backlink: `Grep -r "\[\[{Nota}\]\]"`

## Frontmatter estandar

```yaml
---
tags:
  - sesion-claude
  - {tags-relevantes}
created: YYYY-MM-DD
tipo: proyecto|tecnico|conocimiento|diario
sesion_origen: claude-code
---
```

## Sincronizacion GitHub (OBLIGATORIO)

Antes de cualquier push:
1. `git pull origin master` primero
2. Resolver conflictos
3. `git add -A && git commit -m "descripcion en espanol" && git push origin master`

Repo: https://github.com/Corgipollo/CerebroEmmanuel (privado)

## Reglas del cerebro

- **Append-only** en `04-Diario/historial-preguntas.md` — nunca borrar entradas
- **No duplicar MOCs** — extender los existentes
- **Backlinks siempre** — cada nota nueva debe linkear al MOC de su proyecto
- **Espanol** en titulos y contenido
- **Frontmatter obligatorio** en notas nuevas

## Comandos relacionados

- `/cerebro` — consulta rapida al vault
- `/exportar` — exportar sesion actual como nota
- `/status` — estado de todos los proyectos