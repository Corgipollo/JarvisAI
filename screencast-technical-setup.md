# Jarvis AI Screencast — Setup Técnico

> Guía paso a paso para grabar, editar y subir el demo a YouTube

---

## 1. INSTALACIÓN OBS STUDIO (Si no lo tienes)

### Opción A: Descargar oficial
1. Ir a: https://obsproject.com/download
2. Descargar OBS Studio para Windows
3. Instalar (siguiente → siguiente → finish)

### Opción B: winget (más rápido)
```bash
winget install OBSProject.OBSStudio
```

---

## 2. CONFIGURACIÓN OBS (Primera vez)

### Settings básicos (File → Settings):

**Video:**
- Base Resolution: 1920x1080
- Output Resolution: 1920x1080
- FPS: 30

**Output:**
- Output Mode: Simple
- Recording Quality: High Quality, Medium File Size
- Recording Format: MP4
- Encoder: NVIDIA NVENC H.264 (si tienes RTX) o x264

**Audio:**
- Sample Rate: 48kHz
- Desktop Audio: Default (para capturar audio del sistema si hace falta)
- Mic/Auxiliary Audio: Tu micrófono

---

## 3. ESCENA PARA SCREENCAST

### Crear escena nueva:
1. En panel "Scenes", click `+` → nombre: `Jarvis Demo`

### Agregar fuentes:
1. **Window Capture:**
   - Click `+` en "Sources" → "Window Capture"
   - Nombre: `Jarvis Terminal`
   - Window: `[python.exe]: Jarvis AI` (seleccionar la ventana de Jarvis)
   - Capture Method: Windows 10 (1903+)
   - ✓ Capture Cursor

2. **Window Capture (segunda):**
   - Click `+` → "Window Capture"
   - Nombre: `Brave Browser`
   - Window: `[brave.exe]: Brave` (seleccionar ventana del browser)
   - ✓ Capture Cursor

### Layout recomendado:
- **Split screen:** Terminal izquierda (50%), Browser derecha (50%)
- **Full screen alternado:** Cambiar entre ambos según el momento del script

**Tip:** Usar `Studio Mode` (botón abajo) para pre-visualizar cambios antes de hacerlos en vivo

---

## 4. PRE-FLIGHT CHECK (Antes de grabar)

### Checklist técnico:
```bash
# 1. Backend Jarvis corriendo
cd C:\Users\Emmanuel\Documents\JarvisAI\backend
python main.py
# Esperar: "Uvicorn running on http://127.0.0.1:8000"

# 2. Frontend (si usas Electron)
cd C:\Users\Emmanuel\Documents\JarvisAI\frontend
npm run dev
# O: npm start (según tu setup)

# 3. Brave cerrado (arrancar limpio)
taskkill /F /IM brave.exe 2>nul

# 4. Test de micrófono en OBS
# Hablar y ver que la barra verde de "Mic/Aux" se mueva
```

### Prep del caso de ejemplo:
- **Lead:** Acme Corp (ficticio pero realista)
- **Data simulada:** Tener JSON/mock data listo SI el scraping real puede fallar
- **Comando exacto:** "Jarvis, investiga a Acme Corp, es una startup fintech en San Francisco"

---

## 5. GRABACIÓN (Paso a Paso)

### Proceso:
1. **OBS:** Click `Start Recording` (botón abajo derecha)
2. **Esperar 3 segundos** (para tener margen de corte después)
3. **Ejecutar el script** (seguir `screencast-demo-script.md`)
4. **Terminar narración**
5. **Esperar 3 segundos**
6. **OBS:** Click `Stop Recording`

### Tips durante grabación:
- **No te apures:** Habla despacio y claro
- **Pausas:** OK pausar entre secciones (se editará después)
- **Errores:** Si te equivocas, pausar 5 segundos, rehacer desde esa sección (luego cortas en edición)
- **Mouse:** Movimientos lentos, no clicks frenéticos

