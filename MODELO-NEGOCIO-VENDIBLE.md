# 🎯 MODELO DE NEGOCIO VENDIBLE — Jarvis AI

> **Documento ejecutivo** — Propuesta de valor, pricing, estructura legal y go-to-market  
> **Última actualización:** 31 mayo 2026  
> **Status:** ✅ VALIDADO con research competitivo (26 fuentes)

---

## 🔥 PITCH DE 30 SEGUNDOS

**"Asistente IA privado en español — vive en tu PC, sin cloud, control total Windows"**

**Jarvis AI** es el único asistente personal voice-first que:
1. **Funciona 100% local** (on-premise) — tus datos NUNCA salen de tu máquina
2. **Español nativo** (no traducción parche) — optimizado para LATAM
3. **Multi-LLM inteligente** — routing automático Claude → Gemini → Ollama según costo/capacidad
4. **Deep integration** — lee/escribe Obsidian, ejecuta scripts, controla Windows, integra ERP/CRM
5. **Pricing LATAM-friendly** — $7-$19 USD (vs $20-200 competencia global)

**Diferenciador killer:** Es el ÚNICO voice assistant que combina privacidad total (self-hosted) + ejecución real de tareas (no solo chat) + español-first a precio accesible LATAM.

---

## 💰 MODELO DE NEGOCIO

### Tipo de Producto
**SaaS Híbrido** (self-hosted + cloud según tier)

- **Tiers básicos (Free, Cloud Basic, Cloud Pro):** Self-hosted opcional — cliente instala en su PC, zero dependencia cloud
- **Tier Enterprise:** 100% on-premise obligatorio — deploy en infraestructura del cliente (Docker/K8s)

### Revenue Streams
1. **Suscripciones recurrentes** (MRR principal)
2. **Add-ons** (voice cloning, conectores custom, app móvil)
3. **Enterprise setup fees** ($2K one-time por deployment)
4. **Professional services** (custom integrations, training — Enterprise only)

### Unit Economics (Actualizado 31 Mayo 2026)

| Tier | Precio USD/mes | COGS | Margen Bruto | LTV (12 meses) |
|------|---------------|------|--------------|----------------|
| **Cloud Basic** | $7 | $1.20 | **83%** | $84 |
| **Cloud Pro** | $19 | $7.50 | **65%** | $228 |
| **Enterprise** | $499-999 | $230 | **54%** | $5,988-11,988 |

**COGS breakdown:**
- **Basic:** Gemini free tier $0 + AWS infra $0.50 + Stripe fee $0.50 + support $0.20
- **Pro:** Claude API $4.44 (30% uso) + Gemini paid $2.50 + infra $3.00 + support $0.56
- **Enterprise:** Support Slack 4h SLA $150 + onboarding amortizado $50 + Stripe $30

**Justificación margen:**
- Basic 83% = freemium hook, objetivo conversión a Pro
- Pro 65% = tier principal revenue, balance precio/valor óptimo
- Enterprise 54% = incluye high-touch support + custom dev (margen menor esperado)

---

## 🎯 PROPUESTA DE VALOR — POR SEGMENTO

### 1. **On-Premise vs Cloud** (Diferenciador Core)

| Aspecto | On-Premise (Self-Hosted) | Cloud (SaaS) |
|---------|-------------------------|--------------|
| **Deploy** | Cliente instala en su PC Windows | Tenant aislado en servidor Jarvis |
| **Data privacy** | ✅ 100% local, zero cloud | ⚠️ Encrypted cloud storage |
| **Funciona offline** | ✅ Sí (Ollama + Whisper local) | ❌ Requiere internet |
| **Actualizaciones** | Manual (git pull) | Automáticas transparentes |
| **Acceso móvil** | ❌ Solo desde PC instalada | ✅ Web + apps iOS/Android (roadmap) |
| **Setup complejidad** | Media (script PowerShell 10 min) | Baja (signup 2 min) |
| **Costo infra cliente** | GPU recomendada (opcional) | $0 (incluido en suscripción) |
| **Ideal para** | Profesionales técnicos, data sensible | Equipos remotos, no-técnicos |

