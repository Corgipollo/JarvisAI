# Auto-Guardado en CerebroEmmanuel

> Reglas de guardado automatico al terminar tareas significativas.
> Importado desde `~/.claude/CLAUDE.md` con `@auto-guardado.md`.

## Cuando guardar

- **SI** la tarea fue significativa (cambio de codigo, decision, hallazgo)
- **NO** si fue trivial (saludo, aclaracion rapida, pregunta simple)

## Donde guardar (vault Obsidian)

| Tipo | Carpeta destino |
|------|-----------------|
| Trabajo de proyecto | `01-Proyectos/{proyecto}/` |
| Tecnico/infra | `02-Tecnico/{subcarpeta}/` |
| Conocimiento nuevo | `03-Conocimiento/{subcarpeta}/` |
| Sesion general | `04-Diario/` |
| Codigo | `07-Codigo/{proyecto}/` |

## Formato de nota (frontmatter obligatorio)

```markdown
---
tags:
  - sesion-claude
  - {tags relevantes}
created: {YYYY-MM-DD}
tipo: {proyecto|tecnico|conocimiento|diario}
sesion_origen: claude-code
---

# {Titulo descriptivo}

> {Resumen 1-2 lineas}

## Lo que se hizo
{Acciones principales}

## Codigo clave
{Snippets si aplica}

## Decisiones
{Decisiones tomadas}

## Pendientes
- [ ] {Lo que quedo pendiente}

## Notas relacionadas
- [[backlinks relevantes]]
```

## Tags automaticos por contenido

| Si el contenido toca... | Tag | MOC backlink |
|-------------------------|-----|--------------|
| shopify, grop, tienda | `ecommerce` | `[[MOC - GROP Ecommerce]]` |
| docker, deploy | `devops` | `[[MOC - DevOps]]` |
| flask, react, css | `frontend`/`backend` | `[[MOC - Desarrollo Web]]` |
| ollama, ia, llm | `ia` | `[[MOC - IA y Automatizacion]]` |
| neurograin, sap, granos | `granos` | `[[MOC - NeuroGrain SAP]]` |
| jarvis, asistente, voz | `jarvis-ai` | `[[MOC - Jarvis AI]]` |
| video, whisper, dubbing | `video` | `[[MOC - Video Dubbing Pipeline]]` |
| manhua, manhwa, ocr | `manhua` | `[[MOC - Manhua Narrado]]` |
| telegram, dispatch, bot | `telegram` | `[[MOC - Dispatch Telegram]]` |
| dropshipping, ads, facebook | `dropshipping-testing` | `[[MOC - Dropshipping Testing AI]]` |
| amazon, fbm, buybox | `amazon` | `[[MOC - Amazon FBM Dropshipping]]` |
| agencia, websites, pymes | `agencia` | `[[MOC - Agencia Websites AI]]` |
| pod, redbubble, print | `pod` | `[[MOC - POD Streetwear]]` |
| forex, trading, bot, spike | `bot-forex` | `[[00 - INDEX Bot Forex V8]]` |
| antigravity, canvas, pencil | `antigravity-canvas` | `[[00 - INDEX Antigravity Canvas]]` |
| jarvis, cobranza | `cobranza` | `[[MOC - Jarvis Cobranza]]` |
| hardware, ram, crash | `hardware` | `[[MOC - Hardware y Diagnostico]]` |
| obsidian, vault, MOC | `meta-vault` | `[[CLAUDE.md]]` |