### Archivo generado:
- Ubicación: `C:\Users\Emmanuel\Videos\` (por defecto OBS)
- Nombre: `2026-05-31 XX-XX-XX.mp4` (timestamp automático)
- Renombrar a: `jarvis-demo-raw.mp4`

---

## 6. POST-PRODUCCIÓN (Opcional, Mínima)

### Opción A: Sin edición (más rápido)
Si la grabación salió bien de una toma:
- **Solo:** Cortar primeros/últimos 3 segundos → listo
- Herramienta: ffmpeg (comando abajo)

### Opción B: Edición ligera (recortes + aceleración)
Herramientas gratis:
- **DaVinci Resolve** (más profesional): https://www.blackmagicdesign.com/products/davinciresolve
- **Shotcut** (más simple): https://shotcut.org/

**Ediciones comunes:**
1. Cortar primeros/últimos segundos en silencio
2. Acelerar sección de scraping (00:30-01:20) a 1.5x-2x si es muy lento
3. Agregar overlay de texto (opcional):
   - "✓ Website scraped"
   - "✓ LinkedIn data"
   - "SCORE: 78/100 — QUALIFIED"

### ffmpeg para cortar inicio/final:
```bash
# Cortar primeros 3s y últimos 3s
ffmpeg -i jarvis-demo-raw.mp4 -ss 00:00:03 -to 00:02:33 -c copy jarvis-demo-trimmed.mp4
```

### ffmpeg para acelerar sección específica:
```bash
# Acelerar de 00:30 a 01:20 a 1.5x
# (Complejo, mejor usar DaVinci/Shotcut para esto)
```

---

## 7. VOICE-OVER POST (Alternativa)

Si prefieres no narrar en vivo:

### Paso 1: Grabar video mudo
- Seguir sección 5, pero sin hablar
- Solo capturar acciones en pantalla

### Paso 2: Crear script de narración
- Tomar texto de `screencast-demo-script.md`
- Guardarlo en `narration-script.txt` (texto plano)

### Paso 3: Generar audio con edge-tts
```bash
# Instalar edge-tts si no lo tienes
pip install edge-tts

# Generar voice-over
edge-tts \
  --voice es-MX-DaliaNeural \
  --text "$(cat narration-script.txt)" \
  --write-media voiceover.mp3 \
  --rate=+5%

# Voces alternativas:
# es-MX-JorgeNeural (voz masculina México)
# en-US-GuyNeural (voz masculina US, profesional)
```

### Paso 4: Merge video + audio
```bash
ffmpeg -i jarvis-demo-trimmed.mp4 -i voiceover.mp3 \
  -c:v copy -c:a aac \
  -map 0:v:0 -map 1:a:0 \
  jarvis-demo-final.mp4
```

**Resultado:** `jarvis-demo-final.mp4` con voice-over profesional

---

## 8. SUBIDA A YOUTUBE

### Paso 1: Ir a YouTube Studio
1. Abrir: https://studio.youtube.com
2. Click: `CREATE` → `Upload videos`
3. Arrastrar `jarvis-demo-final.mp4`

### Paso 2: Detalles del video

**Título:**
```
Jarvis AI — Lead Research Automation Demo (Real Case)
```

**Descripción:**
```
Demostración real de Jarvis AI automatizando investigación de leads B2B.

🎯 En este video:
✓ Comando de voz → investigación automática
✓ Website scraping, LinkedIn, tech stack, funding data
✓ Scoring automático (FIT/URGENCY/BUDGET: 0-100)
✓ Outreach email personalizado generado al instante

⚡ Resultados:
• Tiempo: 30 min → 2 min (reducción 93%)
• Output: Lead calificado + email listo para enviar
• Escalable: 20+ leads al día vs 2 manualmente

━━━━━━━━━━━━━━━━━━
🤖 Jarvis AI
Asistente personal voice-first para founders y sales teams

📂 GitHub: https://github.com/Corgipollo/JarvisAI
🛠 Stack: FastAPI + React + faster-whisper + Claude API
👤 Built by Emmanuel Pedraza (@Corgipollo)

━━━━━━━━━━━━━━━━━━
🔗 Links:
• Landing: [TU_LANDING_AQUI]
• Demo request: [CALENDLY_O_EMAIL]
• Docs: [DOCS_SI_APLICA]

