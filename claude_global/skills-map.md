# Mapa de Skills — Por Dominio

> Tabla de mapeo: keyword detectada → skill principal a invocar.
> Uso: importado desde `~/.claude/CLAUDE.md` con `@skills-map.md`.

## Reglas del Skill Scanner

1. **ANTES de responder**: identificar dominio → invocar skill principal con `Skill` tool
2. **DURANTE**: combinar skills si la tarea cruza dominios
3. **DESPUES**: imprimir bloque "Skills activadas / disponibles / siguiente paso"

## Mapa: Keyword → Skill

| Si Emmanuel menciona... | Skill PRINCIPAL | Skills COMPLEMENTARIAS |
|--------------------------|-----------------|------------------------|
| animar, animacion, motion, GSAP | `ui-ux-pro-max` | `react-expert`, `remotion-expert` |
| Three.js, 3D, WebGL, shader | `react-expert` | `ui-ux-pro-max` |
| video, editar video, render, MP4 | `remotion-expert` | `ui-ux-pro-max` |
| React, componente, hook, Next.js | `react-expert` | `ui-ux-pro-max`, `playwright-expert` |
| CSS, Tailwind, UI, colores | `ui-ux-pro-max` | `react-expert`, `a11y-audit` |
| Python, script, pandas, data | `python-pro` | `pandas-pro`, `fastapi-expert` |
| API, FastAPI, endpoint, REST | `fastapi-expert` | `python-pro`, `api-design-reviewer` |
| Docker, container, compose | `docker-development` | `github:workflow-automation` |
| Shopify, tienda, producto, liquid | `shopify-expert` | `ad-creative`, `revenue-operations` |
| ads, Facebook, anuncio, creative | `ad-creative` | `campaign-analytics`, `ab-test-setup` |
| SEO, ranking, keywords | `ai-seo` | `content-production`, `seo-auditor` |
| email, outreach, cold, prospectar | `cold-email` | `campaign-analytics` |
| contenido, blog, articulo | `content-production` | `brand-guidelines`, `ai-seo` |
| test, testing, E2E, playwright | `playwright-expert` | `tdd`, `debugging-wizard` |
| bug, error, crash, debug, fix | `debugging-wizard` | `focused-fix`, `pair-programming` |
| PR, pull request, code review | `pr-review-expert` | `github:code-review` |
| release, deploy, CI/CD, workflow | `github:release-manager` | `github:workflow-automation` |
| prompt, LLM, optimizar prompt | `prompt-engineer` | `llm-cost-optimizer` |
| RAG, embeddings, vector | `rag-architect` | `agentdb-vector-search` |
| swarm, agentes, multi-agent | `swarm-orchestration` | `swarm-advanced` |
| forex, trading, bot, MT5, scalper, binance | agente `bot-forex-analyst` | `python-pro`, `pandas-pro` |
| manhua, manhwa, narrado, OCR, voice clone, ffmpeg | agente `manhwa-pipeline` | `remotion-expert`, `python-pro` |
| Jarvis, asistente, voz | `fastapi-expert` | `python-pro`, `prompt-engineer` |
| plan, PRD, requerimientos | `prd` | `sparc:architect`, `user-story` |
| sprint, agile, backlog | `sprint-plan` | `sprint-health`, `project-health` |
| arquitectura, sistema, diseno | `sparc:architect` | `sparc:spec-pseudocode` |
| Amazon, FBM, BuyBox, seller | `shopify-expert` | `revenue-operations` |
| marca, brand, identidad | `brand-guidelines` | `ui-ux-pro-max` |
| competencia, vs, alternativas | `competitor-alternatives` | `competitive-matrix` |
| contrato, propuesta, cotizacion | `contract-and-proposal-writer` | `sales-engineer` |
| churn, retencion, cancelacion | `churn-prevention` | `customer-success-manager` |
| MCP, server, herramienta custom | `mcp-server-builder` | `claude-api` |
| hook, automatizacion, workflow | `hooks-automation` | `automation:workflow-select` |
| accesibilidad, WCAG, a11y | `a11y-audit` | `ui-ux-pro-max` |
| deuda tecnica, refactor | `tech-debt` | `sparc:refinement-optimization-mode` |
| obsidian, vault, MOC, cerebro, backlinks, tags | `obsidian-vault` + agente `vault-curator` | — |
| investiga, research, busca todo, estado del arte | `deep-research` + agente `research-expert` | `obsidian-vault` |
| multi-proyecto, tareas cruzadas, multiples dominios | agente `orchestrator` | `swarm-orchestration` |
| papers, arxiv, literature review, paper de | `deep-research` | `rag-architect` |
| que dice Reddit, que dice HN, que opinan | `deep-research` | — |
| es cierto que, fact check, verifica | `deep-research` | — |
| compara X vs Y (con evidencia externa) | `deep-research` | `competitive-matrix` |
| cuanto gaste, budget, tokens, API cost | `cost-tracker` | — |
| audita mi setup, weekly review Claude | agente `grop-supervisor` | `hooks-automation` |
| GROP, Shopify, tienda, AutoDS | agente `grop-ecommerce` | `shopify-expert`, `ad-creative` |
| Jarvis, asistente, voz STT/TTS | agente `jarvis-ai` | `fastapi-expert`, `python-pro` |
| NeuroGrain, SAP, ERP granos | agente `neurograin-sap` | `fastapi-expert`, `docker-development` |
| Agencia Websites, PyMEs, leads | agente `agencia-websites` | `cold-email`, `ai-seo` |
| haz una web, landing page, sitio, portfolio, SaaS UI | `web-builder` + agente `web-expert` | `ui-ux-pro-max`, `react-expert`, `ai-seo`, `a11y-audit` |
| blog nuevo, docs site, storefront custom | `web-builder` | `content-production`, `shopify-expert` |
| Core Web Vitals, LCP, INP, CLS, Lighthouse | `web-builder` | `a11y-audit`, `analytics-tracking` |
| premium, Awwwards, animaciones, scroll scroll-trigger, interactivo, 3D | `web-builder` tier premium | `ui-ux-pro-max`, `react-expert`, `remotion-expert` |
| GSAP, Motion, Framer Motion, Lenis, Three.js, R3F | `web-builder` tier premium | `react-expert` |
| video hero, parallax, pinning, text reveal | `web-builder` tier premium | `ui-ux-pro-max` |

