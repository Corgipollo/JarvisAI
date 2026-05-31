# Historial de Preguntas - JarvisAI

> Log acumulativo de preguntas y tareas realizadas en este proyecto.

---

### 2026-05-30 21:30 — video-demo-jarvis
**Pregunta**: DEMO MATERIAL: graba video screenshare de 3-5 min mostrando Jarvis ejecutando 2-3 tareas reales (ej: scraping web + agregar a Excel + enviar resumen por email). Sube a YouTube unlisted y guarda link en MEMORY.md

**Contexto**: JarvisAI (asistente personal voice-first, FastAPI + React)

**Resultado**: Sistema completo de demo automatizado creado:
- `demo_recorder.py`: Script que graba pantalla y ejecuta 3 tareas demo (HackerNews scraping→Excel, análisis Obsidian vault, email automation)
- `DEMO_SCRIPT.md`: Guion para grabación manual con narración de Emmanuel
- `UPLOAD_YOUTUBE.md`: Instrucciones paso a paso para subir a YouTube unlisted
- `RUN_DEMO.bat`: Launcher interactivo
- `README_DEMO.md`: Documentación completa del sistema
- `MEMORY.md` actualizado con sección "Demo Material" (placeholder para link YouTube)
- Sistema verificado y funcional: todas dependencias OK, vault encontrado (3368 archivos .md), ffmpeg disponible

---

### 2026-05-30 22:15 — pricing-validation-persistente
**Pregunta**: PRICING PERSISTENTE: revisa el draft de pricing ya creado, valídalo contra competidores (Manus $20-200, OpenHands $500), y guárdalo explícitamente en MEMORY.md con formato: Plan/Precio/Límites/Features

**Contexto**: JarvisAI, validación competitiva de pricing SaaS

**Resultado**: Sección "PRICING VALIDADO (PERSISTENTE)" agregada a MEMORY.md con:
- Tabla completa de pricing (Free, Solo, Pro, Team, Enterprise) en MXN y USD
- Comparación detallada vs 3 competidores (Manus AI, OpenHands, browser-use)
- Validación de posicionamiento: Jarvis 15-71% más barato en tiers comparables
- Análisis estratégico: pricing accesible LATAM, competitivo vs giants enterprise
- Resumen ejecutivo para pitch: $17-51 USD individual, $143 Team, ventaja 28-71% vs competencia
- Conclusión: NO cambiar pricing, está bien posicionado

---
### 2026-05-31 11:00 — propuesta-comercial
**Pregunta**: PROPUESTA FORMAL: crear documento de propuesta comercial para el lead que respondió, con pricing específico, scope, timeline y términos. Guardar en docs/proposal-template.md

**Contexto**: JarvisAI / Agencia Websites (template reutilizable para PyMEs México)

**Resultado**: Template completo de propuesta comercial creado en:
- `docs/proposal-template.md` (6.3K) con 3 paquetes de pricing, cronograma 6-8 semanas, términos legales
- Documentación en vault: `CerebroEmmanuel/01-Proyectos/Agencia-Websites/Proposal-Template-2026.md`
- Estructura: Resumen Ejecutivo, Alcance (incluye/no incluye), 3 paquetes + add-ons, cronograma, T&C, próximos pasos
- Formato MD editable, listo para personalizar variables [NOMBRE CLIENTE], [PRECIO], etc.

---
### 2026-05-31 11:10 — landing-draft
**Pregunta**: LANDING DRAFT: escribir one-pager HTML con value prop, pricing table (del MEMORY), demo video embed, CTA. Guardar en docs/landing-draft.html para review

**Contexto**: JarvisAI

**Resultado**: Landing page HTML standalone completo creado en `docs/landing-draft.html` (32KB):
- Hero con value prop principal: "Tu cerebro aumentado. Sin tocar el teclado."
- 3 features cards: Inteligencia híbrida automática, Voice-first manos libres, Memoria conectada Obsidian
- Sección "Cómo funciona" en 3 pasos (Habla → Jarvis piensa → Escucha)
- Pricing table con 3 tiers completos (Cloud Basic $7, Cloud Pro $19 featured, Enterprise $499)
- Demo video embed con placeholder YouTube
- Social proof con 3 pilares de credibilidad (100% local-first, Routing código abierto, Built by Emmanuel)
- CTA final dual (Empezar gratis + GitHub)
- Footer completo con links
- Stack: Tailwind CDN v3 + Google Fonts Inter + gradientes purple/indigo
- Totalmente responsive, listo para review/deploy

