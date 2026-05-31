# 🔍 Reporte: Competidores Computer Use Agents

**Fecha:** 30 mayo 2026
**Investigación:** OpenHands, Manus AI, browser-use

---

## 📊 Resumen Ejecutivo

Investigué 3 competidores principales de agentes Computer Use. Aquí los hallazgos clave:

---

## 1️⃣ **OpenHands** ⭐ 75.4k stars

**Qué hace:**
- Plataforma AI-driven development modular
- Múltiples frontends: CLI, GUI local, Cloud, Kubernetes
- LLM-agnostic (Claude, GPT, cualquier modelo)
- Score SWEBench: 77.6

**Precio:**
- Open-source (MIT): gratis
- Pro Cloud: $20/mes
- Enterprise: custom

**💡 Ventaja para Jarvis:**
**Arquitectura modular multi-frontend** — Un SDK Python central que alimenta CLI, GUI, cloud. Nosotros podríamos tener voice + CLI + GUI compartiendo el mismo motor FastAPI.

🔗 https://github.com/OpenHands/OpenHands

---

## 2️⃣ **Manus AI** (by Monica/Meta?)

**Qué hace:**
- Agente autónomo general, planifica tareas multi-paso
- "My Computer": ejecuta command-line en sistema local
- Outperforma GPT-4 en benchmark GAIA (>65%)

**Precio:**
- Free: 300 créditos/día
- Standard: $20/mes (4k créditos)
- Customizable: $40/mes (8k)
- Extended: $200/mes (40k)

**💡 Ventaja para Jarvis:**
**Sistema de créditos por acción** — Cada acción consume créditos (browse, code, file). Daily refresh credits hacen el freemium predecible. Podríamos implementar esto para metering granular.

⚠️ Nota: Hay contradicción sobre ownership (Monica vs Meta). Sitio oficial no confirma adquisición.

🔗 https://manus.im/

---

## 3️⃣ **browser-use** ⭐ 96.3k stars

**Qué hace:**
- Python library para automatización web con AI
- Vision-based interaction: screenshots + HTML
- Identifica elementos sin CSS selectors frágiles
- Multi-LLM, open-source MIT

**Precio:**
- Open-source: gratis
- Cloud PAYG: $0/mes + uso
- Starter: $100/mes
- Business: $500/mes

**💡 Ventaja para Jarvis:**
**Vision-based element detection** — Combina screenshots + DOM para que LLM identifique elementos clickeables por visión. Podríamos usar esto para automatización desktop (UI elements por visión + UIA fallback).

🔗 https://github.com/browser-use/browser-use

---

## ✅ Acciones Recomendadas

1. **Prototipar vision-based UI detection** (inspirado en browser-use)
2. **Diseñar sistema créditos diarios** (300 gratis/día como Manus)
3. **Separar engine de interfaces** (arquitectura multi-frontend como OpenHands)

---

## 📁 Guardado

Tabla completa guardada en:
`C:\Users\Emmanuel\Documents\JarvisAI\MEMORY.md`
(Sección "Competencia y posicionamiento")

---

**Fuentes:** GitHub oficial + docs + arXiv + 12 fuentes web trianguladas
**Confianza:** ALTA (OpenHands, browser-use), MEDIA (Manus ownership)