## Skills nuevas (post-install 2026-04-18)

| Si Emmanuel menciona... | Skill PRINCIPAL | Skills COMPLEMENTARIAS |
|--------------------------|-----------------|------------------------|
| bedrock, second brain, zettelkasten, ingesta confluence/gdocs | `bedrock-ask` | `bedrock-preserve`, `bedrock-teach`, `bedrock-sync` |
| salud vault, backlinks rotos, orphans, vault compress | `bedrock-healthcheck` | `bedrock-compress`, agente `vault-curator` |
| importa github/confluence/gdoc al vault | `bedrock-teach` | `bedrock-preserve`, `obsidian-vault` |
| setup vault nuevo, zettelkasten inicial | `bedrock-setup` | `bedrock-vaults` |
| multiples vaults, registry, default vault | `bedrock-vaults` | `bedrock-setup` |
| dedupe vault, fragmentacion concepts, fix backlinks | `bedrock-compress` | `bedrock-healthcheck` |
| sync entidades con github/externas | `bedrock-sync` | `bedrock-teach` |
| case study, deep-dive blog, growth post MDX | `cook-the-blog` | `content-production`, `ai-seo` |
| docs desde codigo, README auto, API reference | `docs-from-code` | `technical-writer`, `api-docs` |
| explica PR, describe cambios, PR comment | `explain-this-pr` | `pr-review-expert`, `pr-description-writer` |
| monitor HN, keywords HackerNews, Slack alert | `hackernews-intel` | `deep-research` |
| humaniza copy, AI cliches, tono natural | `human-tone` | `content-production`, `brand-guidelines` |
| post LinkedIn, articulo → LinkedIn, LinkedIn GTM | `linkedin-post-generator` | `human-tone`, `content-production` |
| llms.txt, citacion ChatGPT/Perplexity, AI discoverable | `llms-txt-generator` | `ai-seo`, `schema-markup-generator` |
| meeting brief, pre-call, research cliente | `meeting-brief-generator` | `sales-engineer`, `cold-email` |
| Meta Ads, Facebook Ads, Instagram Ads | `meta-ads-skill` | `ad-creative`, `campaign-analytics` |
| newsletter, digest RSS, Ghost CMS | `newsletter-digest` | `content-production` |
| outreach sequence, multi-channel, signal-based | `outreach-sequence-builder` | `cold-email`, `human-tone` |
| descripcion PR, PR description | `pr-description-writer` | `explain-this-pr`, `pr-review-expert` |
| pricing page audit, psicologia precio, charm | `pricing-page-psychology-audit` | `brand-guidelines`, `competitor-alternatives` |
| Product Hunt launch, PH kit, launch day | `producthunt-launch-kit` | `ad-creative`, `content-production` |
| Reddit ICP, subreddit monitor, buyer signal | `reddit-icp-monitor` | `outreach-sequence-builder`, `deep-research` |
| schema.org, JSON-LD, rich snippets | `schema-markup-generator` | `ai-seo`, `seo-auditor` |
| CLAUDE.md generator, init CLAUDE.md | `claude-md-generator` | `skill-builder` |
| design system, design OS, 10 libros design | `design-skill-os` | `ui-ux-pro-max`, `brand-guidelines` |
| diseno web espec, DESIGN.md, spec first web | `web-design` | `ui-ux-pro-max`, `web-builder` |

## Formato de cierre obligatorio

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Skills activadas: [las que se usaron]
Skills disponibles: [3-5 mas del dominio]
Mejor siguiente paso: [sugerencia con skill especifica]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```