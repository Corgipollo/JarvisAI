# 📹 Cómo Subir el Demo de Jarvis a YouTube

## Paso 1: Generar el video

```bash
cd C:\Users\Emmanuel\Documents\JarvisAI
python demo_recorder.py
```

Esto creará:
- `generated/demo_videos/jarvis_demo_final_YYYYMMDD_HHMMSS.mp4`

Duración: ~2.5-3 minutos

---

## Paso 2: Subir a YouTube (Manual - Método Recomendado)

### 2.1 Ir a YouTube Studio

1. Abre **YouTube Studio**: https://studio.youtube.com
2. Click en **Crear** → **Subir videos**
3. Selecciona el archivo: `generated/demo_videos/jarvis_demo_final_*.mp4`

### 2.2 Información del video

**Título:**
```
Jarvis AI - Asistente Personal de Voz para Obsidian | Demo
```

**Descripción:**
```
🤖 Jarvis AI es tu segundo cerebro que además tiene manos.

En este demo verás:
✅ Web scraping automático (HackerNews → Excel)
✅ Integración con Obsidian (lectura de vault + resumen IA)
✅ Automatización de emails

🔗 Más info: jarvis-ai.mx
📧 Early access: [tu email]

---

Tech stack:
- Python + FastAPI
- React + Electron
- Claude API + Gemini + Ollama
- faster-whisper (STT) + edge-tts (TTS)

Open-source: https://github.com/Corgipollo/JarvisAI

#JarvisAI #IA #Obsidian #Automation #VoiceAI #ProductivityTools
```

**Miniatura:**
- Usa una captura de Jarvis en acción (generarla con `ffmpeg -i video.mp4 -ss 00:00:30 -vframes 1 thumbnail.jpg`)
- O diseña una en Canva: "JARVIS AI" + "Voice Assistant" + screenshot

**Playlist:**
- Crear playlist nueva: "Jarvis AI - Demos y Tutoriales"

**Audiencia:**
- ✅ No, no está hecho para niños

**Elementos del video:**
- Subtítulos: Subir `.srt` si generas (opcional)

---

### 2.3 Configuración de privacidad

⚠️ **IMPORTANTE**: Selecciona **"No listado"** (Unlisted)

Esto permite que:
- ✅ Solo personas con el link vean el video
- ✅ No aparece en búsquedas públicas
- ✅ Perfecto para pitch a inversionistas/clientes

**Fecha de publicación:**
- Publicar ahora (Publish now)

---

### 2.4 Obtener el link

Una vez subido, copia el link:
```
https://youtu.be/XXXXXXXXXXX
```

---

## Paso 3: Agregar link a MEMORY.md

### 3.1 Manual

Abre `MEMORY.md` y agrega al final (antes de "Próxima revisión"):

```markdown
---

## Demo Material

**Video demo (YouTube unlisted):** https://youtu.be/XXXXXXXXXXX

Fecha: 30 mayo 2026  
Duración: 2:45  
Contenido:
- Tarea 1: Web scraping HackerNews → Excel (60s)
- Tarea 2: Obsidian vault analysis + resumen IA (45s)
- Tarea 3: Email automation (30s)

---
```

### 3.2 Automatizado (con Claude Code)

Pídele a Claude:
```
Agrega el link de YouTube [pega link aquí] a MEMORY.md en la sección "Demo Material"
```

---

## Paso 4 (Opcional): Subir con API de YouTube

Si quieres automatizar completamente:

```python
# demo_youtube_upload.py
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Requiere OAuth2 setup (ver https://developers.google.com/youtube/v3/quickstart/python)

def upload_to_youtube(video_path, title, description):
    youtube = build('youtube', 'v3', credentials=credentials)
    
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': ['JarvisAI', 'IA', 'Obsidian', 'Automation'],
            'categoryId': '28'  # Science & Technology
        },
        'status': {
            'privacyStatus': 'unlisted',
            'selfDeclaredMadeForKids': False
        }
    }
    
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    
    request = youtube.videos().insert(
        part='snippet,status',
        body=body,
        media_body=media
    )
    
    response = request.execute()
    video_id = response['id']
    
    return f"https://youtu.be/{video_id}"
```

**Nota:** Requiere configurar OAuth2 en Google Cloud Console (10-15 min setup).  
Para el MVP, **subida manual es más rápida**.

---

## Checklist Final

- [ ] Video generado (`demo_recorder.py`)
- [ ] Subido a YouTube (unlisted)
- [ ] Link copiado
- [ ] Agregado a MEMORY.md sección "Demo Material"
- [ ] Video compartido en:
  - [ ] Pitch deck
  - [ ] Email a beta testers
  - [ ] LinkedIn post de Emmanuel

---

**Tiempo total estimado:** 10-15 minutos  
**Próximo paso:** Usar este video en la landing page (jarvis-ai.mx) y en outreach a primeros clientes.
