# Jarvis AI — Demo Screencast Script (2-3 min)

> **Caso de uso:** Lead Research Automation con Scoring Automático  
> **Objetivo:** Mostrar Jarvis investigando un lead B2B y generando outreach personalizado  
> **Duración:** 2:30 minutos  
> **Audiencia:** Founders, sales teams, growth marketers

---

## Pre-Setup (antes de grabar)

✅ Jarvis corriendo en background  
✅ Brave browser cerrado (se abrirá en vivo)  
✅ Terminal lista en `C:\Users\Emmanuel\Documents\JarvisAI\`  
✅ Audio de micrófono claro (narración en vivo o voice-over post)  
✅ Pantalla limpia, sin notificaciones  
✅ Ejemplo de lead real: **"Acme Corp"** (empresa ficticia pero realista)

---

## SCRIPT CON TIMECODES

### 00:00 - 00:15 | INTRO (15s)
**Visual:** Pantalla negra → fade in a escritorio limpio con logo Jarvis  
**Narración:**
> "Imagina que necesitas investigar 20 leads al día. Website, LinkedIn, tech stack, funding... normalmente toma 30 minutos por lead. Mira cómo Jarvis lo hace en 2 minutos."

**Acción:** Mostrar Jarvis icon en system tray

---

### 00:15 - 00:30 | COMANDO DE VOZ (15s)
**Visual:** Abrir interfaz Jarvis (Electron app o terminal según tu setup)  
**Narración (usuario hablando a Jarvis):**
> "Jarvis, investiga a Acme Corp, es una startup fintech en San Francisco."

**Acción:** 
- Micrófono icon activo (mostrando que escucha)
- Texto aparece en pantalla mientras hablas (STT en vivo)
- Jarvis responde: *"Entendido, investigando Acme Corp..."*

---

### 00:30 - 01:20 | RESEARCH EN ACCIÓN (50s)

**Visual:** Split screen o picture-in-picture mostrando:
- **Izquierda:** Terminal con logs de Jarvis en tiempo real
- **Derecha:** Navegador automatizado (Brave) abriendo tabs

**Acciones automáticas visibles:**
1. **00:30-00:40** | Google search "Acme Corp fintech"  
   → Abre website  
   → Scrapes About page, Team page, Jobs page  
   **Log en terminal:** `✓ Website scraped: 3 pages, 2,450 words`

2. **00:40-00:50** | LinkedIn company page  
   → Muestra cantidad de empleados (ej: 45)  
   → Captura industry, HQ location  
   **Log:** `✓ LinkedIn data: 45 employees, Series A, SF-based`

3. **00:50-01:00** | BuiltWith / Wappalyzer  
   → Detecta tech stack (React, AWS, Stripe)  
   **Log:** `✓ Tech stack detected: React, Node.js, AWS, Stripe`

4. **01:00-01:10** | Crunchbase scrape  
   → Funding: Series A, $8M, 6 meses ago  
   **Log:** `✓ Funding data: $8M Series A (6 months ago)`

5. **01:10-01:20** | Google News search  
   → Encuentra PR reciente (ej: "Acme Corp raises $8M...")  
   **Log:** `✓ News: Recent PR, product launch Q2 2026`

**Narración durante este bloque:**
> "Jarvis abre el browser, scrapes el website, LinkedIn, detecta el tech stack, busca funding data y noticias recientes. Todo en paralelo."

---

### 01:20 - 01:50 | SCORING AUTOMÁTICO (30s)

**Visual:** Jarvis muestra tabla de scoring en terminal o interfaz

**Output en pantalla:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LEAD: Acme Corp
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

RESEARCH SUMMARY:
- Fintech startup, 45 employees, SF-based
- Series A ($8M, 6 months ago)
- Tech stack: React, AWS, Stripe (premium tools)
- Hiring: 3 open positions (growth signal)
- Recent PR: Product launch Q2 2026

SCORING:
├─ FIT Score:        32/40
│  ├─ ICP Match:     15/15 ✓ (fintech, mid-size)
│  ├─ Pain Point:    12/15 ✓ (hiring = scaling pain)
│  └─ DM Access:      5/10 ⚠ (LinkedIn not connected)
│
├─ URGENCY Score:    24/30
│  ├─ Timing:        13/15 ✓ (funding 6mo ago, hiring)
│  ├─ Competitor:     8/10 ✓ (DIY tools detected)
│  └─ Growth:         5/5  ✓ (high growth)
│
└─ BUDGET Score:     22/30
   ├─ Revenue:        10/15 ~ (est. $2-5M ARR)
   ├─ Funding:         7/10 ✓ (Series A)
   └─ Tech Spend:      5/5  ✓ (premium stack)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL SCORE: 78/100
CLASSIFICATION: ✅ QUALIFIED
RECOMMENDATION: Immediate outreach
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Narración:**
> "Jarvis califica el lead en 3 dimensiones: FIT, URGENCY y BUDGET. Acme Corp obtiene 78/100 — es un lead calificado para outreach inmediato."

---

### 01:50 - 02:20 | OUTREACH GENERADO (30s)

**Visual:** Jarvis genera email personalizado automáticamente

**Output en pantalla:**
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OUTREACH GENERATED (PERSONALIZED)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Subject: Scaling Acme's ops post-Series A? 🚀

Hi [Founder Name],

Saw you raised $8M 6 months ago and now hiring 
for 3 roles — congrats on the momentum.

Quick question: as you scale from 45 to 100+ people, 
how are you planning to automate your [pain point: 
internal ops / customer onboarding / data processing]?

Most Series A fintechs we work with hit a wall 
around 50 people where DIY tools break down.

Built a 3-min case study showing how we helped 
[similar company] reduce ops time by 95% with 
AI automation.

Worth a 15-min call next week?

Best,
Emmanuel

P.S. Love the AWS + Stripe stack — makes integration 
seamless on our end.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Narración:**
> "Y genera un email personalizado con timing específico, pain point inferido y credibilidad técnica. Todo listo para enviar."

---

### 02:20 - 02:30 | CIERRE (10s)

**Visual:** Fade to logo Jarvis + texto en pantalla

**Texto overlay:**
```
⚡ Jarvis AI
━━━━━━━━━━━━━━━━━━
30 min → 2 min
20 leads/día investigados
Scoring + Outreach automático
```

**Narración:**
> "De 30 minutos a 2 minutos. De 2 leads al día a 20. Eso es Jarvis."

**CTA en pantalla:**
```
Prueba Jarvis: jarvis-ai.com
GitHub: github.com/Corgipollo/JarvisAI
```

**Audio:** Fade out con música sutil (opcional)

---

## POST-PRODUCCIÓN (Mínima)

1. **Grabar con OBS Studio:**
   - Resolución: 1920x1080, 30fps
   - Audio: micrófono claro O voice-over post con edge-tts
   - Capturar ventana específica (Jarvis + Brave) para evitar distracciones

2. **Edición (opcional):**
   - Acelerar secciones del browser scraping a 1.5x-2x (no más de 20s de scraping en tiempo real)
   - Agregar overlay de texto para highlighting key points
   - Música de fondo sutil (opcional, no distraer de la narración)

3. **Export:**
   - MP4, H.264, 1920x1080, ~5-10MB
   - Duración final: 2:20 - 2:40

---

## SUBIDA YOUTUBE (Unlisted)

**Título:**  
`Jarvis AI — Lead Research Automation Demo (2 min)`

**Descripción:**
```
Demostración de Jarvis AI automatizando research de leads B2B.