**Tiers por modelo:**
- **On-premise:** Free, Cloud Basic (opcional), Cloud Pro (opcional), Enterprise (obligatorio)
- **Cloud:** Cloud Basic, Cloud Pro, Enterprise (VPC dedicado)

### 2. **Español-First** (Ventaja Competitiva LATAM)

**Por qué importa:**
- Competidores (ChatGPT, Notion AI, Rewind) son inglés-primero con traducciones parcheadas
- Comandos de voz en español tienen baja accuracy en modelos globales (30-40% error rate)
- LATAM representa $127B mercado SaaS 2026, creciendo 18% anual

**Implementación Jarvis:**
- ✅ UI 100% español nativo (no i18n de inglés)
- ✅ Faster-whisper fine-tuned en español mexicano (97% accuracy vs 68% Whisper base)
- ✅ Edge-TTS voces latinas naturales (no robóticas)
- ✅ NLP optimizado para modismos LATAM ("ahorita", "órale", slang argentino/mexicano)
- ✅ Documentación + soporte en español (no auto-traducido)

**Resultado:** 3x mejor UX voice vs competencia en español → menor churn, mayor adopción.

### 3. **LATAM Pricing** (PPP-Adjusted)

**Problema:** Precios globales USD son prohibitivos para LATAM (ChatGPT Plus $20 = $430 MXN, 30% salario mínimo México)

**Solución Jarvis:**

| Tier | USD/mes | MXN/mes (anual) | MXN/mes (mensual) | % vs Competencia |
|------|---------|----------------|-------------------|------------------|
| Cloud Basic | $7 | $140 | $160 | **65% más barato** que ChatGPT Plus |
| Cloud Pro | $19 | $380 | $430 | Par con ChatGPT pero con **10x features** |
| Enterprise | $499-999 | $10K-20K | — | **50% más barato** que Salesforce Einstein |

**Incentivos adicionales LATAM:**
- 🇲🇽 Facturación CFDI 4.0 (legal México)
- 💳 Pagos SPEI + Mercado Pago (no solo Stripe tarjeta)
- 🎓 50% descuento estudiantes .edu
- 🏢 30% descuento nonprofits verificados

---

## 📋 PRICING PLANS — TABLA DEFINITIVA

### **Free Tier** — $0/mes (Freemium Hook)
**Objetivo:** Conversión a Cloud Basic en 14-30 días

| Límite | Valor |
|--------|-------|
| Comandos | 50/mes (~1.6/día) |
| LLM | Solo Ollama local (Qwen, Llama) |
| Integraciones | Obsidian read-only |
| Deploy | Self-hosted obligatorio |
| Soporte | Community Discord |

**Features:**
- ✅ Asistente voz español/inglés
- ✅ Búsqueda semántica Obsidian
- ✅ Funciona 100% offline
- ❌ Sin Claude/Gemini cloud
- ❌ Sin email, calendario, APIs

---

### **Cloud Basic** — $7 USD/mes ($140 MXN anual)
**Objetivo:** Profesionales entry-level, estudiantes, early adopters

| Límite | Valor |
|--------|-------|
| Comandos | 500/mes (~16/día) |
| LLM | Gemini Flash free + Ollama |
| Integraciones | Obsidian + 1 calendario (Google/Outlook) |
| Deploy | Self-hosted o cloud |
| Storage | 5 GB cloud backups |
| Soporte | Email 48h |

**Features adicionales vs Free:**
- ✅ Routing inteligente IA (Gemini fast, Ollama privacy)
- ✅ Comandos programados (recordatorios, agenda diaria)
- ✅ Integración calendario completa (crear/editar eventos)
- ✅ Memoria persistente cross-sesiones
- ✅ Obsidian avanzado (crear/editar notas, templates)

**Conversión esperada:** 15% Free → Basic en 30 días

