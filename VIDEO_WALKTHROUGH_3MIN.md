# 🎬 JARVIS AI — VIDEO WALKTHROUGH (3 MINUTOS)

**Audiencia:** Usuario técnico nuevo, sabe Git/Python/Node pero nunca usó Jarvis  
**Objetivo:** Del git clone a primer comando de voz en 3 minutos  
**Tono:** Directo, sin fluff, mostrar NO explicar  

---

## 📝 GUION (3:00 TOTAL)

### [0:00 - 0:15] HOOK + PROBLEMA (15 seg)

**[VISUAL: Pantalla dividida — izquierda: caos de 10 apps abiertas, derecha: una sola ventana de Jarvis]**

**VOICEOVER:**
> "Cambias de contexto 300 veces al día. Spotify. Obsidian. Terminal. Navegador.  
> ¿Y si controlaras todo con tu voz, sin tocar el mouse?  
> Esto es Jarvis AI. Instalación completa en 3 minutos."

**[VISUAL: Título animado "JARVIS AI — Del Git Clone a 'Hola Jarvis' en 3 min"]**

---

### [0:15 - 0:45] REQUISITOS PRE-VUELO (30 seg)

**[VISUAL: Screencast de Windows 11, terminal abierta]**

**VOICEOVER:**
> "Requisitos: Windows 11, Python 3.11, Node 20, Git.  
> Si no los tienes, el script te dirá exactamente qué instalar."

**[VISUAL: Ejecutar comandos rápidamente]**
```powershell
python --version  # 3.11.9
node --version    # v20.12.0
git --version     # 2.45.0
```

**[MOSTRAR: Checkmarks verdes apareciendo]**

**VOICEOVER:**
> "Todo listo. Vamos."

---

### [0:45 - 1:30] INSTALACIÓN AUTOMÁTICA (45 seg)

**[VISUAL: Clone del repo]**
```powershell
cd C:\Users\TU_USUARIO\Documents
git clone https://github.com/TU_USUARIO/JarvisAI.git
cd JarvisAI
```

**VOICEOVER:**
> "Clona el repo. Ejecuta el instalador."

**[VISUAL: Ejecutar script]**
```powershell
.\install-v2-zero-friction.ps1
```

**[VISUAL: Time-lapse del script corriendo — mostrar pasos clave en pantalla]**
- ✓ Verificando Python 3.11... OK
- ✓ Verificando Node 20... OK
- ✓ Instalando backend dependencies... OK
- ✓ Instalando frontend dependencies... OK
- ⚠ Gemini API Key NO configurada

**VOICEOVER:**
> "El script detecta tu sistema, instala todo automáticamente.  
> Te pide configurar Gemini. Gratis, toma 30 segundos."

**[VISUAL: Navegador abre https://aistudio.google.com/apikey]**

**VOICEOVER:**
> "Clic en 'Create API Key'. Copia."

**[VISUAL: Pegar en .env]**
```
GEMINI_API_KEY=tu_key_aqui
```

**[MOSTRAR: ✓ Gemini API Key válida y funcional]**

---

### [1:30 - 2:15] PRIMER USO — CONTROL DE SPOTIFY (45 seg)

**VOICEOVER:**
> "Instalación completa. Ahora el primer caso de uso real:  
> Controla Spotify con tu voz."

**[VISUAL: Abrir START_JARVIS_FULL.bat]**
```powershell
.\START_JARVIS_FULL.bat
```

**[VISUAL: Split-screen — Backend en terminal, Frontend Electron abriendo]**

**Backend:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

**Frontend:**
**[MOSTRAR: Ventana Electron con interfaz de Jarvis, micrófono listo]**

**VOICEOVER:**
> "Backend y frontend corriendo. Interfaz lista."

**[VISUAL: Usuario habla al micrófono]**

**USUARIO (voz real):** "Jarvis, reproduce música en Spotify"

**[VISUAL: Waveform animada mientras transcribe]**

**[MOSTRAR: Transcripción apareciendo en pantalla]**
```
[Usuario]: Jarvis, reproduce música en Spotify
```

**[MOSTRAR: Respuesta de Jarvis]**
```
[Jarvis]: Reproduciendo música en Spotify. Playlist activa: Discover Weekly.
```

**[VISUAL: Spotify abriendo y reproduciendo música]**

**VOICEOVER:**
> "Spotify abre y reproduce. Sin tocar el mouse."

---

### [2:15 - 2:45] SEGUNDO CASO — CAPTURA Y ANALIZA PANTALLA (30 seg)

**VOICEOVER:**
> "Segundo caso de uso: analiza tu pantalla con IA."

**[VISUAL: Usuario tiene un error de código en VSCode]**

**USUARIO (voz):** "Jarvis, toma una captura y analízala"

**[VISUAL: Screenshot capturada, enviándose a Claude Vision]**

**[MOSTRAR: Respuesta de Jarvis]**
```
[Jarvis]: Veo un error en tu código Python, línea 47.
Falta cerrar el paréntesis en la función `calculate_total()`.
Sugerencia: Agrega `)` después de `price`.
```

