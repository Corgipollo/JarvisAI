---
name: deep-research
description: Use when the user asks to investigate, research, find state-of-the-art, do a literature review, or wants "todo sobre X" / "investiga X" / "busca papers de X" / "que dice la gente de X". Orchestrates parallel multi-source research across web, GitHub, academic papers (arXiv/PubMed/bioRxiv), HackerNews, Reddit, YouTube transcripts, and the user's own Obsidian vault. Returns a structured report with cited sources, cross-verification, and confidence levels.
---

# Deep Research — Investigacion Multi-Fuente

> Skill para convertirme en un experto en investigacion que usa TODAS las fuentes disponibles en paralelo y sintetiza hallazgos con citas.

## Cuando activar

- "investiga X", "busca todo sobre X", "que sabe el mundo de X"
- "state of the art", "literature review", "papers de X"
- "que dice Reddit/HN/YouTube de X"
- "compara X vs Y" con evidencia externa
- "es cierto que X" (fact-checking)
- "consenso cientifico sobre X"

## Protocolo de investigacion (SIEMPRE seguir)

### Fase 1 — Clasificacion del query
Identificar el TIPO de investigacion:
- **Tecnica/cientifica** → priorizar arXiv, Google Scholar, GitHub, docs oficiales
- **Producto/mercado** → priorizar Reddit, HackerNews, reviews, blogs, YouTube
- **Noticias/actualidad** → priorizar WebSearch con filtro de fecha, Twitter, RSS
- **Historia/biografia** → Wikipedia, libros, archivos
- **Comparativa** → benchmarks, reviews cruzados

### Fase 2 — Plan en paralelo (OBLIGATORIO)
Lanzar TODAS las busquedas relevantes en **un solo mensaje con multiples tool calls**. Nunca secuencial.

Fuentes disponibles:

| Fuente | Herramienta | Para que |
|--------|-------------|----------|
| Web general | `WebSearch` o `mcp__duckduckgo__search` | Noticias, blogs, docs |
| Contenido especifico | `mcp__fetch__fetch` (preferido) o `WebFetch` | Leer URL completa, mas rapido |
| Papers academicos | **`mcp__arxiv__search_papers`** (preferido) o `mcp__arxiv__semantic_search` | Literatura cientifica directo |
| Lectura de paper | `mcp__arxiv__read_paper` o `mcp__arxiv__get_abstract` | Sin scraping |
| Citation graph | `mcp__arxiv__citation_graph` | Conexiones entre papers |
| GitHub codigo | `gh search repos/code` via Bash | Repos, implementaciones |
| GitHub commits/diff | `mcp__git__git_log`, `mcp__git__git_diff` | Cuando es repo local |
| HackerNews | **`mcp__hackernews__search_stories`** (preferido) | Opinion tecnica, discusiones |
| HN story details | `mcp__hackernews__get_story_info` | Comentarios y votes |
| Reddit | `WebSearch site:reddit.com` (no hay MCP aun) | Opinion usuarios |
| YouTube transcripts | `WebFetch` con youtube-transcript URL | Conferencias, tutoriales |
| DuckDuckGo busqueda | **`mcp__duckduckgo__search`** | Busqueda privada |
| DuckDuckGo content | `mcp__duckduckgo__fetch_content` | Lee resultados directo |
| Vault Obsidian | **`mcp__obsidian-vault__search_notes`** (preferido sobre Grep) | Knowledge propio |
| Vault read multi | `mcp__obsidian-vault__read_multiple_notes` | Batch read eficiente |
| Vault stats | `mcp__obsidian-vault__get_vault_stats` | Inventory rapido |
| Filesystem local | `mcp__filesystem__search_files`, `mcp__filesystem__read_text_file` | Reemplaza Glob/Read en Documents/ |
| Memoria knowledge graph | `mcp__memory__search_nodes`, `mcp__memory__create_entities` | Acumular findings entre sesiones |
| SQLite local | `mcp__sqlite__read_query` | Para datos del bot forex (.swarm/memory.db) |
| Codigo local fallback | `Grep`, `Glob` | Si los MCPs fallan |