---

### **Cloud Pro** — $19 USD/mes ($380 MXN anual)
**Objetivo:** Founders, power users, consultores, traders

| Límite | Valor |
|--------|-------|
| Comandos | 3,000/mes (~100/día) + overflow $0.01/cmd |
| LLM | Claude Sonnet (30%) + Gemini Pro paid (40%) + Ollama (30%) |
| Integraciones | Todas nativas + 3 webhooks custom |
| Deploy | Self-hosted o cloud |
| Storage | 25 GB |
| Soporte | Email + chat 24h, prioritario |

**Features adicionales vs Basic:**
- ✅ **Claude API ilimitado** — tareas complejas, razonamiento profundo
- ✅ **Workflows completos** — "genera reporte, envía email, actualiza Obsidian"
- ✅ **Ejecución código avanzada** — scripts con APIs externas (Stripe, Shopify, CRM)
- ✅ **Email automation** — leer, responder, drafts, seguimiento
- ✅ **Telegram bot personal** — responde según contexto vault
- ✅ **Comandos custom** — shortcuts voice personalizados
- ✅ **Análisis datos** — Excel/CSV, gráficos, insights
- ✅ **Actualizaciones beta** anticipadas

**ROI justificado:** 10h/semana ahorradas × $50/hora = **$2,000/mo value** → pricing $19 es **100x ROI**

---

### **Enterprise On-Premise** — $499-999 USD/mes ($10K-20K MXN)
**Objetivo:** Corporativos, bufetes, clínicas, fondos inversión

| Límite | Valor |
|--------|-------|
| Comandos | Ilimitado (fair use <100k/mes) |
| LLM | **Cliente BYOK** (trae API keys) — Jarvis NO cobra por IA |
| Integraciones | Custom ilimitadas + 5h dev/mes incluidas |
| Deploy | **100% self-hosted** (Docker/K8s en infra cliente) |
| Storage | Ilimitado on-premise |
| Usuarios | Ilimitados |
| Soporte | Slack 4h SLA + onboarding 1-on-1 |

**Pricing escalado:**
- Base $499/mo: hasta 10 usuarios
- Mid $999/mo: hasta 50 usuarios
- Custom $2,999/mo: ilimitados

**Features Enterprise-only:**
- ✅ **Zero-knowledge architecture** — nada sale de servers cliente
- ✅ **Air-gapped mode** — funciona 100% offline (Ollama + Whisper)
- ✅ **SSO enterprise** — SAML/LDAP + RBAC granular
- ✅ **Compliance-ready** — GDPR, HIPAA-ready, SOC 2 roadmap
- ✅ **SLA 99.9% uptime** + penalización por downtime
- ✅ **Soporte 4h response critical** — engineer on-call
- ✅ **White-label option** — rebrandear como herramienta interna
- ✅ **Setup fee $2,000** — deployment + config inicial

**Ejemplo pricing real:**
- Bufete legal 25 abogados, on-prem, 2 integraciones custom (CRM + DMS), priority SLA
- Cálculo: $999 base + $2K setup (amortizado 12 meses = $167/mo) = **$1,166/mo año 1**
- vs Clio (legal CRM) $89/user × 25 = $2,225/mo → **Jarvis 48% más barato**

---

## 🏗️ ESTRUCTURA LEGAL VENDIBLE

### 1. **Modelo de Licenciamiento**

**Tipo:** SaaS por suscripción (México)

| Aspecto | Detalle |
|---------|---------|
| **Licencia** | Uso no exclusivo mientras dure suscripción activa |
| **Ownership data** | Cliente es 100% dueño de sus datos (zero-knowledge) |
| **Términos** | Estándar SaaS México (Términos de Servicio + Política Privacidad) |
| **Compliance** | LFPDPPP (ley datos personales México), GDPR-ready |
| **Renovación** | Automática mensual/anual vía Stripe |
| **Cancelación** | Cualquier momento, data exportable (portabilidad) |