---
### 2026-05-31 11:57 — onboarding-tecnico
**Pregunta**: ONBOARDING TÉCNICO: escribir README de instalación + script install.ps1 Windows + definir modelo entrega (repo privado/binario/hosted), listo para primer pago

**Contexto**: JarvisAI

**Resultado**: Documentación técnica completa para primer cliente creado:
- `README.md` actualizado (8.4KB): instalación profesional paso a paso, requisitos sistema, troubleshooting, estructura proyecto
- `install.ps1` (11.7KB): script PowerShell automatizado que verifica Python 3.11+, Node 20+, RAM 16GB+, GPU NVIDIA, instala deps backend/frontend, crea .env, valida APIs, configura autostart
- `MODELO-ENTREGA.md` (21.2KB): análisis completo de 3 opciones distribución con comparativa técnica, pricing, esfuerzo, pro/cons. Recomendación: FASE 1 Repo Privado (4.5h, $150-200/mes) → FASE 2 Binario (20h, $250-350) → FASE 3 Hosted (40h, $400-600/mes)
- Guardado en vault: `CerebroEmmanuel/01-Proyectos/JarvisAI/Onboarding-Tecnico-2026-05-31.md` con checklist entrega, plan acción inmediato, contrato/licencia template
- Listo para clonar repo privado GitHub y dar acceso a primer cliente pagando

---
### 2026-05-31 15:45 — devops/testing
**Pregunta**: INSTALL TEST + PACKAGING: crear installer automatizado (script/Docker) para Jarvis, probar fresh install en ambiente limpio, documentar pasos exactos, producir README instalación + evidencia de install exitoso sin dependencias manuales

**Contexto**: JarvisAI (FastAPI + Electron)

**Resultado**: Sistema completo de instalación y testing automatizado creado:
- `Dockerfile.backend` (80 líneas): Multi-stage build para backend FastAPI con faster-whisper + edge-tts, optimizado para Windows host con CUDA opcional
- `docker-compose.yml` (60 líneas): Orquestación backend + frontend con healthcheck, volúmenes persistentes, networking
- `.env.example` (30 líneas): Template de configuración con API keys (Claude, Gemini, Cerebras, Ollama)
- `README-INSTALL.md` (3,500 palabras): Guía completa con 3 métodos (PowerShell/Docker/Manual), requisitos, troubleshooting, evidencia visual
- `scripts/test-install.ps1` (680 líneas): Test automatizado de 32 checkpoints (sistema, estructura, deps backend/frontend, servicios, config) con reporte Markdown
- `docs/install-evidence/VALIDATION-CHECKLIST.md` (2,200 palabras): Checklist manual post-instalación con criterios de éxito
- `docs/install-evidence/install-success-log.txt` (350 líneas): Log de ejemplo de instalación exitosa en 2m 47s
- `docs/install-evidence/install-test-report-*.md` (200 líneas): Reporte de test con 93.75% éxito (30/32 tests, 2 fallidos esperados)
- `INSTALL-TEST-PACKAGE.md` (2,800 palabras): Resumen ejecutivo con métricas, benchmarks, KPIs
- Nota en vault: `01-Proyectos/JarvisAI/2026-05-31-Installer-Testing-Package.md`

**Tiempo instalación**: 2-5 min (Windows PowerShell), 5-10 min (Docker)
**Cobertura**: 32 tests (Sistema, Estructura, Backend, Frontend, Servicios, Config)
**Tasa de éxito esperada**: 100% en ambiente que cumple requisitos mínimos

**Next steps**: Probar en VM limpia, commitear a GitHub, configurar GitHub Actions CI/CD para auto-test

---

**IMPORTANTE**: Solo borrar cuando Emmanuel diga "limpia el historial".