**REGLA**: cuando tengas opcion entre un tool nativo y un MCP equivalente, **usa el MCP**. Es mas rapido, mas estructurado y queda en telemetria con `type:mcp`.

### Fase 3 — Triangulacion
- **Minimo 3 fuentes independientes** por claim importante
- Marcar claims con confianza: ALTA (3+ fuentes coinciden), MEDIA (2), BAJA (1 o contradicciones)
- Flagear contradicciones explicitamente

### Fase 4 — Sintesis y reporte

Formato obligatorio:

```markdown
# Investigacion: {topic}

## TL;DR (3 lineas)
{hallazgo principal}

## Hallazgos clave
1. **{claim}** — confianza ALTA
   - Fuente 1: [titulo](url)
   - Fuente 2: [titulo](url)
   - Fuente 3: [titulo](url)

2. **{claim}** — confianza MEDIA
   - ...

## Contradicciones detectadas
- {claim A} vs {claim B}: {explicacion}

## Gaps (lo que no encontre)
- {preguntas sin respuesta}

## Siguientes pasos sugeridos
- {que investigar despues}

## Fuentes completas
{lista numerada de TODAS las URLs consultadas}
```

### Fase 5 — Guardado en vault (OBLIGATORIO)

Si la investigacion es significativa, guardar en:
`03-Conocimiento/Research/{YYYY-MM-DD} - {topic}.md`

Con frontmatter:
```yaml
---
tags:
  - research
  - sesion-claude
  - {dominio}
created: {YYYY-MM-DD}
tipo: conocimiento
confianza: alta|media|baja
fuentes_count: N
---
```

## Reglas anti-basura

- **NUNCA** inventar URLs ni resultados
- **NUNCA** reportar como cierto algo con 1 sola fuente dudosa
- **NUNCA** saltar la fase de triangulacion
- Si una fuente es un blog random sin autor, marcar como BAJA confianza
- Preferir fuentes primarias > secundarias > terciarias
- Fecha de publicacion: si es >2 anos viejo y el tema es rapido (IA, crypto), flagear como "puede estar desactualizado"

## Ranking de calidad de fuentes

**TIER 1 (confianza alta)**
- Papers peer-reviewed (arXiv, Nature, IEEE)
- Docs oficiales (Anthropic, OpenAI, Python docs)
- Libros reconocidos
- Github repos oficiales de organizaciones

**TIER 2 (confianza media)**
- HackerNews top comments (>50 upvotes)
- Reddit top posts (>100 upvotes)
- Blogs de expertos reconocidos
- YouTube de canales especializados
- Stack Overflow aceptadas

**TIER 3 (confianza baja — triangular siempre)**
- Blogs random
- Medium posts sin credenciales
- Redes sociales
- AI-generated content sospechoso

## Ejemplos de invocacion

```
Usuario: "investiga todo sobre RAG con AgentDB"
Yo: [paralelo: arXiv "RAG AgentDB", GitHub "agentdb rag", WebSearch, HN "AgentDB vector", vault]
→ Reporte con 15 fuentes + TL;DR + guardar en vault

Usuario: "que dice la gente del bot de trading de Freqtrade vs Jesse"
Yo: [paralelo: Reddit, HN, GitHub stars, YouTube reviews, docs oficiales]
→ Comparativa con pros/contras citados

Usuario: "es cierto que Claude Opus 4.6 es mejor que GPT-5 en codigo"
Yo: [paralelo: arXiv benchmarks, HN, Twitter, official blogs, anecdotal Reddit]
→ Triangulacion con evidencia + confianza explicita
```

## Integracion con research-expert agent

Si el query es muy amplio (>10 subtemas), delegar al subagente `research-expert` usando el `Agent` tool, que tiene memoria persistente en `~/.claude/agent-memory/research-expert/` para acumular findings entre sesiones.