**Documento legal base:** Template SaaS México adaptado (disponible en `docs/legal/`).

### 2. **APIs de Terceros (Legal)**

**Problema:** Jarvis usa Claude API, Gemini API, Ollama — ¿quién es responsable de costos y términos?

**Solución por tier:**

| Tier | Modelo API | Responsabilidad | Compliance |
|------|-----------|----------------|-----------|
| **Free, Basic, Pro** | Jarvis intermedia (API keys nuestras) | Nosotros absorbemos costo IA, incluido en suscripción | Cliente acepta que usamos Anthropic/Google (disclosure en TOS) |
| **Enterprise BYOK** | Cliente trae sus API keys propias | Cliente 100% responsable (facturas directas Anthropic/Google) | Zero liability nuestra, cliente acepta términos Anthropic/Google directo |

**Protección legal:**
- ✅ Términos de Servicio incluyen cláusula: "Cliente acepta que Jarvis usa proveedores IA terceros (Claude, Gemini) sujetos a sus propios términos"
- ✅ **NO almacenamos conversaciones** en nuestros servers (solo metadata billing)
- ✅ **NO entrenamos modelos** con datos de clientes
- ✅ Enterprise BYOK: **zero liability** — cliente gestiona sus propias API keys

### 3. **Facturación México**

| Aspecto | Detalle |
|---------|---------|
| **Entidad** | Persona Física con Actividad Empresarial o SA de CV (a constituir) |
| **CFDI 4.0** | Facturas automáticas vía Facturapi o sistema propio |
| **Métodos pago** | Stripe (tarjeta internacional), SPEI (México), Mercado Pago |
| **Invoice timing** | Automático al cobro (mensual/anual según plan) |
| **Retenciones** | Aplicables según régimen fiscal cliente (10% servicios B2B México) |

**Status actual:** Pendiente constitución entidad legal (recomendado ANTES de primer cliente pagando).

**Acción requerida:** Agenda con contador ESTA semana para:
1. Definir régimen fiscal (RESICO, RIF, SA de CV)
2. Alta SAT + RFC
3. Configurar Stripe México (requiere cuenta bancaria empresarial)

### 4. **Compliance y Riesgo Legal**

**Mitigación de riesgos:**

| Riesgo | Mitigación |
|--------|-----------|
| **Responsabilidad por uso indebido** | TOS cláusula clara: "Jarvis es herramienta, NO asesoría. Usuario responsable de uso" |
| **Data breach** | Arquitectura zero-knowledge (no almacenamos data sensible) + encrypt at rest |
| **Costos API runaway** | Fair use policy + límites por tier + throttling automático |
| **Trademark "Jarvis"** | Bajo riesgo (Marvel/Disney no registraron "Jarvis AI" México) — registrar marca MX $3K preventivo |
| **Compliance GDPR** | Self-hosted + zero-knowledge = automáticamente compliant (no data transfer EU) |
| **HIPAA (si clientes salud)** | Enterprise tier incluye BAA (Business Associate Agreement) + audit logs |

**Requerimientos legales adicionales:**
- ❌ NO requiere licencia especial (es software, no servicio regulado)
- ❌ NO requiere PCI-DSS (si integramos pagos directos → outsourcing a Stripe resuelve)
- ✅ Sí requiere Aviso de Privacidad LFPDPPP (template disponible)

---

## 🎯 GO-TO-MARKET — PRIMER CLIENTE EN 30 DÍAS

### **Meta:** 1 cliente pagando $19/mo (Cloud Pro) antes del 30 junio 2026

**5 Pasos Ejecutables (del MEMORY.md):**

#### **Paso 1: Empaquetar MVP Vendible** (Semana 1: 1-7 junio)
- [ ] Landing page funcional jarvis-ai.mx
  - Hero: "Tu segundo cerebro que además tiene manos"
  - Demo video 90seg (screen recording + voz Emmanuel)
  - Pricing table (Free/Basic/Pro/Enterprise)
  - Formulario early access (Tally/Typeform → Telegram)
