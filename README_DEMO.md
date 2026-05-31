# 🎬 Sistema de Demo de Jarvis AI

> Sistema automatizado para generar video demo de 3-5 minutos mostrando capacidades reales de Jarvis.

## 🚀 Inicio Rápido

### Método 1: Launcher Interactivo (MÁS FÁCIL)

```bash
RUN_DEMO.bat
```

Selecciona opción:
- **[1]** Demo completo con grabación de video
- **[2]** Demo rápido sin grabar (solo prueba)
- **[3]** Mostrar ayuda

---

### Método 2: Command Line Directo

**Demo completo (graba video):**
```bash
python demo_recorder.py
```

**Demo rápido (solo ejecuta tareas):**
```bash
python demo_recorder.py --no-record
```

---

## 📁 Archivos del Sistema

```
JarvisAI/
├── demo_recorder.py       # Script principal (grabación + tareas)
├── DEMO_SCRIPT.md         # Guion para narración manual
├── UPLOAD_YOUTUBE.md      # Instrucciones subida YouTube
├── RUN_DEMO.bat           # Launcher interactivo
├── README_DEMO.md         # Este archivo
└── generated/
    └── demo_videos/       # Videos generados aquí
```

---

## 🎯 Tareas Demo Incluidas

### 1️⃣ Web Scraping → Excel (90 segundos)
- Comando: *"Jarvis, busca las últimas 10 noticias de IA en HackerNews y guárdalas en Excel"*
- Ejecuta: Scraping de HackerNews API
- Resultado: `demo_hn_noticias.xlsx` con título, URL, puntuación

### 2️⃣ Obsidian Vault Analysis (60 segundos)
- Comando: *"Jarvis, lee mis notas de proyectos y dame un resumen de pendientes"*
- Ejecuta: Análisis de vault CerebroEmmanuel
- Resultado: Resumen IA de tareas urgentes vs importantes

### 3️⃣ Email Automation (45 segundos)
- Comando: *"Jarvis, envía un resumen semanal a mi equipo"*
- Ejecuta: Generación de email con plantilla
- Resultado: Email profesional enviado (simulado en demo)

---

## 🔧 Requisitos

### Software:
- ✅ Python 3.10+
- ✅ pip (gestor de paquetes)
- ⚠️ ffmpeg (opcional, para compresión de video)

### Librerías Python:
```bash
pip install mss opencv-python openpyxl requests
```
*(El script las instala automáticamente si faltan)*

### Verificar instalación:
```bash
python -c "import mss, cv2, openpyxl, requests; print('✅ Todo OK')"
```

---

## 📹 Flujo Completo

```
[1] Ejecutar demo_recorder.py
      ↓
[2] Script graba pantalla + ejecuta 3 tareas
      ↓
[3] Video guardado en generated/demo_videos/
      ↓
[4] Compresión automática con ffmpeg (si disponible)
      ↓
[5] Revisar video
      ↓
[6] Subir a YouTube (unlisted) - ver UPLOAD_YOUTUBE.md
      ↓
[7] Copiar link a MEMORY.md sección "Demo Material"
      ↓
[8] ✅ Usar en landing page, pitch deck, outreach
```

---

## ⚙️ Configuración Avanzada

### Cambiar resolución de grabación:

Editar `demo_recorder.py`:
```python
self.monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}
#                                            ↑              ↑
#                                         Cambiar aquí
```

### Cambiar duración de tareas:

Editar `demo_recorder.py` en `run_full_demo()`:
```python
# Tarea 1: Web Scraping (60 seg) ← Cambiar este número
recorder.record_for_duration(60)
```

### Personalizar tareas:

Editar funciones en `demo_recorder.py`:
- `demo_task_1_web_scraping()` - Cambiar fuente de datos
- `demo_task_2_obsidian_integration()` - Ajustar path del vault
- `demo_task_3_email_automation()` - Modificar plantilla email

---

## 🐛 Troubleshooting

### ❌ "ModuleNotFoundError: No module named 'mss'"
```bash
pip install mss opencv-python openpyxl requests
```

### ❌ "ffmpeg: command not found"
- Windows: Descargar de https://ffmpeg.org/download.html
- Agregar al PATH de Windows
- O ignorar (video se genera sin compresión, solo más pesado)

### ❌ Video sale muy pesado (>500 MB)
- Instalar ffmpeg para compresión automática
- O comprimir manualmente después:
  ```bash
  ffmpeg -i video_raw.avi -c:v libx264 -crf 23 video_compressed.mp4
  ```

### ❌ Vault de Obsidian no encontrado
- Verificar path en `demo_task_2_obsidian_integration()`:
  ```python
  vault_path = Path(r"C:\Users\Emmanuel\Documents\CerebroEmmanuel")
  ```
- Cambiar al path correcto de tu vault

### ❌ Grabación sale en negro
- Verificar permisos de captura de pantalla
- Probar con otra app en el frente
- Reiniciar Python y volver a intentar

---

## 📊 Métricas del Video

**Objetivo:**
- Duración: 3-5 minutos ✅
- Resolución: 1920x1080 (Full HD) ✅
- FPS: 30 ✅
- Tamaño final: <100 MB (con ffmpeg) ✅
- Formato: MP4 (H.264 + AAC) ✅

**Optimizado para:**
- YouTube (unlisted)
- Embedding en landing page
- Envío por email (link)
- Presentaciones (descarga + reproducción local)

---

## 🎨 Personalización para Versión Final

El sistema automatizado es ideal para **prueba rápida** y **MVP**.

Para **versión comercial profesional**, considera:

1. **Grabación manual con narración** (ver `DEMO_SCRIPT.md`)
   - Voz de Emmanuel > voz sintética
   - Storytelling > ejecución robótica
   - Más personal = más conversión

2. **Edición profesional**
   - DaVinci Resolve (gratis) o Premiere Pro
   - Subtítulos en español (accesibilidad + engagement)
   - Background music sutil (Epidemic Sound, Artlist)
   - Overlays de texto para highlights

3. **Miniatura custom**
   - Diseño en Canva
   - Incluir logo de Jarvis + screenshot atractivo
   - Texto: "JARVIS AI - Voice Assistant Demo"

4. **Call to Action fuerte**
   - Últimos 10 segundos: pantalla con jarvis-ai.mx
   - Descripción del video: link directo a landing
   - Comentario pinnned: "Early access: [formulario]"

---

## 📈 Próximos Pasos

Una vez tengas el video en YouTube:

1. ✅ Agregar link a `MEMORY.md`
2. ✅ Embeber en landing page (jarvis-ai.mx)
3. ✅ Usar en pitch deck para inversionistas
4. ✅ Compartir con primeros 3 beta testers (Paso 2 del plan)
5. ✅ Post en LinkedIn de Emmanuel (storytelling + link)
6. ✅ Agregar a README del repo GitHub

---

## 📞 Soporte

Si algo no funciona:
1. Verificar requisitos (Python, pip, dependencias)
2. Revisar sección Troubleshooting arriba
3. Ejecutar test de verificación:
   ```bash
   python -c "exec(open('demo_recorder.py').read().split('if __name__')[0]); print('Test OK')"
   ```

---

**Tiempo total estimado:** 10-15 minutos (demo automatizado) o 1 hora (versión manual profesional)

**Resultado:** Video demo profesional listo para pitch a primeros clientes 🚀