En este video:
✓ Comando de voz → investigación automática
✓ Website scraping, LinkedIn, tech stack, funding data
✓ Scoring automático (FIT/URGENCY/BUDGET)
✓ Outreach email personalizado generado

Tiempo: 30 min → 2 min
Output: Lead calificado + email listo para enviar

━━━━━━━━━━━━━━━━━━
Jarvis AI: Asistente personal voice-first para founders
GitHub: https://github.com/Corgipollo/JarvisAI
Stack: FastAPI + React + faster-whisper + Claude API

Built by @Corgipollo
```

**Tags:**  
`ai automation, lead research, sales automation, voice assistant, jarvis ai, b2b sales, lead qualification, fastapi, react, claude api`

**Visibility:**  
🔒 Unlisted (solo personas con link)

---

## EMBED CODE PARA LANDING

Una vez subido, YouTube da el código embed. Ejemplo:

```html
<!-- Responsive embed -->
<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%;">
  <iframe 
    src="https://www.youtube.com/embed/YOUR_VIDEO_ID" 
    style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;" 
    frameborder="0" 
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
    allowfullscreen>
  </iframe>
</div>
```

**Para landing page Jarvis:**
- Colocar ARRIBA del fold (hero section)
- Título encima: "Ve Jarvis en Acción — 2 Minutos"
- CTA debajo: "Prueba Gratis" o "Descarga Beta"

---

## CHECKLIST PRE-GRABACIÓN

- [ ] Jarvis backend corriendo (`python backend/main.py`)
- [ ] Frontend Electron listo (o terminal si es CLI-only)
- [ ] Brave browser cerrado (arrancar limpio)
- [ ] Lead de ejemplo preparado (Acme Corp o real sanitizado)
- [ ] Scripts de research funcionando (probar con `pytest` antes)
- [ ] Audio de micrófono testeado (sin eco/ruido)
- [ ] OBS configurado (captura de ventana, 1920x1080, 30fps)
- [ ] Narración ensayada (opcional: hacer voice-over post con edge-tts)

---

## ALTERNATIVA: Voice-Over Post-Producción

Si prefieres no narrar en vivo:

1. **Grabar silencioso:** Solo capturar pantalla con acciones
2. **Script de narración:** Usar el texto de arriba
3. **Generar audio con edge-tts:**
   ```bash
   edge-tts --voice es-MX-DaliaNeural --text "$(cat narration.txt)" --write-media voiceover.mp3 --rate=+5%
   ```
4. **Merge en ffmpeg:**
   ```bash
   ffmpeg -i screencast.mp4 -i voiceover.mp3 -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 final.mp4
   ```

---

**Creado:** 2026-05-31  
**Caso base:** Lead Qualification Framework (2026-05-30)  
**Output esperado:** Video 2-3min, YouTube unlisted, embed listo para landing