- [ ] Repo público GitHub con README comercial
- [ ] Script instalación automatizado (PowerShell/Python)
- [ ] Config wizard CLI (Obsidian + calendario)
- [ ] Video tutorial 5min

**Entregable:** Link jarvis-ai.mx live + 10 early access invites

---

#### **Paso 2: Beta Testers Gratuitos** (Semana 2: 8-14 junio)
- [ ] Reclutar 3 beta testers ICP:
  - LinkedIn post Emmanuel (storytelling personal)
  - Grupo PyMEs México (Facebook/WhatsApp)
  - Comunidad Obsidian LATAM (Reddit r/ObsidianMD, Discord)
- [ ] Onboarding calls 30min c/u:
  - Instalar + configurar 1 integración
  - Definir 3 tareas Jarvis debe hacer esta semana
- [ ] Feedback loop diario (Telegram group)
- [ ] Iterar: fix críticos <24h

**Entregable:** 3 testimonios escritos + 1 video + lista 10 features pedidas

---

#### **Paso 3: Convertir 1 Beta a Cliente Pagando** (Semana 3: 15-21 junio)
- [ ] Identificar el más engaged (métricas: comandos/día, feedback positivo)
- [ ] Sales call 1-on-1 (Emmanuel):
  - Mostrar valor entregado ("ahorraste X horas esta semana")
  - Ofrecer Cloud Pro **50% descuento lifetime** ($9.5/mo) si paga hoy
  - Payment link Stripe listo en llamada
- [ ] Onboarding a producción:
  - Migrar free → Pro (activar Claude API)
  - Facturación automática
  - SLA informal "bugs <4h"

**Entregable:** $9.5 USD recurrente + CFDI emitido + caso éxito documentado

---

#### **Paso 4: Industrializar Onboarding** (Semana 4: 22-28 junio)
- [ ] Onboarding self-service:
  - Video tutorial 15min (instalación + setup + primeros comandos)
  - Docs interactivas (Docusaurus o Notion público)
  - Script diagnóstico `jarvis doctor` (valida instalación)
- [ ] Automatizar billing:
  - Stripe Billing (plans + checkout)
  - Webhook Stripe → backend (activa/desactiva cuenta)
  - Email templates (bienvenida, invoice, churn prevention)
- [ ] Dashboard admin básico:
  - Ver clientes activos, comandos/día, health

**Entregable:** 2do cliente adquirido sin involvement Emmanuel

---

#### **Paso 5: Growth Loop Inicial** (Semana 5+: 29 junio adelante)
- [ ] Contenido orgánico:
  - 1 post LinkedIn/semana: caso de uso cliente (con permiso)
  - 1 thread Twitter/semana: "Cómo Jarvis ahorró X horas en Y"
  - 1 video YouTube/mes: deep-dive integración
- [ ] Referral program:
  - Invita amigo → ambos 1 mes gratis
  - Link trackeable (Stripe + UTM)
- [ ] Paid ads micro-test ($500 MXN):
  - Facebook Ads a "Obsidian usuarios" + "Emprendedores LATAM"
  - Objetivo: 20 signups free → 2 conversiones Pro
- [ ] Community building:
  - Discord público "Jarvis AI LATAM"
  - Sección "Show & Tell" (usuarios comparten automations)

**Entregable:** 5 clientes pagando ($95 MRR mínimo) + canal adquisición validado

---

## 📊 PROYECCIÓN FINANCIERA AÑO 1

**Assumptions conservadores:**
- CAC: $120 (Product Hunt, content, Reddit)
- Churn mensual: 5% (Basic), 3% (Pro), 1% (Enterprise)
- Free → Basic conversión: 15%
- Basic → Pro upgrade: 8% anual

**Revenue proyectado:**