**[VISUAL: Usuario corrige el error basado en la sugerencia]**

**VOICEOVER:**
> "Claude Vision detecta el error. Te da el fix. Siguiente."

---

### [2:45 - 3:00] CIERRE + CTA (15 seg)

**[VISUAL: Pantalla final con 3 puntos clave]**

**VOICEOVER:**
> "Jarvis AI. Voice-first. 100% local. Privado.  
> Control de Spotify, análisis de pantalla, integración con Obsidian.  
> Link en la descripción. Instalación en 3 minutos."

**[VISUAL: Fade a logo de Jarvis + repo GitHub]**

**TEXTO EN PANTALLA:**
```
github.com/TU_USUARIO/JarvisAI
Requisitos: Win 11 | Python 3.11 | Node 20
API Gemini gratis: aistudio.google.com/apikey
```

**[MÚSICA: Fade out]**

---

## 🎥 ESPECIFICACIONES TÉCNICAS

### Resolución
- **1920x1080 (1080p)** — screencast de Windows

### Duración Total
- **3:00** exactos (puede ser 2:50 - 3:10)

### Secciones Timing
| Sección | Tiempo | Frames (30fps) |
|---------|--------|----------------|
| Hook + Problema | 0:00 - 0:15 | 0 - 450 |
| Requisitos | 0:15 - 0:45 | 450 - 1350 |
| Instalación | 0:45 - 1:30 | 1350 - 2700 |
| Caso Uso 1 (Spotify) | 1:30 - 2:15 | 2700 - 4050 |
| Caso Uso 2 (Screenshot) | 2:15 - 2:45 | 4050 - 4950 |
| Cierre + CTA | 2:45 - 3:00 | 4950 - 5400 |

### Audio
- **Voiceover:** Voz natural (puede ser edge-tts con voz es-MX-DaliaNeural)
- **Música de fondo:** Ambient tech (bajo volumen, -20dB)
- **SFX:** Checkmarks, notificaciones (sutiles)

### Herramientas de Grabación
- **Screencast:** OBS Studio (1080p60, CRF 18)
- **Edición:** DaVinci Resolve / Premiere Pro
- **Voiceover:** edge-tts (si automatizado) o grabación manual

### Estilos Visuales
- **Anotaciones:** Flechas y highlights en amarillo/cyan
- **Tipografía:** Monospace para código, sans-serif para texto
- **Transiciones:** Cuts rápidos, sin fades lentos
- **Cursor:** Resaltar con círculo cuando hace clic

---

## 📋 CHECKLIST DE PRODUCCIÓN

### Pre-Producción
- [ ] Script completo revisado y cronometrado
- [ ] Storyboard visual (opcional pero útil)
- [ ] Preparar cuenta Gemini con API key de prueba
- [ ] Limpiar desktop de Windows (sin iconos innecesarios)

### Grabación
- [ ] Screencast en 1080p60
- [ ] Todos los comandos funcionan sin errores
- [ ] Spotify configurado y listo para demo
- [ ] Micrófono de calidad para voiceover (o usar edge-tts)

### Post-Producción
- [ ] Editar a 3:00 exactos
- [ ] Agregar anotaciones/flechas donde necesario
- [ ] Música de fondo mezclada correctamente
- [ ] Color grading (contraste alto para legibilidad de código)
- [ ] Agregar subtítulos (SRT) en español e inglés

### Distribución
- [ ] Exportar en H.264, 1080p, 5-10 Mbps
- [ ] Subir a YouTube con timestamp chapters:
  ```
  0:00 Intro
  0:15 Requisitos
  0:45 Instalación
  1:30 Control de Spotify
  2:15 Análisis de Pantalla
  2:45 Conclusión
  ```
- [ ] Thumbnail llamativo (mockup de Jarvis + "3 MIN INSTALL")

---

## 🎯 MÉTRICAS DE ÉXITO

**KPI del video:**
- **Retención >70%** en los primeros 30 segundos (el hook)
- **Watch time >2:00** promedio (usuarios ven al menos hasta Spotify demo)
- **CTR del link** en descripción >5%

**Conversión esperada:**
- **30%** de viewers intentan instalar Jarvis
- **10%** completan instalación exitosamente
- **5%** configuran al menos 1 integración (Spotify/Obsidian)

---

## 💡 TIPS DE PRODUCCIÓN

1. **Velocidad 1.2x en partes de instalación:** Para que parezca más rápido sin perder legibilidad
2. **Zoom in cuando importa:** Comando crítico = zoom al código
3. **No leer literalmente el script:** Sonar natural, no robotizado
4. **Mostrar ERRORES reales y cómo el script los maneja:** Demuestra robustez
5. **B-roll opcional:** Pantallas de loading pueden tener b-roll de código/terminal

---

**Siguiente paso:** Grabar, editar, publicar.  
**Herramienta recomendada para auto-generación:** Remotion (si quieres scripted video) o manual con OBS.