━━━━━━━━━━━━━━━━━━
⏱ Timestamps:
00:00 - Intro
00:15 - Comando de voz
00:30 - Research automático
01:20 - Scoring (FIT/URGENCY/BUDGET)
01:50 - Outreach personalizado generado
02:20 - Cierre + CTA

#AI #Automation #LeadResearch #SalesAutomation #VoiceAI
```

**Thumbnail (Opcional pero recomendado):**
- Crear con Canva: https://www.canva.com
- Dimensiones: 1280x720 px
- Texto grande: "30 min → 2 min"
- Subtítulo: "Lead Research Automation"
- Imagen de Jarvis logo o screenshot del scoring

### Paso 3: Configuración de visibilidad

**Audience:** No es para niños

**Visibility:**
- ✅ **Unlisted** (solo personas con el link pueden verlo)
- NO "Private" (eso bloquea embeds)
- NO "Public" (a menos que quieras que aparezca en búsquedas)

**Monetization:** Desactivar (video demo)

**Tags:**
```
ai automation, lead research, sales automation, voice assistant, jarvis ai, b2b sales, lead qualification, fastapi, react, claude api, sales tools, automation demo, ai agent, voice ai, sales enablement
```

### Paso 4: Click `PUBLISH`

Esperar ~2-5 minutos de procesamiento.

---

## 9. OBTENER EMBED CODE

### Una vez publicado:

1. Ir al video en YouTube
2. Click `SHARE` (botón abajo del video)
3. Click `Embed`
4. **Copiar el código** que aparece (ejemplo abajo)

### Código embed base:
```html
<iframe 
  width="560" 
  height="315" 
  src="https://www.youtube.com/embed/YOUR_VIDEO_ID" 
  title="YouTube video player" 
  frameborder="0" 
  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" 
  referrerpolicy="strict-origin-when-cross-origin" 
  allowfullscreen>
</iframe>
```

**Personalización recomendada:**

```html
<!-- Responsive embed (se adapta a móviles) -->
<div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; background: #000;">
  <iframe 
    src="https://www.youtube.com/embed/YOUR_VIDEO_ID?rel=0&modestbranding=1" 
    style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;" 
    frameborder="0" 
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
    allowfullscreen>
  </iframe>
</div>
```

**Parámetros útiles en URL:**
- `?rel=0` — no mostrar videos relacionados al final
- `&modestbranding=1` — logo YouTube más discreto
- `&autoplay=1` — auto-play al cargar (usar con cuidado, UX puede ser molesto)
- `&start=15` — empezar en segundo 15 (si quieres skipear intro)

---

## 10. INTEGRACIÓN EN LANDING PAGE

### Ejemplo Hero Section con video:

```html
<!-- Landing de Jarvis AI -->
<section class="hero bg-gradient-to-br from-gray-900 to-gray-800 text-white py-20">
  <div class="container mx-auto px-4 max-w-6xl">
    
    <!-- Headline -->
    <h1 class="text-5xl font-bold text-center mb-4">
      Investiga 20 Leads al Día en Piloto Automático
    </h1>
    
    <p class="text-xl text-gray-300 text-center mb-12 max-w-3xl mx-auto">
      Jarvis AI hace research de leads B2B, scoring automático y genera outreach personalizado. 
      <span class="text-blue-400 font-semibold">30 minutos → 2 minutos.</span>
    </p>
    
    <!-- Video Demo (responsive) -->
    <div class="mb-12 max-w-4xl mx-auto">
      <div style="position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,0.5);">
        <iframe 
          src="https://www.youtube.com/embed/YOUR_VIDEO_ID?rel=0&modestbranding=1" 
          style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; border-radius: 12px;" 
          frameborder="0" 
          allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
          allowfullscreen>
        </iframe>
      </div>
      <p class="text-sm text-gray-400 text-center mt-3">
        ⏱ 2 minutos — Ve Jarvis en acción con un caso real
      </p>
    </div>
    
    <!-- CTAs -->
    <div class="flex flex-col sm:flex-row gap-4 justify-center">
      <a href="#signup" class="bg-blue-600 hover:bg-blue-700 text-white font-bold py-4 px-8 rounded-lg text-lg transition">
        Prueba Gratis
      </a>
      <a href="https://github.com/Corgipollo/JarvisAI" class="bg-gray-700 hover:bg-gray-600 text-white font-bold py-4 px-8 rounded-lg text-lg transition">
        Ver en GitHub
      </a>
    </div>
    
  </div>