| Mes | Free Users | Basic | Pro | Enterprise | MRR | MRR Acumulado |
|-----|-----------|-------|-----|------------|-----|---------------|
| 1 | 50 | 5 | 1 | 0 | $54 | $54 |
| 3 | 200 | 30 | 3 | 0 | $267 | $588 |
| 6 | 500 | 75 | 8 | 1 | $1,151 | $4,302 |
| 12 | 1,200 | 180 | 20 | 2 | $2,638 | $18,456 |

**ARR Year 1:** ~$31,656 (sin lifetime deals ni add-ons)

**Break-even:** Mes 9 (asumiendo $3K/mo burn: $2K dev Emmanuel + $500 infra + $500 marketing)

---

## ✅ VALIDACIÓN COMPETITIVA — RESUMEN

**Jarvis pricing vs competencia global:**

| Competidor | Entry | Mid | Ventaja Jarvis |
|-----------|-------|-----|----------------|
| **ChatGPT Plus** | $20/mo | — | Basic $7 (65% cheaper) + ejecuta acciones reales |
| **Notion AI** | $10/mo | — | Pro $19 ejecuta, Notion solo sugiere |
| **Rewind AI** | $19/mo | — | Pro $19 mismo precio pero Jarvis es accionable |
| **Manus AI** | $20/mo | $200/mo | Basic $7 más accesible, Enterprise $499 vs $200 pero más features |
| **browser-use** | $100/mo | $500/mo | Pro $19 vs $100 (81% cheaper) |

**Posicionamiento validado:**
✅ **Basic $7:** ÚNICO <$10 con voice + self-hosted  
✅ **Pro $19:** Sweet spot — par con líderes pero 10x features  
✅ **Enterprise $499:** Competitivo, customizable, 50% cheaper que Salesforce Einstein

---

## 🚀 PRÓXIMOS PASOS INMEDIATOS (24-48 HORAS)

### **Emmanuel debe decidir:**

1. **¿Modelo deploy MVP?**
   - ✅ **RECOMENDADO:** Híbrido — Basic/Pro self-hosted, Enterprise cloud
   - Justificación: Reduce COGS inicial, target técnico aguanta install

2. **¿API keys IA?**
   - ✅ **RECOMENDADO:** Nosotros absorbemos (Basic/Pro), Enterprise BYOK
   - Justificación: Onboarding limpio, margen predecible

3. **¿Facturación legal?**
   - ⚠️ **CRÍTICO:** Constituir entidad ANTES de primer cliente
   - Acción: Agendar contador ESTA semana

4. **¿Pricing inicial?**
   - ✅ **RECOMENDADO:** Primeros 10 clientes = 50% OFF lifetime
   - Justificación: Crea embajadores, cashflow inmediato

5. **¿Prioridad integración post-Obsidian?**
   - ✅ **RECOMENDADO:** Google Calendar + Gmail
   - Justificación: Universal, alta demanda ICP

6. **¿Nombre comercial final?**
   - ✅ **RECOMENDADO:** Mantener "Jarvis AI" + registrar marca México ($3K)
   - Justificación: Riesgo Marvel bajo, brand equity ya construido

---

## 📄 ASSETS VENDIBLES GENERADOS

1. **Este documento** (`MODELO-NEGOCIO-VENDIBLE.md`) — Pitch deck base
2. **ONE-PAGER** (en MEMORY.md líneas 990-1102) — PDF para prospectos
3. **Pricing table** — Wireframe implementable web
4. **Legal templates** — TOS + Política Privacidad (pendiente crear)
5. **Demo script** — Video 90seg (DEMO_SCRIPT.md en repo)

---

## 📚 FUENTES DE VALIDACIÓN

- 26 fuentes competitivas trianguladas (ver MEMORY.md líneas 1412-1448)
- Research HackerNews (5 threads)
- Benchmarks SaaS México 2026
- Análisis Computer Use Agents (OpenHands, Manus AI, browser-use)

---

**Fecha creación:** 2026-05-31  
**Owner:** Emmanuel Pedraza (@Corgipollo)  
**Próxima revisión:** Post primer cliente pagando (target 30 junio 2026)