</section>
```

### Alternativa: Modal de video (click para abrir)

```html
<!-- Thumbnail clickeable -->
<div class="video-thumbnail cursor-pointer" onclick="openVideoModal()">
  <img src="thumbnail.jpg" alt="Demo Jarvis AI" class="rounded-lg shadow-xl">
  <div class="play-button-overlay">▶️</div>
</div>

<!-- Modal (oculto por defecto) -->
<div id="videoModal" class="hidden fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center" onclick="closeVideoModal()">
  <div class="max-w-4xl w-full mx-4">
    <iframe 
      width="100%" 
      height="600" 
      src="https://www.youtube.com/embed/YOUR_VIDEO_ID?autoplay=1" 
      frameborder="0" 
      allowfullscreen>
    </iframe>
  </div>
</div>

<script>
function openVideoModal() {
  document.getElementById('videoModal').classList.remove('hidden');
}
function closeVideoModal() {
  document.getElementById('videoModal').classList.add('hidden');
}
</script>
```

---

## 11. MÉTRICAS POST-LAUNCH (Tracking)

### YouTube Analytics (importante):
1. Ir a YouTube Studio → Analytics
2. Métricas clave para demo:
   - **Average view duration:** ideal >70% (gente ve casi todo)
   - **Traffic sources:** ¿de dónde vienen? (embedded player = tu landing)
   - **Audience retention graph:** ¿dónde se van? (mejorar esa parte)

### A/B Testing ideas:
- **Thumbnail:** probar 2-3 versiones diferentes
- **Duración:** 2min vs 3min (más corto puede retener más)
- **Voz:** edge-tts masculina vs femenina
- **CTA:** "Prueba Gratis" vs "Descarga Beta" vs "Agenda Demo"

---

## 12. CHECKLIST FINAL PRE-LAUNCH

### Antes de hacer público el video en landing:

- [ ] Video subido y procesado en YouTube
- [ ] Visibility = Unlisted (verificar)
- [ ] Thumbnail custom agregado (opcional pero +CTR)
- [ ] Descripción completa con links
- [ ] Embed code copiado y testeado
- [ ] Landing page actualizada con embed
- [ ] Landing testeada en mobile/desktop
- [ ] Video se reproduce correctamente en landing
- [ ] Analytics de YouTube activado
- [ ] Compartir link con 2-3 personas para feedback inicial

---

## TROUBLESHOOTING

### "El video no se embebe en mi landing"
- **Causa:** Video en "Private" en vez de "Unlisted"
- **Fix:** YouTube Studio → Video → Visibility → Unlisted → Save

### "Audio no se escucha bien"
- **Causa:** Micrófono muy bajo o ruido de fondo
- **Fix:** OBS Settings → Audio → Mic/Aux → Ajustar volumen a -6dB aprox
- **Fix 2:** Usar voice-over post con edge-tts (más limpio)

### "Video muy pesado (>50MB)"
- **Causa:** Bitrate muy alto en OBS
- **Fix:** Comprimir con ffmpeg:
  ```bash
  ffmpeg -i jarvis-demo-final.mp4 -vcodec h264 -crf 28 jarvis-demo-compressed.mp4
  ```
  (CRF 23-28 es buen balance calidad/tamaño)

### "Scraping falla durante grabación en vivo"
- **Prevención:** Tener mock data listo como fallback
- **Fix:** Editar el JSON de response en el código para que SIEMPRE devuelva data hardcodeada durante demos
  ```python
  # En research.py (solo para demos)
  if os.getenv("DEMO_MODE") == "1":
      return MOCK_DATA_ACME_CORP
  ```

---

**Creado:** 2026-05-31  
**Tiempo estimado total:** 1-2 horas (setup + grabación + upload)  
**Output:** Video demo en YouTube unlisted + embed listo para landing
